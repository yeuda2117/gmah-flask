#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gmach-api v8 — Yemot ► Google-Sheet
© 2025 — (ניסיוני)
"""

# ---------------------------------------------------
# imports
# ---------------------------------------------------
import os, time, logging, csv, re, difflib
import requests
from flask import Flask, request

# ---------------------------------------------------
# logging בסיסי
# ---------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ---------------------------------------------------
# קבועים
# ---------------------------------------------------
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"
)

# ---------------------------------------------------
# APP
# ---------------------------------------------------
app = Flask(__name__)

# ---------------------------------------------------
# ➊ ניקוי טקסט בסיסי
# ---------------------------------------------------
_hebrew_nrml = re.compile(r"[^\u0590-\u05FFa-z0-9 ]")
def clean_txt(txt: str) -> str:
    """
    מנקה: ניקוד, סימני פיסוק, רווחים כפולים → מחזיר lower-case.
    """
    if not txt:
        return ""
    txt = txt.lower()
    txt = _hebrew_nrml.sub(" ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

# ---------------------------------------------------
# ➋ אלגוריתם התאמה סלחני
# ---------------------------------------------------
def good_match(q: str, rec: str) -> bool:
    """
    true ↔  q תת-מחרוזת rec או דמיון ≥ 0.7 (70 %).
    """
    q, rec = clean_txt(q), clean_txt(rec)
    if not q or not rec:
        return False
    if q in rec:
        return True
    return difflib.SequenceMatcher(None, q, rec).ratio() >= 0.70

# ---------------------------------------------------
# ➌ טעינת גיליון עם Cache
# ---------------------------------------------------
_sheet_cache = {"t": 0.0, "rows": []}

def load_sheet():
    now = time.time()
    if now - _sheet_cache["t"] < 120 and _sheet_cache["rows"]:
        return _sheet_cache["rows"]

    try:
        resp = requests.get(SHEET_URL, timeout=10)
        resp.raise_for_status()
        rows = []
        reader = csv.DictReader(resp.text.splitlines())
        for r in reader:
            name = (r.get("שם הגמח") or "").strip()
            msg  = (r.get("טקסט להשמעה") or "").strip()
            ext  = (r.get("שלוחה להשמעה") or "").strip()  # עשוי להיות ריק
            rows.append(
                {
                    "name": name,
                    "msg":  msg,
                    "ext":  ext,
                }
            )
        _sheet_cache.update({"t": now, "rows": rows})
        logging.info("Sheet ↻ %d rows", len(rows))
        return rows
    except Exception as e:
        logging.error("Sheet load error: %s", e)
        return []

# ---------------------------------------------------
# ➍ לוגיקת התאמה ובניית תשובה
# ---------------------------------------------------
def handle_text(text: str) -> str:
    q = clean_txt(text)
    if not q:
        return "say_api_answer=yes\nid_list_message=t-לא התקבל טקסט ?״"

    matches = []
    for row in load_sheet():
        if good_match(q, row["name"]) or good_match(q, row["msg"]):
            matches.append(row)

    logging.info("🔍 total matches: %d", len(matches))

    # -- לא נמצא
    if not matches:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמ\"ח מתאים"

    # -- התאמה יחידה
    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        msg = m["msg"] or "אין מידע נוסף"
        return f"say_api_answer=yes\nid_list_message=t-{msg}"

    # -- כמה התאמות → רשימה קצרה
    tts = "מצאתי כמה גמחים:\n"
    for i, m in enumerate(matches[:5], 1):
        tts += f"{i}. {m['name']}\n"
    return f"say_api_answer=yes\nid_list_message=t-{tts}"

# ---------------------------------------------------
# ➎ Route יחיד POST ← Yemot
# ---------------------------------------------------
@app.route("/", methods=["POST"])
def api():
    text = request.form.get("search_term", "")
    logging.info("🎤 raw text: '%s'", text)

    resp = handle_text(text)

    logging.info("⤴️  response to Yemot: %s", resp.encode("utf-8"))
    return resp


# בריאות
@app.route("/")
def home():
    return "OK – gmach-api v8"

# ---------------------------------------------------
# main (local run)
# ---------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
