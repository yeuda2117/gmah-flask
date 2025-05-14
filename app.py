"""gmach‑api v5  — simple Google‑Sheets → Yemot bridge
====================================================
▪ מקבל search_term מ‑Yemot API (זיהוי דיבור או הקשה).
▪ קורא גיליון Google (עמודות A‑C) ללא תלות בכותרות.
▪ מחפש התאמה חלקית / פאזית בשם הגמ"ח (A) או בטקסט להשמעה (C).
▪ מחזיר את הטקסט שבעמודה C כ‑TTS; אם אין התאמה – הודעה מתאימה.
▪ אין שימוש בשלוחה, אין צורך בעמודה B (שלוחה להשמעה) – תישאר ריקה או לכל שימוש עתידי.
"""

from flask import Flask, request
import os, requests, csv, re, difflib, time, logging, io

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# ----- CONFIG ----------------------------------------------------------------
SHEET_URL = (
    "https://docs.google.com/spreadsheets/"
    "d/1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"
)
CACHE_TTL = 120  # שניות – טען את הגיליון פעם בשתי דקות

# -----------------------------------------------------------------------------
app = Flask(__name__)
_sheet_cache = {"ts": 0.0, "rows": []}

# ----- helpers ----------------------------------------------------------------

def normalize(txt: str) -> str:
    """הסרת ניקוד, סימני פיסוק ורווחים כפולים → lower"""
    if not txt:
        return ""
    txt = re.sub(r"[\u0591-\u05C7]", "", txt)   # ניקוד
    txt = re.sub(r"[^\w\s]", " ", txt)          # סימנים
    return re.sub(r"\s+", " ", txt.lower()).strip()


def load_sheet():
    """טוען את הגיליון ומחזיר רשימת מילונים: name / msg / clean"""
    now = time.time()
    if now - _sheet_cache["ts"] < CACHE_TTL and _sheet_cache["rows"]:
        return _sheet_cache["rows"]
    try:
        r = requests.get(SHEET_URL, timeout=10)
        r.raise_for_status()
        # DictReader לא אמין אם אין כותרות – נשתמש ב‑reader רגיל
        reader = csv.reader(io.StringIO(r.text))
        rows = []
        for row in reader:
            if len(row) < 3:
                continue  # שורה חלקית
            name, _, msg = row[0].strip(), row[1].strip(), row[2].strip()
            if not (name or msg):
                continue
            rows.append({
                "name": name,
                "msg": msg,
                "name_clean": normalize(name),
                "msg_clean": normalize(msg),
            })
        _sheet_cache.update(ts=now, rows=rows)
        logging.info("Sheet ↻ %d rows", len(rows))
        return rows
    except Exception as e:
        logging.error("Sheet load error: %s", e)
        return []


def fuzzy_inside(q: str, target: str) -> bool:
    """האם q נמצא בתוך target (מילה שלמה) או דמיון ≥ 0.6"""
    if not q or not target:
        return False
    if q in target:
        return True
    return difflib.SequenceMatcher(None, q, target).ratio() >= 0.6


def handle_text(text: str) -> str:
    q = normalize(text)
    if not q:
        return "say_api_answer=yes\nid_list_message=t-לא התקבל טקסט לחיפוש"

    rows = load_sheet()
    matches = []
    for row in rows:
        logging.info("🔎 check: name='%s' msg='%s'", row["name_clean"], row["msg_clean"])
        if fuzzy_inside(q, row["name_clean"]) or fuzzy_inside(q, row["msg_clean"]):
            matches.append(row)

    logging.info("🔍 total matches: %d", len(matches))

    if not matches:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמ\"ח מתאים"

    if len(matches) == 1:
        msg = matches[0]["msg"] or "אין מידע נוסף"
        return f"say_api_answer=yes\nid_list_message=t-{msg}"

    # מספר תוצאות › קריאה של שמות בלבד
    tts = "נמצאו כמה גמחים:\n" + "\n".join(
        f"{i+1}. {m['name']}" for i, m in enumerate(matches[:5])
    )
    return f"say_api_answer=yes\nid_list_message=t-{tts}"

# ----- routes -----------------------------------------------------------------

@app.route("/", methods=["POST"])
def api():
    if not request.form:
        return "say_api_answer=yes\nid_list_message=t-בקשה לא תקינה"
    text = request.form.get("search_term", "")
    logging.info("🎤 raw text: '%s'", text)
    return handle_text(text)


@app.route("/")
def home():
    return "OK – gmach‑api v5"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
