---
applyTo: "**"
---

# SMILE-IoT — Contexto do Workspace

Este workspace é o projeto **SMILE-IoT**: sistema de monitorização não-invasiva de energia elétrica AC com ESP32, MQTT, PostgreSQL, InfluxDB e Streamlit.

- **Firmware:** `firmware/src/main.cpp` — ESP32, EmonLib, PubSubClient (PlatformIO)
- **Backend/Dashboard:** `software/` — Streamlit multi-page, Python 3.9+
- **Bases de dados:** `software/db/` — PostgreSQL 15 (utilizadores) + InfluxDB 2.7 (série temporal)
- **MQTT topics:** TX `smile-iot/power`, RX `smile-iot/control/outlet`
- **Infra:** `software/docker-compose.yml` — PostgreSQL + InfluxDB
- **Spec completa:** `docs/SPEC.md` — fonte de verdade para requisitos, schemas e arquitetura

**Regras de segurança do projeto:**
- Nunca commitar segredos — usar `.env` não versionado
- Passwords sempre hashed com bcrypt/argon2
- Queries SQL sempre parametrizadas
- MQTT sem TLS é um risco ativo (TODO pendente)
