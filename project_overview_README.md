# SMILE-IoT: Local Energy Monitoring and Inspection System via IoT

## 1. Overview
**SMILE-IoT** is an embedded system prototype for non-invasive monitoring of alternating current (AC) electrical energy consumption. The project aims to address the need to audit and profile the consumption of equipment or electrical panels quickly, safely, and cost-effectively, without the need for circuit interruption or complex electrical interventions.

The system bridges **Electrical Engineering** (analog signal acquisition and conditioning, power calculation) and **Software Engineering** (microcontroller processing, IoT transmission, and real-time data visualization).

---

## 2. System Architecture
The architecture was designed with a focus on modularity and rapid feasibility, divided into three main layers: perception (Hardware), transport (Network), and application (Software).

### Logical Block Diagram
```text
[ AC Electrical Grid ] 
       │
       ▼ (Magnetic Field)
┌────────────────────┐      ┌──────────────────────┐      ┌────────────────────┐
│ 1. SCT-013 Sensor  ├─────►│ 2. Signal            ├─────►│ 3. Microcontroller │
│ (Current           │      │ Conditioning         │      │ ESP32 (12-bit ADC) │
│  Transformer       │      │                      │      │ RMS Processing     │
│  30A/1V)           │      │                      │      │                    │
└────────────────────┘      └──────────────────────┘      └─────────┬──────────┘
                                                                    │
                                                                    ▼ (Wi-Fi / MQTT)
┌────────────────────┐      ┌──────────────────────┐      ┌────────────────────┐
│ 6. End User        │◄─────┤ 5. Web Dashboard     │◄─────┤ 4. IoT Server      │
│ (Browser/Mobile)   │      │ (Real-Time Charts)   │      │ (Broker/Backend)   │
└────────────────────┘      └──────────────────────┘      └────────────────────┘
```

Concretely, layer 4–5 is implemented in [`software/`](software/software_README.md) as
Mosquitto (MQTT broker) + a Python ingest worker + a Flask REST API over
PostgreSQL/InfluxDB, with a React dashboard — detailed in
[docs/SOFTWARE_ARCHITECTURE_2026-07-09.md](docs/SOFTWARE_ARCHITECTURE_2026-07-09.md).
Layer 3 is the ESP32 firmware in [`firmware/`](firmware/)
([docs/FIRMWARE_REWRITE_2026-07-08.md](docs/FIRMWARE_REWRITE_2026-07-08.md)).