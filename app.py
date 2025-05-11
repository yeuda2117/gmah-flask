"""Enhanced debug version for Yemot Gmach search with ElevenLabs STT.
   - Handles both search_term (voice) and file_url (record)
   - Extensive logging of headers, form keys, response data
   - Returns proper responses to Yemot
   - Does NOT overwrite old project if deployed to a different render service/repo
"""

from flask import Flask, request
import requests, os, csv, tempfile, logging, json, time

# configure logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY")
ELEVEN_ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"

app = Flask(__name__)

# cache sheet for 2 minutes to reduce hits
_sheet_cache = {"time":0, "rows":[]}

def load_sheet():
    now=time.time()
    if now-_sheet_cache["time"]<120 and _sheet_cache["rows"]:
        return _sheet_cache["rows"]
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
        _sheet_cache["rows"]=rows
        _sheet_cache["time"]=now
        logging.info("Sheet loaded %d rows", len(rows))
        return rows
    except Exception as e:
        logging.error("Sheet load error: %s", e)
        return []

def stt_eleven(path):
    if not ELEVEN_API_KEY:
        logging.error("ELEVEN_API_KEY missing in env!")
        return ""
    headers = {"xi-api-key": ELEVEN_API_KEY}
    files = {"file": open(path,"rb")}
    data = {"model_id":"scribe_v1","language_code":"heb"}
    try:
        r = requests.post(ELEVEN_ENDPOINT, headers=headers, files=files, data=data, timeout=90)
        if r.status_code!=200:
            logging.error("Eleven STT bad status %s: %s", r.status_code, r.text[:300])
            return ""
        js=r.json()
        text=js.get("text","")
        logging.info("Eleven STT OK: '%s'", text)
        return text
    except Exception as e:
        logging.error("Eleven STT exception: %s", e)
        return ""

def handle_text(text):
    logging.info("handle_text(): '%s'", text)
    text=text.lower().strip()
    if not text:
        return "say_api_answer=yes\nid_list_message=t-לא התקבל טקסט"
    rows=load_sheet()
    matches=[]
    for row in rows:
        name_words=row["name"].lower().split()
        msg=row["message"].lower()
        words=text.split()
        score=sum(1 for w in words if w in name_words or w in msg)
        if score>=1:
            matches.append(row)
    if not matches:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמח מתאים"
    if len(matches)==1:
        m=matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        msg=m["message"] or "אין מידע נוסף"
        return f"say_api_answer=yes\nid_list_message=t-{msg}"
    tts="מצאתי מספר גמחים:\n"
    for i,m in enumerate(matches[:5],1):
        tts+=f"{i}. {m['name']}\n"
    return f"say_api_answer=yes\nid_list_message=t-{tts}"

@app.route("/", methods=["POST"])
def api():
    logging.info("---- NEW POST ----")
    logging.info("Headers: %s", dict(request.headers))
    logging.info("Form keys: %s", list(request.form.keys()))
    # Voice pathway
    if request.form.get("search_term"):
        text=request.form.get("search_term")
        logging.info("VOICE TEXT: '%s'", text)
        return handle_text(text)
    # Record pathway
    if request.form.get("file_url"):
        url=request.form.get("file_url")
        logging.info("file_url received: %s", url)
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                r=requests.get(url, timeout=30)
                r.raise_for_status()
                tmp.write(r.content)
                tmp_path=tmp.name
            text=stt_eleven(tmp_path)
            os.unlink(tmp_path)
            if text:
                return handle_text(text)
            else:
                return "say_api_answer=yes\nid_list_message=t-לא הבנתי את ההקלטה"
        except Exception as e:
            logging.error("Download/STT chain error: %s", e)
            return "say_api_answer=yes\nid_list_message=t-שגיאה בטיפול בהקלטה"
    logging.warning("POST missing expected fields")
    return "say_api_answer=yes\nid_list_message=t-לא קיבלתי נתונים"

@app.route("/", methods=["GET"])
def home():
    return "OK - gmah debug full"

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)