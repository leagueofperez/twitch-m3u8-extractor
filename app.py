# app.py
import re

from flask import Flask, jsonify, render_template, request

from twitch_extractor import TwitchError, extract_streams_from_url

app = Flask(__name__)

SENSITIVE = re.compile(
    r"(token|sig|nauth|nauthsig|client_id)=[^&\s\"']+", re.IGNORECASE
)
URL_RE = re.compile(r"https?://\S+")


def sanitize_error(message):
    clean = SENSITIVE.sub(r"\1=REDACTED", message)
    return URL_RE.sub("[redactado]", clean)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/extract", methods=["POST"])
def extract():
    try:
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify({"error": "URL vacía"}), 400

        stream_list = extract_streams_from_url(url)
        return jsonify({"streams": stream_list})

    except TwitchError as exc:
        return jsonify({"error": sanitize_error(str(exc))}), 400

    except Exception as exc:
        app.logger.exception("Error no controlado en /extract")
        return jsonify({"error": sanitize_error(f"{exc.__class__.__name__}: {exc}")}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)