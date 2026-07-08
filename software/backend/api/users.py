"""User management (admin) + self-service password change."""

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from backend.api.helpers import admin_required, err
from backend.services import postgres

bp = Blueprint("users", __name__)


def _validate_new_user(data: dict) -> str | None:
    if len((data.get("username") or "").strip()) < 3:
        return "username must be at least 3 characters."
    if "@" not in (data.get("email") or ""):
        return "email looks invalid."
    if len(data.get("password") or "") < 5:
        return "password must be at least 5 characters."
    if data.get("role") not in ("admin", "user"):
        return "role must be 'admin' or 'user'."
    return None


@bp.get("")
@admin_required
def list_users():
    return postgres.list_users()


@bp.post("")
@admin_required
def create_user():
    data = request.get_json(silent=True) or {}
    problem = _validate_new_user(data)
    if problem:
        return err(400, "validation", problem)
    try:
        user_id = postgres.create_user(
            data["username"].strip(), data["email"].strip().lower(),
            data["password"], data["role"],
        )
    except postgres.DuplicateUser:
        return err(409, "duplicate", "Username or email already exists.")
    return {"id": user_id}, 201


@bp.patch("/<int:user_id>")
@admin_required
def patch_user(user_id: int):
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    if role not in ("admin", "user"):
        return err(400, "validation", "role must be 'admin' or 'user'.")
    if not postgres.set_role(user_id, role):
        return err(404, "not_found", "No such user.")
    return {"id": user_id, "role": role}


@bp.delete("/<int:user_id>")
@admin_required
def delete_user(user_id: int):
    if user_id == int(get_jwt_identity()):
        return err(409, "cannot_delete_self", "You cannot delete your own account.")
    if not postgres.delete_user(user_id):
        return err(404, "not_found", "No such user.")
    return "", 204


@bp.put("/me/password")
@jwt_required()
def change_my_password():
    data = request.get_json(silent=True) or {}
    current = data.get("current_password") or ""
    new = data.get("new_password") or ""
    if len(new) < 5:
        return err(400, "weak_password", "Password must be at least 5 characters.")
    try:
        postgres.change_password_checked(int(get_jwt_identity()), current, new)
    except postgres.WrongPassword:
        return err(403, "wrong_current_password", "Current password is incorrect.")
    return {"message": "password_updated"}
