from flask import Flask, request, Response

app = Flask(__name__)

@app.route("/", methods=["POST"])
def api():
    # להוציא טקסט שהגיע מהקלטה (סתם בשביל הדגמה)
    text = request.form.get("search_term", "")

    # תשובה לבדיקה בעברית
    response_text = "say_api_answer=yes\nid_list_message=t-בדיקה בעברית\n"
    # או נסה עם אנגלית
    # response_text = "say_api_answer=yes\nid_list_message=t-Test only\n"

    # חובה! להחזיר כ- windows-1255
    return Response(response_text.encode("windows-1255"), content_type="text/plain; charset=windows-1255")

@app.route("/", methods=["GET"])
def home():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
