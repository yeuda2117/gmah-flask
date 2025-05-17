"""
gmach-api v8 – without say_api_answer
"""
from flask import Flask, request
import requests, os, csv, tempfile, logging, time, re

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY")
ELEVEN_ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
SHEET_URL = ("https://docs.google.com/spreadsheets/d/"
             "1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv")

app = Flask(__name__)

# ---------- helpers ----------------------------------------------------------
_sheet_cache = {"t": 0, "rows": []}


def clean_txt(t: str) -> str:
    return re.sub(r"[^א-תa-z0-9 ]", " ", t.lower()).strip()


def load_sheet():
    now = time.time()
    if now - _sheet_cache["t"] < 120 and _sheet_cache["rows"]:
        return _sheet_cache["rows"]

    try:
        r = requests.get(SHEET_URL, timeout=10)
        r.raise_for_status()
        rows = []
        for row in csv.DictReader(r.text.splitlines()):
            rows.append({
                "name": row.get("שם הגמח", ""),
                "msg": row.get("טקסט להשמעה", ""),
                "ext": row.get("שלוחה להשמעה", ""),
                "name_clean": clean_txt(row.get("שם הגמח", "")),
                "msg_clean": clean_txt(row.get("טקסט להשמעה", "")),
            })
        _sheet_cache.update(t=now, rows=rows)
        logging.info("Sheet ↻ %d rows", len(rows))
        return rows
    except Exception as e:
        logging.error("Sheet error: %s", e)
        return []


def handle_text(text: str) -> str:
    q = clean_txt(text)
    if not q:
        return "id_list_message=t-לא התקבל טקסט"

    rows = load_sheet()
    matches = []
    for row in rows:
        if q in row["name_clean"] or q in row["msg_clean"]:
            matches.append(row)

    logging.info("🔍 total matches: %d", len(matches))

    if not matches:
        return "id_list_message=t-לא נמצא גמח מתאים"

    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        msg = m["msg"] or "אין מידע נוסף"
        return f"id_list_message=t-{msg}"

    # several results → רשימה
    tts = "מצאתי כמה גמחים:\n"
    for i, m in enumerate(matches[:5], 1):
        tts += f"{i}. {m['name']}\n"
    return f"id_list_message=t-{tts}"


# ---------- routes -----------------------------------------------------------
@app.route("/", methods=["POST"])
def api():
    text = request.form.get("search_term", "")
    logging.info("🎤 raw text: '%s'", text)

    resp = handle_text(text)
    logging.info("⤴️  response to Yemot: %s", resp.encode("utf-8"))
    return resp


@app.route("/")
def home():
    return "OK – gmach-api v8"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
