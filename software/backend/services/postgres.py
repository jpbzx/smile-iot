"""User / auth / audit persistence (PostgreSQL).

Ported from the retired Streamlit db/postgres_manager.py — same security
behaviour (bcrypt, failed-attempt lockout, audit log, single-use reset
tokens), rebuilt with an English schema, TIMESTAMPTZ columns and
context-managed connections.
"""

import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import bcrypt
import psycopg2
import psycopg2.errors

from backend import config


# --- Exceptions (mapped to HTTP codes in the API layer) -----------------------
class AccountLocked(Exception):
    def __init__(self, locked_until: datetime):
        self.locked_until = locked_until
        super().__init__(f"locked until {locked_until.isoformat()}")


class DuplicateUser(Exception):
    pass


class WrongPassword(Exception):
    pass


# --- Connection helper --------------------------------------------------------
@contextmanager
def get_conn():
    conn = psycopg2.connect(**config.POSTGRES)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# --- Audit --------------------------------------------------------------------
def log_login_attempt(username: str, success: bool, reason: str = "") -> None:
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO login_logs (username, success, reason) VALUES (%s, %s, %s)",
                (username, success, reason),
            )
    except Exception:
        pass  # auditing must never break the login path


def list_login_logs(limit: int = 100) -> list[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT username, success, reason, at FROM login_logs ORDER BY at DESC LIMIT %s",
            (limit,),
        )
        return [
            {"username": u, "success": s, "reason": r, "timestamp": t.isoformat()}
            for u, s, r, t in cur.fetchall()
        ]


# --- Login / lockout ----------------------------------------------------------
def verify_login(username: str, password: str) -> dict | None:
    """Returns the user dict on success, None on bad credentials.
    Raises AccountLocked while a lockout is active."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id, username, role, password_hash, failed_attempts, locked_until
               FROM users WHERE username = %s""",
            (username,),
        )
        row = cur.fetchone()

    if row is None:
        log_login_attempt(username, False, "no_such_user")
        return None

    user_id, uname, role, stored_hash, failed, locked_until = row

    if locked_until is not None and _now() < locked_until:
        log_login_attempt(username, False, "locked")
        raise AccountLocked(locked_until)

    if bcrypt.checkpw(password.encode(), stored_hash.encode()):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = %s",
                (user_id,),
            )
        log_login_attempt(username, True, "success")
        return {"id": user_id, "username": uname, "role": role}

    # Wrong password: bump the counter, maybe lock
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET failed_attempts = failed_attempts + 1 "
            "WHERE id = %s RETURNING failed_attempts",
            (user_id,),
        )
        new_count = cur.fetchone()[0]
        reason = "invalid_password"
        if new_count >= config.MAX_FAILED_ATTEMPTS:
            until = _now() + timedelta(minutes=config.LOCKOUT_MINUTES)
            cur.execute("UPDATE users SET locked_until = %s WHERE id = %s", (until, user_id))
            reason = f"locked_after_{new_count}"
    log_login_attempt(username, False, reason)
    return None


# --- Users CRUD ----------------------------------------------------------------
def get_user(user_id: int) -> dict | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, email, role FROM users WHERE id = %s", (user_id,)
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {"id": row[0], "username": row[1], "email": row[2], "role": row[3]}


def list_users() -> list[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id, username, email, role, locked_until, created_at
               FROM users ORDER BY id"""
        )
        return [
            {
                "id": i,
                "username": u,
                "email": e,
                "role": r,
                "locked_until": lu.isoformat() if lu else None,
                "created_at": ca.isoformat(),
            }
            for i, u, e, r, lu, ca in cur.fetchall()
        ]


def create_user(username: str, email: str, password: str, role: str) -> int:
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO users (username, email, password_hash, role)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (username, email, hash_password(password), role),
            )
            return cur.fetchone()[0]
    except psycopg2.errors.UniqueViolation as exc:
        raise DuplicateUser() from exc


def set_role(user_id: int, role: str) -> bool:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET role = %s WHERE id = %s", (role, user_id))
        return cur.rowcount == 1


def delete_user(user_id: int) -> bool:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        return cur.rowcount == 1


def change_password_checked(user_id: int, current_password: str, new_password: str) -> None:
    """Changes a user's own password; requires the current one. Raises WrongPassword."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if row is None or not bcrypt.checkpw(current_password.encode(), row[0].encode()):
            raise WrongPassword()
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (hash_password(new_password), user_id),
        )


# --- Password reset tokens ------------------------------------------------------
def create_reset_token(email: str, expires_minutes: int = 60) -> str | None:
    """Returns a fresh token, or None when the email is unknown
    (caller must answer neutrally either way — no user enumeration)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if row is None:
            return None
        token = secrets.token_urlsafe(32)
        cur.execute(
            """INSERT INTO password_reset_tokens (user_id, token, expires_at)
               VALUES (%s, %s, %s)""",
            (row[0], token, _now() + timedelta(minutes=expires_minutes)),
        )
        return token


def reset_password_with_token(token: str, new_password: str) -> tuple[bool, str]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT user_id, expires_at, used FROM password_reset_tokens WHERE token = %s",
            (token,),
        )
        row = cur.fetchone()
        if row is None:
            return False, "invalid_token"
        user_id, expires_at, used = row
        if used:
            return False, "token_used"
        if _now() > expires_at:
            return False, "token_expired"
        cur.execute(
            "UPDATE users SET password_hash = %s, failed_attempts = 0, locked_until = NULL "
            "WHERE id = %s",
            (hash_password(new_password), user_id),
        )
        cur.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE token = %s", (token,)
        )
        return True, "password_updated"


# --- Health -------------------------------------------------------------------
def ping() -> bool:
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone()[0] == 1
    except Exception:
        return False


# --- Schema -------------------------------------------------------------------
def init_db(seed_admin_password: str = "admin123") -> None:
    """Creates all tables (idempotent) and seeds the first admin user."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user'
                    CHECK (role IN ('admin', 'user')),
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            -- Ready for multi-board (Phase 5); unused in single-board scope
            CREATE TABLE IF NOT EXISTS devices (
                id SERIAL PRIMARY KEY,
                mac_address VARCHAR(17) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                current_limit_a NUMERIC(5,2) NOT NULL DEFAULT 15.0
            );
            CREATE TABLE IF NOT EXISTS device_access (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, device_id)
            );

            CREATE TABLE IF NOT EXISTS login_logs (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50),
                success BOOLEAN NOT NULL,
                reason TEXT,
                at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                used BOOLEAN NOT NULL DEFAULT FALSE
            );
        """)

        cur.execute("SELECT count(*) FROM users")
        if cur.fetchone()[0] == 0:
            cur.execute(
                """INSERT INTO users (username, email, password_hash, role)
                   VALUES (%s, %s, %s, %s)""",
                ("admin", "admin@smile-iot.local", hash_password(seed_admin_password), "admin"),
            )
            print(f"Seeded admin user (password: {seed_admin_password!r} — change it!)")
    print("PostgreSQL schema ready.")
