"""Flask API for Yemot Gmach search – improved matching
-----------------------------------------------------
• clean_text() – normalises Hebrew/English strings (lower case, strips ניקוד, תווים מיוחדים, גרשיים).  
• partial_match() – basic fuzzy match using difflib + word‑overlap.  
• prefers `file_url` (אם יישלח בעתיד) אבל תומך רק ב‑search_term כרגע.  
• sheet cache 2 דק׳.  
• מחזיר תוצאה אחת / רשימה / אין תוצאה.
"""

from flask import Flask, request
import requests, os, csv, tempfile, logging, time, re, difflib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY")  # לא בשימוש כעת
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"

app = Flask(__name__)
_sheet_cache = {"ts": 0, "rows": []}

############################################################
# helpers
############################################################

def clean_text(txt: str) -> str:
    """Lower‑case, strip nikud/punctuation, collapse spaces."""
    if not txt:
        return ""
    # Hebrew nikud range \u0590-\u05C7
    txt = re.sub(r"[\u0590-\u05C7]", "", txt)
    # remove punctuation / special chars
    txt = re.sub(r"[^\w\s]", "", txt)
    return re.sub(r"\s+", " ", txt.lower()).strip()


def load_sheet():
    now = time.time()
    if now - _sheet_cache["ts"] < 120 and _sheet_cache["rows"]:
        return _sheet_cache["rows"]
    try:
        r = requests.get(SHEET_URL, timeout=10)
        r.raise_for_status()
        reader = csv.DictReader(r.text.splitlines())
        rows = []
        for row in reader:
            rows.append({
                "name": row.get("שם הגמח", "").strip(),
                "name_clean": clean_text(row.get("שם הגמח", "")),
                "ext": row.get("שלוחה להשמעה", "").strip(),
                "msg": row.get("טקסט להשמעה", "").strip(),
                "msg_clean": clean_text(row.get("טקסט להשמעה", ""))
            })
        _sheet_cache.update(ts=now, rows=rows)
        logging.info("Sheet ↻ %d rows", len(rows))
        return rows
    except Exception as e:
        logging.error("Sheet load error: %s", e)
        return []


def partial_match(query: str, target: str) -> bool:
    """basic fuzzy check – True if high similarity (>0.6)"""
    if not query or not target:
        return False
    if query in target:
        return True
    ratio = difflib.SequenceMatcher(None, query, target).ratio()
    return ratio >= 0.6

############################################################
# main logic
############################################################

def handle_text(text: str):
    q = clean_text(text)
    if not q:
        return "say_api_answer=yes\nid_list_message=t-לא התקבל טקסט"

    rows = load_sheet()
    matches = []
    for row in rows:
        if partial_match(q, row["name_clean"]) or partial_match(q, row["msg_clean"]):
            matches.append(row)

    if not matches:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמח מתאים"

    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        msg = m["msg"] or "אין מידע נוסף"
        return f"say_api_answer=yes\nid_list_message=t-{msg}"

    # several matches – החזר רשימה
    tts = "מצאתי יותר מגמ" + "ח אחד:\n"
    for i, m in enumerate(matches[:5], 1):
        tts += f"{i}. {m['name']}\n"
    return f"say_api_answer=yes\nid_list_message=t-{tts}"

############################################################
# routes
############################################################

@app.route("/", methods=["POST"])
def api():
    logging.info("---- NEW POST ----")
    logging.info("Form keys: %s", list(request.form.keys()))

    # ימות כבר מזהה דיבור → search_term מחזיק את הטקסט
    if request.form.get("search_term"):
        raw = request.form.get("search_term")
        logging.info("🎤 raw text: '%s'", raw)
        return handle_text(raw)

    logging.warning("אין search_term בבקשה")
    return "say_api_answer=yes\nid_list_message=t-לא קיבלתי נתון זיהוי"

@app.route("/", methods=["GET"])
def home():
    return "OK - gmach matcher v2"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
