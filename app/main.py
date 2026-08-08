from __future__ import annotations

import logging
import threading

import numpy as np
from flask import Flask
from flask.json.provider import DefaultJSONProvider

from app.api.routes import api, warm_caches
from app.data.database import initialize_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


class ApiJSONProvider(DefaultJSONProvider):
    """JSON encoder that safely converts numpy scalars/arrays produced by pandas."""

    def default(self, o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.bool_):
            return bool(o)
        return super().default(o)


def create_app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.json = ApiJSONProvider(flask_app)
    flask_app.json.sort_keys = False
    flask_app.register_blueprint(api, url_prefix="/api")
    with flask_app.app_context():
        initialize_database()
    _warm_thread = threading.Thread(target=warm_caches, name="cache-warm", daemon=True)
    _warm_thread.start()
    return flask_app


app = create_app()
