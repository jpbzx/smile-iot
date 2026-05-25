# SMILE-IoT: Local Energy Monitoring and Inspection System via IoT

**Última atualização:** Maio 25, 2026  
**Branch ativo:** `feature/set_sistem_4_prodReady`  
**Versão:** v0.2-beta (Produção ready)

---

## 1. Overview
**SMILE-IoT** is an embedded system prototype for non-invasive monitoring of alternating current (AC) electrical energy consumption. The project aims to address the need to audit and profile the consumption of equipment or electrical panels quickly, safely, and cost-effectively, without the need for circuit interruption or complex electrical interventions.

The system bridges **Electrical Engineering** (analog signal acquisition and conditioning, power calculation) and **Software Engineering** (microcontroller processing, IoT transmission, and real-time data visualization).

### Key Features
- ✅ Non-invasive AC current monitoring via SCT-013-030 sensor
- ✅ Real-time MQTT telemetry transmission
- ✅ Relay control for outlet switching (ON/OFF)
- ✅ Multi-page Streamlit dashboard with authentication
- ✅ PostgreSQL (user management) + InfluxDB (time-series data)
- ✅ Docker-based infrastructure orchestration
- ✅ Role-based access control (Admin/User)

---

## 2. System Architecture
The architecture was designed with a focus on modularity and rapid feasibility, divided into three main layers: perception (Hardware), transport (Network), and application (Software).

### Logical Block Diagram
```text
[ AC Electrical Grid @ 230V ] 
       │
       ▼ (Magnetic Field)
┌────────────────────────────┐      ┌───────────────────┐      ┌──────────────────┐
│ 1. SCT-013 Sensor          ├─────►│ 2. Signal         ├─────►│ 3. ESP32         │
│    (Current Transformer    │      │    Conditioning   │      │    (12-bit ADC)  │
│     30A/1V, 0.5s delay)    │      │    (Voltage Div.) │      │    RMS Calc.     │
│                            │      │                   │      │    Relay Control │
└────────────────────────────┘      └───────────────────┘      └─────────┬────────┘
                                                                        │
                                                    ┌───────────────────┼───────────────────┐
                                                    │                   │                   │
                                                    ▼ (Wi-Fi/MQTT)      │                   │
                                        ┌──────────────────────┐        │                   │
                                        │ 4. MQTT Broker       │        │                   │
                                        │    (EMQX/Mosquitto)  │        │                   │
                                        └──────────┬───────────┘        │                   │
                                                   │                    │                   │
                                                   ▼                    ▼                   ▼
                                    ┌──────────────────────┐  ┌─────────────────┐  ┌──────────────────┐
                                    │ 5. PostgreSQL        │  │ 6. InfluxDB     │  │ 7. Streamlit     │
                                    │    (Utilizadores,    │  │    (Série       │  │    Dashboard     │
                                    │     Permissões)      │  │     Temporal)   │  │    (Multi-page)  │
                                    └─────────┬────────────┘  └────────┬────────┘  └────────┬─────────┘
                                              │                        │                   │
                                              └────────────┬───────────┴───────────────────┘
                                                           │
                                                           ▼
                                                   ┌──────────────────┐
                                                   │ 8. End User      │
                                                   │    (Browser)     │
                                                   └──────────────────┘
```

---

## 3. Technology Stack

### Hardware
- **Microcontroller:** ESP32 DevKit V1 (Wi-Fi, 12-bit ADC)
- **Sensor:** SCT-013-030 (30A/1V non-invasive CT sensor)
- **Relay:** GPIO-controlled for outlet switching
- **Signal Conditioning:** Voltage divider + DC offset

### Firmware
- **Platform:** PlatformIO (Arduino framework)
- **Language:** C++
- **Key Libraries:**
  - `EmonLib` — RMS current calculation
  - `PubSubClient` — MQTT client
  - `ArduinoJson` — JSON serialization

### Software Stack
- **Frontend:** Streamlit (Python, reactive multi-page UI)
- **Backend:** Python 3.9+ with async MQTT subscriber
- **Databases:**
  - PostgreSQL 15 (user management, metadata)
  - InfluxDB 2.7 (time-series energy data)
- **Message Broker:** MQTT (EMQX/Mosquitto)
- **Orchestration:** Docker Compose
- **Authentication:** bcrypt password hashing with lockout protection

### Infrastructure
- **Containerization:** Docker + Docker Compose
- **Services:**
  - `postgres_db` — PostgreSQL container
  - `influx_db` — InfluxDB container
  - `streamlit_app` — Dashboard application

---

## 4. Project Structure

```
smile-iot/
├── firmware/                    # ESP32 embedded code
│   ├── src/
│   │   └── main.cpp            # Sensor reading, MQTT TX/RX, relay control
│   ├── platformio.ini          # PlatformIO configuration
│   └── README.md               # Firmware-specific instructions
│
├── software/                    # Python backend & dashboard
│   ├── app.py                  # Streamlit multi-page entry point
│   ├── views/                  # UI pages (login, dashboard, admin, profile)
│   │   ├── login.py            # Authentication page
│   │   ├── dashboard.py        # Real-time monitoring
│   │   ├── admin_panel.py      # System management (admin only)
│   │   └── profile.py          # User profile settings
│   ├── db/                     # Database managers
│   │   ├── postgres_manager.py # PostgreSQL ORM & auth logic
│   │   └── influx_manager.py   # InfluxDB time-series writer
│   ├── utils/                  # Supporting modules
│   │   ├── mqtt_client.py      # MQTT subscriber with threading
│   │   ├── database.py         # Connection helpers
│   │   └── simulated_data.py   # Test data generator
│   ├── docker-compose.yml      # Infrastructure orchestration
│   ├── Dockerfile              # Streamlit app container image
│   ├── requirements.txt        # Python dependencies
│   └── README.md               # Software-specific instructions
│
├── hardware/                    # Circuit schematics & BOM
│   └── README.md               # Hardware documentation
│
├── docs/                        # Academic documentation & specifications
│   ├── SPEC.md                 # Detailed system specification
│   ├── AGENT_README.md         # GitHub Copilot agent instructions
│   └── README.md               # Documentation overview
│
├── README.md                    # This file
├── LICENSE                      # Project license
└── CHANGELOG.md                 # Version history
```

---

## 5. Quick Start

### Prerequisites
- **Hardware:** ESP32 + SCT-013-030 sensor + relay module
- **Software:** Docker, Docker Compose, Python 3.9+, PlatformIO

### Step 1: Clone Repository
```bash
git clone https://github.com/jpbzx/smile-iot.git
cd smile-iot
```

### Step 2: Start Infrastructure (Databases)
```bash
cd software
cp .env.example .env  # Create and configure environment variables
docker-compose up -d
```

### Step 3: Flash Firmware to ESP32
```bash
cd firmware
pio run -t upload
pio device monitor -b 115200  # Monitor serial output
```

### Step 4: Run Dashboard
```bash
cd software
pip install -r requirements.txt
streamlit run app.py
```

Access the dashboard at **http://localhost:8501**

---

## 6. MQTT Protocol

### Topics
- **Telemetry (ESP32 → Dashboard):** `smile-iot/power`
- **Commands (Dashboard → ESP32):** `smile-iot/command`

### Telemetry Payload (JSON TX)
```json
{
  "current_A": 5.23,
  "outlet_state": "ON"
}
```
**Note:** `power_W` and `voltage_V` are calculated on the backend using nominal voltage (230V PT).

### Command Payload (RX)
```
ON   # Turn outlet relay ON
OFF  # Turn outlet relay OFF
```

---

## 7. Database Schema

### PostgreSQL: `smile_iot_users`
**Table: `utilizadores`**
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

### InfluxDB: `energy_data`
**Measurement:** `energy_reading`
- **Tags:** `device`, `outlet_state`
- **Fields:** `current_A`, `power_W`, `voltage_V`
- **Timestamp:** Automatic

---

## 8. Features

### Current Implementation
- [x] Real-time AC current monitoring
- [x] MQTT telemetry transmission
- [x] Remote relay control (outlet ON/OFF)
- [x] Multi-page Streamlit dashboard
- [x] User authentication with bcrypt
- [x] Role-based access control (Admin/User)
- [x] PostgreSQL user management
- [x] InfluxDB time-series data storage
- [x] Docker-based deployment
- [x] Session timeout & lockout protection

### Planned Features
- [ ] TLS/SSL MQTT encryption
- [ ] Multi-device support (multiple sensors)
- [ ] Energy cost calculation (€/kWh)
- [ ] Alert notifications (threshold-based)
- [ ] REST API for external integrations
- [ ] Historical data export (CSV/PDF reports)

---

## 9. Security Considerations

⚠️ **Current Security Status:**
- **Passwords:** Hashed with bcrypt ✅
- **MQTT:** No TLS encryption ⚠️ (public broker)
- **Database:** Local Docker deployment ✅
- **Session Management:** Timeout protection ✅
- **Account Lockout:** Failed login protection ✅

**TODO:**
- Implement MQTT over TLS/SSL
- Deploy private MQTT broker
- Add environment-based secret management

---

## 10. Contributing

Contributions are welcome! Please follow these guidelines:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 11. License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

## 12. Contact

**Maintainer:** João Bessa  
**Institution:** ISEP — Instituto Superior de Engenharia do Porto  
**Email:** [Your email here]  
**Repository:** [github.com/jpbzx/smile-iot](https://github.com/jpbzx/smile-iot)

---

**⚡ SMILE-IoT — Simplifying Energy Monitoring with IoT**