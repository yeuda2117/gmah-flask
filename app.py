#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gmach-api v9  –  resilient header mapping & safe output
"""

import os, csv, time, re, logging, difflib
from flask import Flask, request
import requests
_sheet_cache = {"time": 0, "rows": []}

# --------------------------------------------------
# logging
# --------------------------------------------------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# --------------------------------------------------
# constants
# --------------------------------------------------
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"
)
CACHE_TTL = 120

# --------------------------------------------------
# helpers
# --------------------------------------------------
_bad_out = '"\r\n'
def safe(t: str) -> str:
    for ch in _bad_out:
        t = t.replace(ch, "")
    return t.strip()

_rx = re.compile(r"[^\w\u0590-\u05fe ]", re.UNICODE)
def clean(s: str) -> str:
    if not s:
        return ""
    return _rx.sub(" ", s.lower()).replace("  ", " ").strip()

def fuzzy(q: str, rec: str) -> bool:
    q = clean(q); rec = clean(rec)
    if not q or not rec:
        return False
    if q in rec:
        return True
    return difflib.SequenceMatcher(None, q, rec).ratio() >= 0.7

# --------------------------------------------------
# sheet cache
# --------------------------------------------------
_cache = {"t": 0.0, "rows": []}

def map_header(name: str) -> str:
    """נורמליזציה של כותרת – להקל בטעויות רווח/BOM/תרגום."""
    name = name.strip().lower().replace("\ufeff", "")
    ix = {
        "שם הגמח": "name",
        "name": "name",
        "שלוחה להשמעה": "ext",
        "ext": "ext",
        "טקסט להשמעה": "msg",
        "msg": "msg",
    }
    return ix.get(name, "")

import io  # בתחילת הקובץ, אם לא מופיע

def load_sheet():
    now = time.time()
    if now - _sheet_cache["time"] < 120 and _sheet_cache["rows"]:
        return _sheet_cache["rows"]
    try:
        resp = requests.get(SHEET_URL, timeout=10)
        resp.raise_for_status()
        # השורה החשובה – שימוש ב־io.StringIO ודקדוד UTF-8
        reader = csv.DictReader(io.StringIO(resp.content.decode('utf-8')))
        rows = []
        for r in reader:
            rows.append({
                "name": r.get("שם הגמח", "").strip(),
                "ext": r.get("שלוחה להשמעה", "").strip(),
                "msg": r.get("טקסט להשמעה", "").strip()
            })
        _sheet_cache["rows"] = rows
        _sheet_cache["time"] = now
        logging.info("Sheet loaded %d rows", len(rows))
        return rows
    except Exception as e:
        logging.error("Sheet load error: %s", e)
        return []


    rows = []
    try:
        r = requests.get(SHEET_URL, timeout=10)
        r.raise_for_status()
        rdr = csv.DictReader(r.text.splitlines())
        # build mapping dict: {orig_col: std_key}
        colmap = {col: map_header(col) for col in rdr.fieldnames}
        logging.info("🗝️  sheet columns: %s", colmap)

        first = None
        for raw in rdr:
            if first is None:
                first = raw
                logging.info("🧪 first row: %s", first)
            rows.append({
                "name": raw.get(next((k for k,v in colmap.items() if v=="name"), ""), "").strip(),
                "ext" : raw.get(next((k for k,v in colmap.items() if v=="ext"),  ""), "").strip(),
                "msg" : raw.get(next((k for k,v in colmap.items() if v=="msg"),  ""), "").strip(),
            })
        _cache.update(t=time.time(), rows=rows)
        logging.info("Sheet ↻ %d rows", len(rows))
    except Exception as e:
        logging.error("❌ sheet load error: %s", e)
    return rows

# --------------------------------------------------
# core
# --------------------------------------------------
def handle(text: str) -> str:
    q = clean(text)
    if not q:
        return "say_api_answer=yes\nid_list_message=t-" + safe("לא התקבל טקסט")

    matches = []
    for row in load_sheet():
        if fuzzy(q, row["name"]) or fuzzy(q, row["msg"]):
            matches.append(row)

    logging.info("🔍 total matches: %d", len(matches))

    if not matches:
        return "say_api_answer=yes\nid_list_message=t-" + safe("לא נמצא גמח מתאים")

    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{safe(m['ext'])}"
        return "say_api_answer=yes\nid_list_message=t-" + safe(m["msg"] or "אין מידע נוסף")

    tts = "מצאתי כמה גמחים:\n" + "\n".join(
        f"{i+1}. {m['name']}" for i, m in enumerate(matches[:5])
    )
    return "say_api_answer=yes\nid_list_message=t-" + safe(tts)

# --------------------------------------------------
# flask
# --------------------------------------------------
app = Flask(__name__)

@app.route("/", methods=["POST"])
def api():
    text = request.form.get("search_term", "")
    logging.info("🎤 raw text: '%s'", text)
    resp = handle(text)
    logging.info("⤴️  response: %s", resp.encode("utf-8"))
    return "say_api_answer=yes\nid_list_message=t-Test only\n"


@app.route("/")
def home():
    return "OK – gmach-api v9"

# --------------------------------------------------
# run
# --------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
