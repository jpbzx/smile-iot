"""Auth endpoints: login, identity, password reset (request + confirm)."""

import logging
import time

from flask import Blueprint, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from backend.api.helpers import err
from backend.services import emailer, postgres

log = logging.getLogger(__name__)

bp = Blueprint("auth", __name__)

# Per-email cooldown for reset requests (in-memory is fine: single process,
# and losing it on restart only shortens the cooldown).
_last_reset_request: dict[str, float] = {}
RESET_COOLDOWN_S = 60


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return err(400, "validation", "username and password are required.")

    try:
        user = postgres.verify_login(username, password)
    except postgres.AccountLocked as exc:
        return err(
            423, "account_locked",
            "Account temporarily locked after repeated failures.",
            locked_until=exc.locked_until.isoformat(),
        )

    if user is None:
        return err(401, "invalid_credentials", "Invalid credentials.")

    token = create_access_token(
        identity=str(user["id"]),
        additional_claims={"role": user["role"], "username": user["username"]},
    )
    return {"access_token": token, "user": user}


@bp.get("/me")
@jwt_required()
def me():
    user = postgres.get_user(int(get_jwt_identity()))
    if user is None:
        return err(401, "unknown_user", "Token subject no longer exists.")
    return user


@bp.post("/password-reset/request")
def password_reset_request():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return err(400, "validation", "email is required.")

    now = time.time()
    if now - _last_reset_request.get(email, 0) < RESET_COOLDOWN_S:
        return err(429, "too_many_requests", "Wait before requesting another reset email.")
    _last_reset_request[email] = now

    token = postgres.create_reset_token(email)
    if token is not None:
        sent, send_err = emailer.send_password_reset_email(email, token)
        if not sent:
            # Dev convenience: with SMTP disabled the token only exists here.
            log.warning("Reset email not sent (%s); token for %s: %s", send_err, email, token)

    # Identical response whether or not the email exists — no enumeration.
    return {"message": "If the email exists, a reset link has been sent."}, 202


@bp.post("/password-reset/confirm")
def password_reset_confirm():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    new_password = data.get("new_password") or ""
    if not token or not new_password:
        return err(400, "validation", "token and new_password are required.")
    if len(new_password) < 5:
        return err(400, "weak_password", "Password must be at least 5 characters.")

    ok, reason = postgres.reset_password_with_token(token, new_password)
    if not ok:
        return err(400, reason, "Reset failed: " + reason.replace("_", " ") + ".")
    return {"message": "password_updated"}
