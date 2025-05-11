
from flask import Flask, request
import requests, os, csv, tempfile

ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY")
ELEVEN_ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"

app = Flask(__name__)

# ---- helpers ----
def load_sheet():
    try:
        resp = requests.get(SHEET_URL, timeout=10)
        resp.raise_for_status()
        reader = csv.DictReader(resp.text.splitlines())
        rows=[]
        for r in reader:
            rows.append({
                "name": r.get("שם הגמח",""),
                "ext" : r.get("שלוחה להשמעה",""),
                "message": r.get("טקסט להשמעה","")
            })
        return rows
    except Exception as e:
        print("Sheet load error:", e)
        return []

def stt_eleven(path):
    if not ELEVEN_API_KEY:
        print("ELEVEN_API_KEY missing!")
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
        print("Eleven STT error:", e)
        return ""

def handle_text(text):
    print("===> handle_text():", text)
    text = text.lower()
    sheet = load_sheet()
    matches=[]
    for row in sheet:
        name_words = row["name"].lower().split()
        msg_lower = row["message"].lower()
        score=0
        for w in text.split():
            if w in name_words or w in msg_lower:
                score+=1
        if score>=1:
            matches.append(row)
    if not matches:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמח מתאים"
    if len(matches)==1:
        m=matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        elif m["message"]:
            return f"say_api_answer=yes\nid_list_message=t-{m['message']}"
        else:
            return "say_api_answer=yes\nid_list_message=t-גמח נמצא אך אין מידע נוסף"
    # many results
    tts="מצאתי מספר גמחים:\n"
    for i,m in enumerate(matches[:5],1):
        tts += f"{i}. {m['name']}\n"
    return f"say_api_answer=yes\nid_list_message=t-{tts}"

# ---- routes ----
@app.route("/", methods=["POST"])
def api():
    print("---- NEW POST ----")
    print("Headers:", dict(request.headers))
    print("Form data keys:", list(request.form.keys()))

    if request.form.get("search_term"):
        text=request.form.get("search_term")
        print("VOICE TEXT:", text)
        return handle_text(text)

    if request.form.get("file_url"):
        url=request.form.get("file_url")
        print("file_url received:", url)
        try:
            tmp=tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            r=requests.get(url, timeout=30)
            tmp.write(r.content)
            tmp.close()
            text=stt_eleven(tmp.name)
            print("STT result:", text)
            os.unlink(tmp.name)
            if text:
                return handle_text(text)
            else:
                return "say_api_answer=yes\nid_list_message=t-לא הצלחתי להבין את ההקלטה"
        except Exception as e:
            print("Download/STT chain error:", e)
            return "say_api_answer=yes\nid_list_message=t-שגיאה בעת עיבוד ההקלטה"

    print("No usable fields in POST")
    return "say_api_answer=yes\nid_list_message=t-לא קיבלתי נתונים"

@app.route("/", methods=["GET"])
def home():
    return "OK"

if __name__ == "__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
