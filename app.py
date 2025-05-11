from flask import Flask, request
import requests, os, csv, tempfile, shutil
from pathlib import Path

ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY")  # set this in Render env vars
ELEVEN_ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"

SHEET_URL = "https://docs.google.com/spreadsheets/d/1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"

app = Flask(__name__)

def load_sheet():
    try:
        resp = requests.get(SHEET_URL, timeout=10)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        reader = csv.DictReader(lines)
        rows = []
        for row in reader:
            rows.append({
                "name": row.get("שם הגמח",""),
                "ext": row.get("שלוחה להשמעה",""),
                "message": row.get("טקסט להשמעה","")
            })
        return rows
    except Exception as e:
        print("Error loading sheet:", e)
        return []

def transcribe_with_eleven(path):
    if ELEVEN_API_KEY is None:
        print("ELEVEN_API_KEY not set")
        return ""
    headers = {"xi-api-key": ELEVEN_API_KEY}
    files = {"file": open(path,"rb")}
    data = {"model_id":"scribe_v1","language_code":"heb"}
    try:
        r = requests.post(ELEVEN_ENDPOINT, headers=headers, files=files, data=data, timeout=60)
        r.raise_for_status()
        js = r.json()
        return js.get("text","")
    except Exception as e:
        print("STT error:", e)
        return ""

def handle_text(text):
    text = text.lower()
    sheet = load_sheet()
    matches=[]
    for row in sheet:
        name_words = row["name"].lower().split()
        msg_lower = row["message"].lower()
        score = 0
        for w in text.split():
            if w in name_words or w in msg_lower:
                score +=1
        if score>=1:
            matches.append(row)
    if not matches:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמ"ח מתאים"
    if len(matches)==1:
        m=matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        elif m["message"]:
            return f"say_api_answer=yes\nid_list_message=t-{m['message']}"
        else:
            return "say_api_answer=yes\nid_list_message=t-גמ\"ח נמצא אך אין מידע נוסף"
    tts="מצאתי מספר גמחים:\n"
    for i,m in enumerate(matches[:5],1):
        tts+=f"{i}. {m['name']}\n"
    return f"say_api_answer=yes\nid_list_message=t-{tts}"

@app.route("/",methods=["POST"])
def api():
    if "search_term" in request.form and request.form.get("search_term"):
        text=request.form.get("search_term")
        print("VOICE TEXT:", text)
        return handle_text(text)
    if "file_url" in request.form:
        file_url=request.form.get("file_url")
        print("Got file url:", file_url)
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                r=requests.get(file_url,timeout=30)
                tmp.write(r.content)
                tmp_path=tmp.name
            text=transcribe_with_eleven(tmp_path)
            print("ELEVEN STT:", text)
            os.unlink(tmp_path)
            if text:
                return handle_text(text)
            else:
                return "say_api_answer=yes\nid_list_message=t-לא הצלחתי להבין את ההקלטה"
        except Exception as e:
            print("Download/STT error:",e)
            return "say_api_answer=yes\nid_list_message=t-שגיאה בטיפול בהקלטה"
    return "say_api_answer=yes\nid_list_message=t-לא התקבל נתון"

@app.route("/",methods=["GET"])
def home():
    return "OK"

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)