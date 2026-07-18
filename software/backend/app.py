"""SMILE-IoT Flask API.

Run (dev):   python -m backend.app          (from software/)
The ingest worker is a separate process:    python -m backend.ingest.worker
"""

import logging
from datetime import timedelta

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from backend import config
from backend.api import auth, control, system, telemetry, users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def create_app() -> Flask:
    if not config.JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not set — copy .env.example to .env and fill it.")

    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = config.JWT_SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=config.SESSION_TIMEOUT_MIN)

    jwt = JWTManager(app)
    CORS(app, origins=["http://localhost:5173"])  # Vite dev server; proxy makes this mostly moot

    # Uniform error payloads, including for JWT failures
    @jwt.unauthorized_loader
    def _missing_token(reason):
        return jsonify(error="unauthorized", message=reason), 401

    @jwt.invalid_token_loader
    def _invalid_token(reason):
        return jsonify(error="invalid_token", message=reason), 401

    @jwt.expired_token_loader
    def _expired_token(_header, _payload):
        return jsonify(error="token_expired", message="Session expired, login again."), 401

    @app.errorhandler(404)
    def _not_found(_):
        return jsonify(error="not_found", message="No such endpoint."), 404

    @app.errorhandler(405)
    def _bad_method(_):
        return jsonify(error="method_not_allowed", message="Wrong HTTP method."), 405

    @app.errorhandler(500)
    def _boom(exc):
        logging.getLogger(__name__).exception("Unhandled error: %s", exc)
        return jsonify(error="internal", message="Internal server error."), 500

    app.register_blueprint(system.bp, url_prefix="/api")
    app.register_blueprint(auth.bp, url_prefix="/api/auth")
    app.register_blueprint(users.bp, url_prefix="/api/users")
    app.register_blueprint(telemetry.bp, url_prefix="/api/telemetry")
    app.register_blueprint(control.bp, url_prefix="/api/control")
    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
