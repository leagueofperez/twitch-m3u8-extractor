# app.py
from flask import Flask, request

import shortener
from config import Config
from routes.api import api
from routes.pages import pages


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config.update(config or {})

    @app.context_processor
    def inject_site_url():
        configured = (app.config["PUBLIC_URL"] or "").strip()
        return {
            "site_url": (configured or request.url_root).rstrip("/"),
            "shortener_enabled": shortener.is_enabled(),
        }

    app.register_blueprint(pages)
    app.register_blueprint(api)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"], host="0.0.0.0", port=5000)