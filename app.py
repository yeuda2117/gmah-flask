from flask import Flask, request, Response
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route("/", methods=["POST"])
def api():
    # קח את ה־search_term מהבקשה
    text = request.form.get("search_term", "")
    logging.info(f"🎤 raw text: '{text}'")

    # תחזיר תמיד טקסט פשוט לבדיקה
    # אם זה עובד, תדע שהבעיה בקידוד (או בתוכן!)
    response_text = "say_api_answer=yes\nid_list_message=t-שלום! זה בדיקת טקסט בעברית בלבד."

    # החזרה בקידוד windows-1255 כפי שדורש ימות המשיח
    return Response("say_api_answer=yes\nid_list_message=t-בדיקה עברית".encode("windows-1255"), content_type="text/plain; charset=windows-1255")



@app.route("/", methods=["GET"])
def home():
    return "OK"

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
