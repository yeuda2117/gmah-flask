"""
Enhanced debug version for Yemot Gmach search with ElevenLabs STT.
Handles both search_term (voice) and file_url (record) + full logging.
"""

import os, csv, time, logging, tempfile, requests
from flask import Flask, request

# ---------- basic logging ----------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# ---------- constants ----------
ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY")
ELEVEN_ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
SHEET_URL = ("https://docs.google.com/spreadsheets/d/"
             "1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv")

app = Flask(__name__)

# ---------- Google-Sheet cache (120 s) ----------
_sheet_cache = {"ts": 0.0, "rows": []}


def load_sheet():
    now = time.time()
    if now - _sheet_cache["ts"] < 120 and _sheet_cache["rows"]:
        return _sheet_cache["rows"]

    try:
        resp = requests.get(SHEET_URL, timeout=10)
        resp.raise_for_status()
        reader = csv.DictReader(resp.text.splitlines())
        rows = [{
            "name": r.get("שם הגמח", ""),
            "ext":  r.get("שלוחה להשמעה", ""),
            "msg":  r.get("טקסט להשמעה", "")
        } for r in reader]

        _sheet_cache.update(ts=now, rows=rows)
        logging.info("Sheet loaded %d rows", len(rows))
        return rows
    except Exception as e:
        logging.error("Sheet load error: %s", e)
        return []


# ---------- Eleven-Labs STT ----------
def stt_eleven(path):
    if not ELEVEN_API_KEY:
        logging.error("ELEVEN_API_KEY missing!")
        return ""

    headers = {"xi-api-key": ELEVEN_API_KEY}
    files = {"file": open(path, "rb")}
    data = {"model_id": "scribe_v1", "language_code": "heb"}

    try:
        r = requests.post(ELEVEN_ENDPOINT, headers=headers,
                          files=files, data=data, timeout=90)
        if r.status_code != 200:
            logging.error("STT bad status %s: %s",
                          r.status_code, r.text[:300])
            return ""
        text = r.json().get("text", "")
        logging.info("STT text: '%s'", text)
        return text
    except Exception as e:
        logging.error("STT exception: %s", e)
        return ""


# ---------- business logic ----------
def handle_text(text: str) -> str:
    text = text.lower().strip()
    if not text:
        return "say_api_answer=yes\nid_list_message=t-לא התקבל טקסט"

    rows = load_sheet()
    matches = []
    for r in rows:
        score = sum(1 for w in text.split()
                    if w in r["name"].lower() or w in r["msg"].lower())
        if score:
            matches.append(r)

    if not matches:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמח מתאים"

    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        return ("say_api_answer=yes\nid_list_message=t-" +
                (m['msg'] or "אין מידע נוסף"))

    # 2+ תוצאות
    tts = "מצאתי מספר גמחים:\n" + \
          "\n".join(f"{i+1}. {m['name']}" for i, m in enumerate(matches[:5]))
    return f"say_api_answer=yes\nid_list_message=t-{tts}"


# ---------- Flask route ----------
@app.route("/", methods=["POST"])
def api():
    logging.info("---- NEW POST ----")
    logging.info("Headers: %s", dict(request.headers))
    logging.info("Form keys: %s", list(request.form.keys()))

    # -------- voice / search_term --------
    if request.form.get("search_term"):
        text = request.form["search_term"]
        logging.info("VOICE TEXT (raw): '%s'", text)

        # אם זה שם-קובץ (‎*.wav) - נוריד ונשלח ל-STT
        if text.endswith(".wav"):
            ext = request.form.get("ApiExtension", "").lstrip("/")
            url = f"https://media.yemot.co.il/Msgs/{ext}/{text}"
            logging.info("⬇️  download: %s", url)

            try:
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                with tempfile.NamedTemporaryFile(delete=False,
                                                 suffix=".wav") as tmp:
                    tmp.write(r.content)
                    tmp_path = tmp.name

                text = stt_eleven(tmp_path)
                os.unlink(tmp_path)
            except Exception as e:
                logging.error("Download/STT chain error: %s", e)
                return ("say_api_answer=yes\n"
                        "id_list_message=t-שגיאה בעיבוד ההקלטה")

        logging.info("✅ final text: '%s'", text)
        return handle_text(text)

    # -------- record / file_url --------
    if request.form.get("file_url"):
        url = request.form["file_url"]
        logging.info("file_url: %s", url)
        try:
            with tempfile.NamedTemporaryFile(delete=False,
                                             suffix=".wav") as tmp:
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                tmp.write(r.content)
                tmp_path = tmp.name

            text = stt_eleven(tmp_path)
            os.unlink(tmp_path)
            return (handle_text(text) if text else
                    "say_api_answer=yes\nid_list_message=t-לא הבנתי את ההקלטה")
        except Exception as e:
            logging.error("Download/STT chain error: %s", e)
            return "say_api_answer=yes\nid_list_message=t-שגיאה בטיפול בהקלטה"

    logging.warning("POST missing expected fields")
    return "say_api_answer=yes\nid_list_message=t-לא קיבלתי נתונים"


@app.route("/", methods=["GET"])
def home():
    return "OK – gmah debug full"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

