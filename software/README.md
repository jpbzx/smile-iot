# Software — SMILE-IoT Backend & Dashboard

Python application layer for telemetry ingestion, data visualization, and user management.

---

## Architecture Overview

The SMILE-IoT software stack follows a **multi-page Streamlit architecture** with integrated MQTT subscriber, dual-database persistence, and role-based authentication.

### Components

```
software/
├── app.py                     # Streamlit multi-page entry point
├── views/                     # UI pages (role-based navigation)
│   ├── login.py              # Authentication page
│   ├── dashboard.py          # Real-time monitoring (user + admin)
│   ├── admin_panel.py        # System management (admin only)
│   └── profile.py            # User profile & password management
├── db/                        # Database managers
│   ├── postgres_manager.py   # User auth, bcrypt hashing, lockout
│   └── influx_manager.py     # Time-series energy data writer
├── utils/                     # Supporting modules
│   ├── mqtt_client.py        # MQTT subscriber with threading
│   ├── database.py           # Connection helpers
│   └── simulated_data.py     # Test data generator
├── docker-compose.yml         # Infrastructure orchestration
├── Dockerfile                 # Streamlit app container
├── requirements.txt           # Python dependencies
└── .env                       # Environment variables (not committed)
```

### Key Features
- **Multi-page Navigation:** Role-based access (Admin sees all pages, Users see dashboard + profile)
- **Real-time MQTT:** Background thread subscribes to `smile-iot/power` and updates UI reactively
- **Dual Persistence:**
  - **PostgreSQL** — User accounts, authentication, metadata
  - **InfluxDB** — Time-series energy readings (current, power, outlet state)
- **Security:**
  - bcrypt password hashing
  - Failed login lockout (5 attempts → 15min block)
  - Session timeout (configurable, default 30 min)
- **Docker Orchestration:** All services (PostgreSQL, InfluxDB, Streamlit) run via `docker-compose`

---

## Setup

### Prerequisites
- **Docker & Docker Compose** (for databases)
- **Python 3.9+** (for local development)
- **MQTT Broker** (e.g., `broker.emqx.io` or local Mosquitto)

### Step 1: Environment Configuration
Create a `.env` file in the `software/` directory:
```bash
# PostgreSQL (User Database)
POSTGRES_USER=admin
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=smile_iot_users

# InfluxDB (Time-Series Database)
INFLUX_USER=admin
INFLUX_PASSWORD=your_secure_password
INFLUX_ORG=smile_org
INFLUX_BUCKET=energy_data
INFLUX_ADMIN_TOKEN=your_secure_token_here

# Application Settings
SESSION_TIMEOUT_MIN=30
MAX_FAILED_ATTEMPTS=5
LOCKOUT_MINUTES=15
```

### Step 2: Start Infrastructure
```bash
cd software
docker-compose up -d
```

This starts:
- `postgres_db` → PostgreSQL on port **5432**
- `influx_db` → InfluxDB on port **8086**
- `streamlit_app` → Dashboard on port **8501** (optional, can run locally)

### Step 3: Install Python Dependencies
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 4: Initialize Databases (First Run)
The database managers (`postgres_manager.py`, `influx_manager.py`) auto-initialize schemas on first connection. To manually create admin user:
```python
from db.postgres_manager import create_user

create_user("admin", "admin@smile-iot.local", "secure_password", role="admin")
```

### Step 5: Run Dashboard
```bash
streamlit run app.py
```

Access at **http://localhost:8501**

---

## Execution Modes

### Mode 1: Full Docker Deployment (Production)
```bash
docker-compose up -d  # All services in containers
```
- Dashboard accessible at **http://localhost:8501**
- Databases persist to `./data/postgres` and `./data/influx`

### Mode 2: Local Development (Hybrid)
```bash
docker-compose up -d postgres_db influx_db  # Only databases
streamlit run app.py                        # Dashboard locally
```
- Faster iteration for UI development
- Database connections via `localhost:5432` and `localhost:8086`

---

## User Roles & Access Control

| Role    | Login | Dashboard | Admin Panel | Profile |
|---------|-------|-----------|-------------|---------|
| `admin` | ✅     | ✅         | ✅           | ✅       |
| `user`  | ✅     | ✅         | ❌           | ✅       |

**Default Credentials:**
- Username: `admin`
- Password: *(set during first run)*

---

## MQTT Integration

### Subscription
The dashboard subscribes to:
- **Topic:** `smile-iot/power`
- **Payload:**
  ```json
  {
    "current_A": 5.23,
    "outlet_state": "ON"
  }
  ```

### Publishing Commands
From the dashboard, users can control the relay:
- **Topic:** `smile-iot/command`
- **Payload:** `ON` or `OFF`

### Thread Safety
- MQTT callbacks run in a background thread
- Data flows through a thread-safe `queue.Queue`
- `sync_mqtt()` transfers queued messages to `st.session_state` on each rerun

---

## Database Schemas

### PostgreSQL: `utilizadores`
```sql
CREATE TABLE utilizadores (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100),
    password_hash BYTEA NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    failed_attempts INT DEFAULT 0,
    locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### InfluxDB: `energy_reading`
- **Bucket:** `energy_data`
- **Measurement:** `energy_reading`
- **Tags:** `device`, `outlet_state`
- **Fields:** `current_A`, `power_W`, `voltage_V`

---

## Dependencies

Key Python packages (see `requirements.txt`):
```
streamlit               # Multi-page reactive UI
paho-mqtt              # MQTT client
pandas                 # Data manipulation
altair                 # Interactive charts
psycopg2-binary        # PostgreSQL driver
influxdb-client        # InfluxDB 2.x client
bcrypt                 # Password hashing
python-dotenv          # Environment variable loader
jsonschema             # JSON validation
```

---

## Troubleshooting

### Issue: Dashboard won't connect to databases
**Solution:** Ensure containers are running:
```bash
docker-compose ps
docker logs smile_postgres
docker logs smile_influx
```

### Issue: MQTT messages not appearing
**Solution:** Check broker connectivity:
```bash
# Test with mosquitto_sub (install mosquitto-clients)
mosquitto_sub -h broker.emqx.io -t "smile-iot/power" -v
```

### Issue: Login fails with correct credentials
**Solution:** Check password hash encoding:
```python
from db.postgres_manager import verify_login
result = verify_login("admin", "your_password")
print(result)  # Should return user dict or None
```

### Issue: Session expires immediately
**Solution:** Update `SESSION_TIMEOUT_MIN` in `.env` and restart:
```bash
docker-compose restart streamlit_app
```

---

## Development Workflow

1. **Make changes** to views or utils
2. **Refresh browser** — Streamlit auto-reloads on file save
3. **Check logs:**
   ```bash
   docker-compose logs -f streamlit_app
   ```
4. **Test MQTT flow:**
   - Use `utils/simulated_data.py` to generate fake data
   - Or flash firmware to ESP32 for real telemetry

---

## Security Best Practices

- ✅ **Never commit `.env`** — add to `.gitignore`
- ✅ **Use strong passwords** — bcrypt hashing with salt
- ✅ **Rotate InfluxDB tokens** periodically
- ⚠️ **TLS for MQTT** — Not implemented yet (TODO)
- ⚠️ **Private broker** — Currently using public `broker.emqx.io`

---

## Next Steps

- [ ] Implement MQTT over TLS/SSL
- [ ] Add historical data export (CSV/PDF)
- [ ] Create REST API for external integrations
- [ ] Add email notifications for alerts
- [ ] Multi-device support (multiple ESP32 nodes)

---

**⚡ For system-wide documentation, see [../docs/SPEC.md](../docs/SPEC.md)**


