from flask import Flask, request
import requests
import csv

app = Flask(__name__)

def get_gmahim():
    url = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv"
    response = requests.get(url)
    lines = response.text.splitlines()
    reader = csv.DictReader(lines)
    gmahim = {}
    for row in reader:
        gmahim[row['שם הגמח']] = row['שלוחה']
    return gmahim

@app.route("/", methods=["POST"])
def handle_api():
    voice_text = request.form.get("search_term", "")
    gmahim = get_gmahim()

    for name, ext in gmahim.items():
        if name in voice_text:
            return f"go_to_folder=/{ext}"
    return "say_api_answer=yes\nid_list_message=t-גמ\"ח לא נמצא"

@app.route("/", methods=["GET"])
def home():
    return "המערכת פועלת תקין 🚀"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)