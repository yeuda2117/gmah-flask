#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gmah-api v8  (fixed import os)
"""
from flask import Flask, request
import os, requests, csv, time, logging, re, unicodedata   # ← נוספו os ו-unicodedata

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"
)
CACHE_TTL = 120  # seconds

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


def clean_txt(t: str) -> str:
    t = t.lower()
    t = "".join(ch for ch in unicodedata.normalize("NFD", t)
                if not unicodedata.combining(ch))          # remove nikud
    t = re.sub(r"[^\w\s]", " ", t)                         # punctuation
    return re.sub(r"\s+", " ", t).strip()


def load_sheet():
    now = time.time()
    if now - _sheet_cache["time"] < CACHE_TTL and _sheet_cache["rows"]:
        return _sheet_cache["rows"]
    try:
        r = requests.get(SHEET_URL, timeout=10)
        r.raise_for_status()
        rows = []
        for row in csv.DictReader(r.text.splitlines()):
            rows.append(
                {
                    "name": row.get("שם הגמח", "").strip(),
                    "ext": row.get("שלוחה להשמעה", "").strip(),
                    "msg": row.get("טקסט להשמעה", "").strip(),
                }
            )
        _sheet_cache.update(time=now, rows=rows)
        logging.info("Sheet ↻ %d rows", len(rows))
        return rows
    except Exception as err:
        logging.error("❌ sheet load error: %s", err)
        return []


def partial_match(q: str, rec: str) -> bool:
    q_words = q.split()
    rec = clean_txt(rec)
    return all(w in rec for w in q_words)


def handle_text(text: str) -> str:
    q = clean_txt(text)
    if not q:
        return "say_api_answer=yes\nid_list_message=t-לא התקבל טקסט"

    matches = []
    for row in load_sheet():
        if partial_match(q, row["name"]) or partial_match(q, row["msg"]):
            matches.append(row)

    logging.info("🔍 total matches: %d", len(matches))

    if not matches:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמח מתאים"

    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        msg = m["msg"] or "אין מידע נוסף"
        return f"say_api_answer=yes\nid_list_message=t-{msg}"

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
    return "OK – gmach-api v8"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
