"""Flask API for Yemot Gmach search – improved matching + debug logging
---------------------------------------------------------------------
• clean_text – מנרמל טקסט.
• partial_match – התאמה חלקית + fuzzy.
• לוגים: בדיקה של כל שורה + תוצאות סופיות.
• מתבסס על search_term (זיהוי־דיבור בימות).
"""

from flask import Flask, request
import requests, os, csv, logging, time, re, difflib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"

app = Flask(__name__)
_sheet_cache = {"ts": 0, "rows": []}

# -------------------------------------------------------------
# helpers
# -------------------------------------------------------------

def clean_text(txt: str) -> str:
    if not txt:
        return ""
    txt = re.sub(r"[\u0590-\u05C7]", "", txt)        # ניקוד
    txt = re.sub(r"[^\w\s]", "", txt)                # סימנים מיוחדים
    return re.sub(r"\s+", " ", txt.lower()).strip()


def load_sheet():
    now = time.time()
    if now - _sheet_cache["ts"] < 120 and _sheet_cache["rows"]:
        return _sheet_cache["rows"]
    try:
        r = requests.get(SHEET_URL, timeout=10)
        r.raise_for_status()
        reader = csv.DictReader(r.text.splitlines())
        rows = [{
            "name": row.get("שם הגמח", "").strip(),
            "name_clean": clean_text(row.get("שם הגמח", "")),
            "ext": row.get("שלוחה להשמעה", "").strip(),
            "msg": row.get("טקסט להשמעה", "").strip(),
            "msg_clean": clean_text(row.get("טקסט להשמעה", ""))
        } for row in reader]
        _sheet_cache.update(ts=now, rows=rows)
        logging.info("Sheet ↻ %d rows", len(rows))
        return rows
    except Exception as e:
        logging.error("Sheet load error: %s", e)
        return []


def partial_match(q: str, target: str) -> bool:
    if not q or not target:
        return False
    if q in target:
        return True
    return difflib.SequenceMatcher(None, q, target).ratio() >= 0.6

# -------------------------------------------------------------
# core logic
# -------------------------------------------------------------

def handle_text(text: str):
    q = clean_text(text)
    if not q:
        return "say_api_answer=yes\rid_list_message=t-לא התקבל טקסט"

    rows = load_sheet()
    matches = []
    for row in rows:
        logging.info("🔎 checking row: name='%s', msg='%s'", row["name_clean"], row["msg_clean"])
        if partial_match(q, row["name_clean"]) or partial_match(q, row["msg_clean"]):
            matches.append(row)

    logging.info("🔍 matches found: %d", len(matches))
    for i, m in enumerate(matches):
        logging.info("📍 Match %d: %s", i + 1, m["name"])

    if not matches:
        return "say_api_answer=yes\rid_list_message=t-לא נמצא גמח מתאים"

    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        msg = m["msg"] or "אין מידע נוסף"
        return f"say_api_answer=yes\rid_list_message=t-{msg}"

    tts = "מצאתי יותר מגמח אחד:\n"
    for i, m in enumerate(matches[:5], 1):
        tts += f"{i}. {m['name']}\n"
    return f"say_api_answer=yes\rid_list_message=t-{tts}"

# -------------------------------------------------------------
# routes
# -------------------------------------------------------------

@app.route("/", methods=["POST"])
def api():
    logging.info("---- NEW POST ----")
    logging.info("Form keys: %s", list(request.form.keys()))

    if request.form.get("search_term"):
        raw = request.form.get("search_term")
        logging.info("🎤 raw text: '%s'", raw)
        return handle_text(raw)

    logging.warning("POST missing search_term")
    return "say_api_answer=yes\rid_list_message=t-לא קיבלתי נתון זיהוי"


@app.route("/", methods=["GET"])
def home():
    return "OK - gmach matcher v3"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
