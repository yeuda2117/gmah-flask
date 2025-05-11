from flask import Flask, request
import requests
import csv

app = Flask(__name__)

def get_gmahim():
    url = "https://docs.google.com/spreadsheets/d/1jK7RsgJzi26JqBd40rqwzgldm9HKeGAp6Z4_8sR524U/export?format=csv"
    response = requests.get(url)
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

@app.route("/", methods=["POST"])
def handle_api():
    voice_text = request.form.get("search_term", "").lower()
    if not voice_text:
        return "say_api_answer=yes\nid_list_message=t-לא קיבלתי טקסט לזיהוי"

    gmahim = get_gmahim()
    matches = []

    for gmah in gmahim:
        gmah_words = gmah["name"].lower().split()
        score = sum(1 for word in gmah_words if word in voice_text)
        if score >= 2:  # מצריך לפחות 2 מילים תואמות
            matches.append(gmah)

    if len(matches) == 1:
        m = matches[0]
        if m["ext"]:
            return f"go_to_folder=/{m['ext']}"
        elif m["message"]:
            return f"say_api_answer=yes\nid_list_message=t-{m['message']}"
        else:
            return "say_api_answer=yes\nid_list_message=t-גמ"ח נמצא אך אין שלוחה או טקסט"
    elif len(matches) > 1:
        tts = "מצאתי מספר גמחים:\n"
        for i, m in enumerate(matches[:5], 1):
            tts += f"{i}. {m['name']}\n"
        return f"say_api_answer=yes\nid_list_message=t-{tts}"
    else:
        return "say_api_answer=yes\nid_list_message=t-לא נמצא גמ"ח מתאים"

@app.route("/", methods=["GET"])
def home():
    return "המערכת פועלת תקין 🚀"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)