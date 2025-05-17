"""gmach‑api v7 — Google‑Sheets → Yemot
=================================================
* קורא גיליון Google ב‑CSV ומזהה עמודות לפי כותרות—even if כוללות תו BOM.
* עמודה **שם הגמח** (A) ו‑**טקסט להשמעה** (C).
* חיפוש fuzzy ומשיב את הטקסט כ‑TTS.
"""

from flask import Flask, request
import os, requests, csv, re, difflib, time, logging, io

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# ----- CONFIG --------------------------------------------------------------
SHEET_URL = (
    "https://docs.google.com/spreadsheets/"
    "d/1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"
)
CACHE_TTL = 120  # seconds

# --------------------------------------------------------------------------
app = Flask(__name__)
_sheet_cache = {"ts": 0.0, "rows": []}

# ----- helpers -------------------------------------------------------------

def normalize(txt: str) -> str:
    """Remove Nikud, punctuation, excessive spaces; lower‑case."""
    if not txt:
        return ""
    txt = re.sub(r"[\u0591-\u05C7]", "", txt)   # ניקוד
    txt = re.sub(r"[^\w\s]", " ", txt)
    return re.sub(r"\s+", " ", txt.lower()).strip()


def load_sheet():
    """Download sheet, cache, return list of dicts with cleaned fields."""
    now = time.time()
    if now - _sheet_cache["ts"] < CACHE_TTL and _sheet_cache["rows"]:
        return _sheet_cache["rows"]
    try:
        r = requests.get(SHEET_URL, timeout=10)
        r.raise_for_status()
        f = io.StringIO(r.content.decode("utf-8-sig"))  # ✨ strip BOM if קיימת
        raw_reader = csv.reader(f)
        headers = [h.strip() for h in next(raw_reader)]
        headers = [h.replace("\ufeff", "") for h in headers]
        # build DictReader manually so we can clean headers
        rows = []
        for raw in raw_reader:
            row = dict(zip(headers, raw))
            # try locating columns even if השמות מעט שונים
            name = row.get("שם הגמח") or row.get("שם") or row.get("הגמח") or ""
            msg = row.get("טקסט להשמעה") or row.get("טקסט") or ""
            name, msg = name.strip(), msg.strip()
            if not (name or msg):
                continue
            rows.append({
                "name": name,
                "msg": msg,
                "name_clean": normalize(name),
                "msg_clean": normalize(msg)
            })
        _sheet_cache.update(ts=now, rows=rows)
        logging.info("Sheet ↻ %d rows", len(rows))
        return rows
    except Exception as e:
        logging.error("Sheet load error: %s", e)
        return []


def fuzzy_match(q: str, target: str) -> bool:
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
        if fuzzy_match(q, row["name_clean"]) or fuzzy_match(q, row["msg_clean"]):
            matches.append(row)
    logging.info("🔍 total matches: %d", len(matches))

    if not matches:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמ\"ח מתאים"

    if len(matches) == 1:
        return f"say_api_answer=yes\nid_list_message=t-{matches[0]['msg'] or 'אין מידע נוסף'}"

    # multiple matches → רשימה
    tts = "נמצאו כמה גמחים:\n" + "\n".join(
        f"{i+1}. {m['name']}" for i, m in enumerate(matches[:5])
    )
    return f"say_api_answer=yes\nid_list_message=t-{tts}"

# ----- routes --------------------------------------------------------------

@app.route("/", methods=["POST"])
def api():
    text = request.form.get("search_term", "")
    logging.info("🎤 raw text: '%s'", text)
    resp = handle_text(text)
    logging.info("⤴️  response to Yemot: %s", resp.encode('utf-8'))
    return resp


@app.route("/")
def home():
    return "OK – gmach‑api v7"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
