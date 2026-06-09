"""Flask application factory.

Serves the React single-page app (built into ``app/webui``) and the JSON API
(``app/api.py``) consumed by it. Update scanning/scheduling/email all run in the
existing backend (db, scanner, scheduler, emailer); this module only wires the
HTTP surface together.
"""
import functools
import os

from flask import (Flask, Response, jsonify, request, send_from_directory)

from . import db, reports, scheduler
from .api import api as api_blueprint
from .config import config

WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")


def _check_basic_auth() -> bool:
    if not config.DASHBOARD_USER:
        return True
    auth = request.authorization
    return bool(
        auth
        and auth.username == config.DASHBOARD_USER
        and auth.password == config.DASHBOARD_PASSWORD
    )


def _auth_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not _check_basic_auth():
            return Response(
                "Authentication required.", 401,
                {"WWW-Authenticate": 'Basic realm="WP Updater"'},
            )
        return view(*args, **kwargs)
    return wrapped


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.secret_key = config.SECRET_KEY

    db.init_db()
    db.seed_settings_if_empty()
    scheduler.start()

    # Protect the JSON API with the same optional basic auth.
    @api_blueprint.before_request
    def _guard_api():
        if not _check_basic_auth():
            return Response(
                "Authentication required.", 401,
                {"WWW-Authenticate": 'Basic realm="WP Updater"'},
            )
        return None

    app.register_blueprint(api_blueprint)

    # ------------------------------------------------------------- reports
    @app.route("/report.html")
    @_auth_required
    def report_html():
        return Response(reports.build_html(), mimetype="text/html")

    @app.route("/report.md")
    @_auth_required
    def report_md():
        return Response(
            reports.build_markdown(),
            mimetype="text/markdown",
            headers={"Content-Disposition": "attachment; filename=wp-update-report.md"},
        )

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    # ----------------------------------------------------------- SPA serving
    @app.route("/")
    @_auth_required
    def spa_index():
        return send_from_directory(WEBUI_DIR, "index.html")

    @app.route("/<path:path>")
    @_auth_required
    def spa_assets(path):
        full = os.path.join(WEBUI_DIR, path)
        if os.path.isfile(full):
            return send_from_directory(WEBUI_DIR, path)
        # Unknown path -> let the SPA's internal router handle it.
        return send_from_directory(WEBUI_DIR, "index.html")

    return app
