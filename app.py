# app.py
from flask import Flask, render_template, request, jsonify
from twitch_extractor import extract_streams_from_url
import traceback

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/extract", methods=["POST"])
def extract():
    try:
        data = request.get_json()
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"error": "URL vacía"}), 400

        stream_list = extract_streams_from_url(url)
        return jsonify({"streams": stream_list})  # ahora es una lista

    except Exception as e:
        print("Error:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)