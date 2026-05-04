import psycopg2
import hashlib

# Configurações de ligação ao Docker (match docker-compose.yml)
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "smile_iot_users",
    "user": "admin",
    "password": "password123"
}

def hash_password(password: str) -> str:
    """Cria um hash da password para segurança"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_connection():
    """Devolve uma ligação ativa à base de dados."""
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """Cria as tabelas e o Admin user."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # 1. Tabela de Utilizadores
        cur.execute("""
            CREATE TABLE IF NOT EXISTS utilizadores (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL
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
                "INSERT INTO utilizadores (username, password_hash, role) VALUES (%s, %s, %s)",
                ('admin', hash_password('admin123'), 'admin')
            )
            print("🟢 Utilizador 'admin' criado com sucesso (password: 'admin123').")

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