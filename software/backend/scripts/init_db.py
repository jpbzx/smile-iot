"""One-time PostgreSQL bootstrap: schema + seed admin.

Run (from software/):  python -m backend.scripts.init_db
Idempotent — safe to re-run.
"""

from backend.services import postgres

if __name__ == "__main__":
    postgres.init_db()
