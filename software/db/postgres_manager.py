import os
import psycopg2
import bcrypt
from pathlib import Path
try:
    from dotenv import load_dotenv
    # Load .env from software/ when present (development only)
    env_path = Path(__file__).resolve().parents[1] / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    # dotenv is optional in environments where env vars are already provided
    pass

# Configurações de ligação ao Docker (match docker-compose.yml)
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ.get("DB_NAME", "smile_iot_users"),
    "user": os.environ.get("DB_USER", "admin"),
    "password": os.environ.get("DB_PASSWORD", "password123"),
}

# Lockout / rate-limiting configuration (environment-configurable)
MAX_FAILED_ATTEMPTS = int(os.environ.get("MAX_FAILED_ATTEMPTS", 5))
LOCKOUT_MINUTES = int(os.environ.get("LOCKOUT_MINUTES", 15))

def verify_login(username, password):
    """Retorna um dic c/ os dados do utilizador ou None se der erro"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, username, role, password_hash, failed_attempts, locked_until
            FROM utilizadores
            WHERE username = %s
        """, (username,))

        user = cur.fetchone()

        if user:
            user_id, user_name, role, stored_hash, failed_attempts, locked_until = user

            # Check for active lockout
            if locked_until is not None:
                try:
                    now = datetime.utcnow()
                    if now < locked_until:
                        # still locked
                        log_login_attempt(username, False, reason="locked")
                        return None
                except Exception:
                    # If parsing locked_until fails, continue to verification
                    pass

            # Normalize stored_hash to bytes
            if isinstance(stored_hash, bytes):
                stored_hash_bytes = stored_hash
            elif isinstance(stored_hash, memoryview):
                stored_hash_bytes = stored_hash.tobytes()
            else:
                stored_hash_str = str(stored_hash).strip()
                if stored_hash_str.startswith("b'") and stored_hash_str.endswith("'"):
                    stored_hash_str = stored_hash_str[2:-1]
                stored_hash_bytes = stored_hash_str.encode()

            # Verify password
            if bcrypt.checkpw(password.encode(), stored_hash_bytes):
                reset_failed_attempts(username)
                log_login_attempt(username, True, reason="success")
                return {
                    "id": user_id,
                    "username": user_name,
                    "role": role
                }
            else:
                new_fail_count = increment_failed_attempts(username)
                reason = "invalid_password"
                if new_fail_count is not None and new_fail_count >= MAX_FAILED_ATTEMPTS:
                    set_lockout(username, LOCKOUT_MINUTES)
                    reason = f"locked_after_{new_fail_count}"
                log_login_attempt(username, False, reason=reason)
                return None
        else:
            # Unknown username — log for audit
            log_login_attempt(username, False, reason="no_such_user")
            return None
        
    except Exception as e:
        print(f"Authentication error: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def hash_password(password: str) -> str:
    """Cria um hash da password para segurança"""
    # bcrypt.hashpw returns bytes; decode to store as text
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def get_connection():
    """Devolve uma ligação ativa à base de dados."""
    return psycopg2.connect(**DB_CONFIG)

def add_user(username, email, password, role):
    """Cria um novo utilizador no DB"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO utilizadores (username, email, password_hash, role) VALUES (%s, %s, %s, %s)",
            (username, email, hash_password(password), role)
        )
        conn.commit()
        return True, "Utitilizador criado com sucesso!"
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, "Erro: Username ou email ja existentes"
    except Exception as e:
        conn.rollback()
        return False, f"Unnespected error: {e}"
    
def update_password(user_id, new_password):
    """Atualizaa a password do user com o user_id"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "UPDATE utilizadores SET password_hash = %s WHERE id = %s",
            (hash_password(new_password), user_id)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def log_login_attempt(username, success: bool, reason: str = ""):
    """Append a login attempt to the audit table login_logs."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO login_logs (username, success, reason, timestamp) VALUES (%s, %s, %s, %s)",
            (username, success, reason, datetime.utcnow())
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def increment_failed_attempts(username):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE utilizadores SET failed_attempts = COALESCE(failed_attempts,0) + 1 WHERE username = %s RETURNING failed_attempts",
            (username,)
        )
        res = cur.fetchone()
        conn.commit()
        return res[0] if res else None
    except Exception:
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def set_lockout(username, minutes: int):
    conn = get_connection()
    cur = conn.cursor()
    try:
        until = datetime.utcnow() + timedelta(minutes=minutes)
        cur.execute(
            "UPDATE utilizadores SET locked_until = %s WHERE username = %s",
            (until, username)
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def reset_failed_attempts(username):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE utilizadores SET failed_attempts = 0, locked_until = NULL WHERE username = %s",
            (username,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def init_db():
    """Cria as tabelas e o Admin user."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # 1. Tabela de Utilizadores (com colunas para lockout)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS utilizadores (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL,
                failed_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP NULL
            );
        """)

        # 2. Tabela de Dispositivos (Placas ESP32)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dispositivos (
                id SERIAL PRIMARY KEY,
                mac_address VARCHAR(50) UNIQUE NOT NULL,
                nome_apresentacao VARCHAR(100) NOT NULL,
                limite_corrente DECIMAL(5,2) DEFAULT 15.0
            );
        """)

        # 3. Tabela de Permissões (A ponte entre utilizador e dispositivo)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS acessos_dispositivos (
                user_id INTEGER REFERENCES utilizadores(id) ON DELETE CASCADE,
                device_id INTEGER REFERENCES dispositivos(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, device_id)
            );
        """)

        # 4. Inserir um Admin por defeito (se a tabela estiver vazia)
        cur.execute("SELECT * FROM utilizadores WHERE username = 'admin'")
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO utilizadores (username, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                ('admin', '', hash_password('admin123'), 'admin')
            )
            print("🟢 Utilizador 'admin' criado com sucesso (password: 'admin123').")

        # Login logs table (audit trail)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS login_logs (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50),
                success BOOLEAN,
                reason TEXT,
                timestamp TIMESTAMP NOT NULL
            );
        """)

        conn.commit()
        print("Base de dados PostgreSQL inicializada")

    except Exception as e:
        print(f"Erro ao inicializar a base de dados: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    init_db()