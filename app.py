"""
gmach-api v8 – full version
– מקבל search_term מ-Yemot
– משווה מול Google Sheet ומחזיר טקסט TTS או מעבר לשלוחה
"""

import os, csv, time, re, logging
from flask import Flask, request
import requests

# --------------------------------------------------
#  Logger
# --------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --------------------------------------------------
#  Consts
# --------------------------------------------------
SHEET_URL = ("https://docs.google.com/spreadsheets/d/"
             "1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/"
             "export?format=csv")

app = Flask(__name__)

# --------------------------------------------------
#  Cache for the sheet (120 s)
# --------------------------------------------------
_sheet_cache = {"t": 0, "rows": []}

# --------------------------------------------------
#  Helpers
# --------------------------------------------------
_bad_chars = '"\r\n'          # גורם ל-"אין מענה" בי-מות

def safe(s: str) -> str:
    """מסיר תווי-בקרה/גרשיים כפולים לפני החזרה ל-Yemot."""
    for ch in _bad_chars:
        s = s.replace(ch, "")
    return s.strip()

_punct_rx = re.compile(r"[^\w\u0590-\u05fe ]", re.UNICODE)

def clean_txt(s: str) -> str:
    """אותיות נמוכות, בלי ניקוד/פסיקים, ריבוי רווחים."""
    if not s:
        return ""
    s = s.lower()
    s = _punct_rx.sub(" ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def load_sheet():
    """טוען / מאחזר מהקאש את גיליון הגמח״ים."""
    now = time.time()
    if now - _sheet_cache["t"] < 120 and _sheet_cache["rows"]:
        return _sheet_cache["rows"]

    try:
        resp = requests.get(SHEET_URL, timeout=10)
        resp.raise_for_status()
        rows = []
        for r in csv.DictReader(resp.text.splitlines()):
            name = (r.get("שם הגמח") or "").strip()
            msg  = (r.get("טקסט להשמעה") or "").strip()
            ext  = (r.get("שלוחה להשמעה") or "").strip()
            rows.append({
                "name": name,
                "name_clean": clean_txt(name),
                "msg": msg,
                "msg_clean": clean_txt(msg),
                "ext": ext
            })
        _sheet_cache.update(t=time.time(), rows=rows)
        logging.info("Sheet ↻ %d rows", len(rows))
        return rows
    except Exception as e:
        logging.error("Sheet load error: %s", e)
        return []

def partial_match(q: str, rec: str) -> bool:
    """True אם כל המילים בשאילתה מופיעות בטקסט היעד (בסדר כלשהו)."""
    q_words = q.split()
    rec     = clean_txt(rec)
    return all(w in rec for w in q_words)

# --------------------------------------------------
#  Core logic
# --------------------------------------------------
def handle_text(text: str) -> str:
    q = clean_txt(text)
    if not q:
        return "say_api_answer=yes\nid_list_message=t-" + safe("לא התקבל טקסט")

    matches = []
    for row in load_sheet():
        if partial_match(q, row["name_clean"]) or partial_match(q, row["msg_clean"]):
            matches.append(row)

    logging.info("🔍 total matches: %d", len(matches))

    # --- לא נמצא בכלל
    if not matches:
        return "say_api_answer=yes\nid_list_message=t-" + safe("לא נמצא גמח מתאים")

    # --- התאמה יחידה
    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{safe(m['ext'])}"
        msg = m["msg"] or "אין מידע נוסף"
        return "say_api_answer=yes\nid_list_message=t-" + safe(msg)

    # --- כמה התאמות
    tts = "מצאתי כמה גמחים:\n"
    for i, m in enumerate(matches[:5], 1):
        tts += f"{i}. {m['name']}\n"
    return "say_api_answer=yes\nid_list_message=t-" + safe(tts)

# --------------------------------------------------
#  Routes
# --------------------------------------------------
@app.route("/", methods=["POST"])
def api():
    text = request.form.get("search_term", "")
    logging.info("🎤 raw text: '%s'", text)
    resp = handle_text(text)
    logging.info("⤴️  response to Yemot: %s", resp.encode('utf-8'))
    return resp

@app.route("/")
def home():
    return "OK – gmach-api v8"

# --------------------------------------------------
#  Run (Render sets $PORT)
# --------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
