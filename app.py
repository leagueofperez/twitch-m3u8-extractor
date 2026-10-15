# app.py
import os
import re

from flask import Flask, jsonify, render_template, request

import shortener
from shortener import ShortenerError
from twitch_extractor import (
    TwitchError,
    extract_streams_from_url,
    parse_twitch_url,
)

app = Flask(__name__)

SENSITIVE = re.compile(
    r"(token|sig|nauth|nauthsig|client_id)=[^&\s\"']+", re.IGNORECASE
)
URL_RE = re.compile(r"https?://\S+")


def site_url():
    """Raíz absoluta del sitio para canonical, og:url, manifest y JSON-LD.

    Prioriza PUBLIC_URL y si no está definida la deduce de la petición, de
    forma que los meta tags son correctos sin configurar nada en local ni
    detrás de un proxy. PUBLIC_URL conviene fijarla en producción: detrás
    de un reverse proxy, url_root puede devolver el esquema o el host
    interno en vez del público.
    """
    configured = (os.environ.get("PUBLIC_URL") or "").strip()
    return (configured or request.url_root).rstrip("/")


@app.context_processor
def inject_site_url():
    return {"site_url": site_url(), "shortener_enabled": shortener.is_enabled()}


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

        is_live, target = parse_twitch_url(url)
        stream_list = extract_streams_from_url(url)

        # Cada URL viaja firmada junto a su slug y titulo. La firma es lo que
        # permite a /shorten aceptar el enlace sin guardar nada en memoria: da
        # igual en que worker caiga cada peticion porque no hay estado que
        # compartir entre ellos.
        if shortener.is_enabled():
            for stream in stream_list:
                quality = stream["quality"]
                stream["shorten"] = shortener.issue(
                    stream["url"],
                    shortener.slug_for(is_live, target, quality),
                    shortener.title_for(is_live, target, quality),
                )

        return jsonify({"streams": stream_list})

    except TwitchError as exc:
        return jsonify({"error": sanitize_error(str(exc))}), 400

    except Exception as exc:
        app.logger.exception("Error no controlado en /extract")
        return jsonify({"error": sanitize_error(f"{exc.__class__.__name__}: {exc}")}), 500


@app.route("/shorten", methods=["POST"])
def shorten():
    if not shortener.is_enabled():
        return jsonify({"error": "El acortado no está configurado en este servidor."}), 503

    if shortener.rate_limited(request.remote_addr or "desconocida"):
        return jsonify({"error": "Demasiadas peticiones. Espera un minuto."}), 429

    try:
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify({"error": "URL vacía"}), 400

        return jsonify(
            shortener.shorten(
                url,
                data.get("slug") or "",
                data.get("title") or "",
                data.get("ts"),
                data.get("sig"),
            )
        )

    except ShortenerError as exc:
        return jsonify({"error": sanitize_error(str(exc))}), exc.status

    except Exception as exc:
        app.logger.exception("Error no controlado en /shorten")
        return jsonify({"error": sanitize_error(f"{exc.__class__.__name__}: {exc}")}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)