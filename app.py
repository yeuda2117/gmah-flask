from flask import Flask, request, Response

app = Flask(__name__)

@app.route("/", methods=["POST"])
def api():
    text = request.form.get("search_term", "")
    response_text = "say_api_answer=yes\nid_list_message=t-בדיקה בעברית"
    return Response(response_text.encode("windows-1255"), content_type="text/plain; charset=windows-1255")

@app.route("/", methods=["GET"])
def home():
    return "OK"
