#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gmah-api v8
===========

* מחובר ל-Yemot כ-API (POST).
* מקבל search_term (טקסט שהמערכת זיהתה בדיבור).
* מחפש בגיליון Google Sheets ומשיב:
    – go_to_folder=/<ext>  אם קיימת שלוחה ייעודית
    – id_list_message=t-<טקסט>  אם יש הודעה
    – הודעת “לא נמצא” אם אין התאמות.

הקובץ עצמאי – אין צורך בספריות חיצוניות מעבר ל-requests ו-Flask.
"""

from flask import Flask, request
import requests, csv, time, logging, re, unicodedata
from pathlib import Path

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"
)
CACHE_TTL = 120  # שניות

# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
_sheet_cache = {"time": 0.0, "rows": []}


def load_sheet():
    """טוען את הגיליון (עם קאש)."""
    now = time.time()
    if now - _sheet_cache["time"] < CACHE_TTL and _sheet_cache["rows"]:
        return _sheet_cache["rows"]

    try:
        r = requests.get(SHEET_URL, timeout=10)
        r.raise_for_status()
        reader = csv.DictReader(r.text.splitlines())
        rows = []
        for row in reader:
            rows.append(
                {
                    "name": row.get("שם הגמח", "").strip(),
                    "ext": row.get("שלוחה להשמעה", "").strip(),
                    "msg": row.get("טקסט להשמעה", "").strip(),
                }
            )
        _sheet_cache["rows"] = rows
        _sheet_cache["time"] = now
        logging.info("Sheet ↻ %d rows", len(rows))
        return rows
    except Exception as err:
        logging.error("❌ sheet load error: %s", err)
        return []


def clean_text(s: str) -> str:
    """Normalize Hebrew: lowercase, remove נִיקּוּד, סימני פיסוק ורווחים כפולים."""
    s = s.lower()
    # הסרת ניקוד
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if not unicodedata.combining(ch))
    # הסרת תווים לא רלוונטיים
    s = re.sub(r"[^\w\s]", " ", s)
    # רווחים מיותרים
    return re.sub(r"\s+", " ", s).strip()


def partial_match(q: str, txt: str) -> bool:
    """האם כל אחת מהמילים ב-q מופיעה ב-txt (התאמה רופפת)."""
    q_words = q.split()
    return all(w in txt for w in q_words)


def handle_text(text: str) -> str:
    """מקבל טקסט, מחפש בגיליון ומחזיר מחרוזת תשובה ל-Yemot."""
    q = clean_text(text)
    if not q:
        return "say_api_answer=yes\nid_list_message=t-לא התקבל טקסט"

    rows = load_sheet()
    matches = []

    for row in rows:
        name_clean = clean_text(row["name"])
        msg_clean = clean_text(row["msg"])
        if partial_match(q, name_clean) or partial_match(q, msg_clean):
            matches.append(row)

    logging.info("🔍 total matches: %d", len(matches))

    # ---- ללא התאמות ----
    if not matches:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמח מתאים"

    # ---- התאמה יחידה ----
    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        msg = m["msg"] or "אין מידע נוסף"
        return f"say_api_answer=yes\nid_list_message=t-{msg}"

    # ---- כמה התאמות – מחזיר רשימה קולית ----
    tts = "מצאתי כמה גמחים:\n"
    for i, m in enumerate(matches[:5], 1):
        tts += f"{i}. {m['name']}\n"
    return f"say_api_answer=yes\nid_list_message=t-{tts}"


# ------------------------------------------------------------
# FLASK
# ------------------------------------------------------------
app = Flask(__name__)


@app.route("/", methods=["POST"])
def api():
    text = request.form.get("search_term", "").strip()
    logging.info("🎤 raw text: '%s'", text)

    resp = handle_text(text)
    logging.info("⤴️  response to Yemot: %s", resp.encode("utf-8"))
    return resp


@app.route("/")
def home():
    return "OK – gmah-api v8"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
