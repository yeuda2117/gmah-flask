from flask import Flask, request
import requests
import csv
import os

app = Flask(__name__)

def get_gmahim():
    url = "https://docs.google.com/spreadsheets/d/1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"
    try:
        response = requests.get(url)
        response.raise_for_status()
        lines = response.text.splitlines()
        reader = csv.DictReader(lines)
        gmahim = []
        for row in reader:
            gmahim.append({
                "name": row.get("שם הגמח", ""),
                "ext": row.get("שלוחה להשמעה", ""),
                "message": row.get("טקסט להשמעה", "")
            })
        return gmahim
    except Exception as e:
        print("שגיאה בקריאת גיליון:", e)
        return []

@app.route("/", methods=["POST"])
def handle_api():
    print("POST DATA:", request.form)
    voice_text = request.form.get("search_term", "").lower()
    print("זוהה טקסט:", voice_text)

    if not voice_text:
        return "say_api_answer=yes\nid_list_message=t-לא קיבלתי טקסט לזיהוי"

    gmahim = get_gmahim()
    matches = []

    for gmah in gmahim:
        # בדיקה לפי עמודה A (שם הגמח)
        name_score = sum(1 for word in gmah["name"].lower().split() if word in voice_text)

        # בדיקה לפי עמודה C (הטקסט להשמעה)
        message_score = sum(1 for word in voice_text.split() if word in gmah["message"].lower())

        if name_score >= 1 or message_score >= 1:
            matches.append(gmah)

    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        elif m["message"]:
            return f"say_api_answer=yes\nid_list_message=t-{m['message']}"
        else:
            return "say_api_answer=yes\nid_list_message=t-גמ\"ח נמצא אך אין שלוחה או טקסט"
    elif len(matches) > 1:
        tts = "מצאתי מספר גמחים:\n"
        for i, m in enumerate(matches[:5], 1):
            tts += f"{i}. {m['name']}\n"
        return f"say_api_answer=yes\nid_list_message=t-{tts}"
    else:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמ\"ח מתאים"

@app.route("/", methods=["GET"])
def home():
    return "המערכת פועלת תקין 🚀"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)