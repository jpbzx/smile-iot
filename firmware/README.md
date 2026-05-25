# Firmware — ESP32 Energy Monitor & Relay Controller

ESP32 C++ codebase for the SMILE-IoT edge node.

---

## Overview
Responsible for:
- **Analog signal acquisition** from SCT-013-030 current transformer
- **RMS current calculation** using EmonLib
- **MQTT telemetry publishing** (current + outlet state)
- **Relay control** via MQTT commands (ON/OFF)
- **Overcurrent protection** (automatic shutoff at 15A)

---

## Hardware Requirements

### Components
- **Microcontroller:** ESP32 DevKit V1
- **Current Sensor:** SCT-013-030 (30A/1V non-invasive CT)
- **Relay Module:** 5V/3.3V compatible (GPIO-controlled)
- **Signal Conditioning:** Voltage divider (2x 10kΩ resistors)
- **Power Supply:** USB or 5V DC

### Pinout
| ESP32 Pin | Component      | Function                     |
|-----------|----------------|------------------------------|
| `GPIO 34` | SCT-013 output | ADC input (analog reading)   |
| `GPIO 25` | Relay module   | Digital output (ON/OFF)      |
| `GPIO 2`  | Built-in LED   | Status indicator             |
| `3V3`     | Voltage divider| DC bias (1.65V offset)       |
| `GND`     | Common ground  | Reference                    |

---

## Stack
- **Environment:** PlatformIO
- **Framework:** Arduino Core (C++)
- **Dependencies:**
  - `EmonLib` (v1.1.0) — Energy Monitoring Library (RMS calculation)
  - `PubSubClient` — MQTT client
  - `ArduinoJson` — JSON serialization

---

## Features Implemented

### 1. Current Measurement
- **Sensor:** SCT-013-030 (calibration factor: 30)
- **Sampling:** 2500 samples per RMS calculation (~0.5s interval)
- **ADC Resolution:** 12-bit (0-4095)
- **Voltage Range:** 0-3.3V (after signal conditioning)

### 2. MQTT Telemetry
**Topic (TX):** `smile-iot/power`  
**Payload:**
```json
{
  "current_A": 5.23,
  "outlet_state": "ON"
}
```
- **Publish Rate:** ~1 message/second
- **Broker:** `broker.emqx.io:1883` (public MQTT broker)
- **Credentials:** Username `1211189`, password `isep`

### 3. Relay Control
**Topic (RX):** `smile-iot/command`  
**Payload:** `ON` or `OFF` (plain text)

**Behavior:**
- `ON` → Energize relay (GPIO 25 HIGH), LED ON
- `OFF` → De-energize relay (GPIO 25 LOW), LED OFF
- Default state: **OFF** on boot

### 4. Overcurrent Protection
- **Threshold:** 15A (typical European household limit)
- **Action:** If current > 15A **and** relay is ON:
  - Automatically turn OFF relay
  - Turn OFF LED indicator
  - Continue monitoring (does not crash)

---

## Configuration

### Wi-Fi Credentials
Edit in `main.cpp`:
```cpp
const char *ssid = "Your_SSID";
const char *pwd = "Your_Password";
```

### MQTT Broker
```cpp
const char *mqtt_broker = "broker.emqx.io";  // Change to private broker
const int port = 1883;                       // 8883 for TLS (not implemented)
```

### Calibration Factor
```cpp
const double calib = 30;  // For SCT-013-030 (no burden resistor)
                          // Use 60.6 for SCT-013-000 (with 33Ω burden)
```

---

## Build & Flash

### Compile
```bash
cd firmware
pio run
```

### Upload to ESP32
```bash
pio run -t upload
```

### Monitor Serial Output
```bash
pio device monitor -b 115200
```

### Generate `compile_commands.json` (for clangd/LSP)
```bash
pio run -t compiledb
```

---

## Serial Output Example
```
Connecting to wifi... make sure network is available
Connected!
Connecting to a MQTT broker as: esp32-1-AA:BB:CC:DD:EE:FF
LIGADO!
CUrrent: 5.230000
Received command on topic -> smile-iot/command: ON
CUrrent: 5.450000
CUrrent: 12.100000
```

---

## MQTT Topics

| Direction | Topic               | Payload                      | Description                  |
|-----------|---------------------|------------------------------|------------------------------|
| ESP32 → Server | `smile-iot/power` | `{"current_A": 5.23, "outlet_state": "ON"}` | Real-time telemetry |
| Server → ESP32 | `smile-iot/command` | `ON` or `OFF`              | Relay control command        |

---

## Code Structure

```cpp
// main.cpp
#include <EmonLib.h>         // RMS calculation
#include <PubSubClient.h>    // MQTT
#include <ArduinoJson.h>     // JSON serialization

EnergyMonitor emon;          // Energy monitor instance
PubSubClient client(espClient);

void setup() {
  emon.current(SCT_PIN, calib);  // Initialize sensor
  WiFi.begin(ssid, pwd);         // Connect to Wi-Fi
  client.setServer(broker, port); // Configure MQTT
  client.setCallback(callback);  // Set command handler
}

void loop() {
  client.loop();                 // Process MQTT messages
  double current = emon.calcIrms(2500);  // Calculate RMS
  
  // Safety check
  if (current > 15.0 && relay_state) {
    digitalWrite(RELAY_PIN, LOW);  // Emergency shutoff
  }
  
  // Publish telemetry
  JsonDocument doc;
  doc["current_A"] = current;
  doc["outlet_state"] = relay_state ? "ON" : "OFF";
  client.publish("smile-iot/power", jsonBuffer);
}
```

---

## Dependencies (platformio.ini)

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
lib_deps = 
  bblanchon/ArduinoJson
  pubsubclient
  openenergymonitor/EmonLib@^1.1.0
```

---

## Troubleshooting

### Issue: Wi-Fi won't connect
**Solution:**
- Verify SSID and password in `main.cpp`
- Check 2.4GHz network availability (ESP32 doesn't support 5GHz)
- Ensure network allows device-to-device communication

### Issue: MQTT connection fails
**Solution:**
- Test broker connectivity: `mosquitto_sub -h broker.emqx.io -t "#" -v`
- Check firewall rules (port 1883 must be open)
- Try alternative broker (e.g., `test.mosquitto.org`)

### Issue: Current readings stuck at 0
**Solution:**
- Verify SCT-013 is clamped around **one conductor only** (not both L+N)
- Check ADC pin connection (GPIO 34)
- Confirm voltage divider provides 1.65V DC offset
- Test ADC reading: `Serial.println(analogRead(SCT_PIN));`

### Issue: Relay doesn't respond to commands
**Solution:**
- Check subscription topic: `client.subscribe("smile-iot/command");`
- Verify relay module power supply (5V or 3.3V)
- Test GPIO manually: `digitalWrite(RELAY_PIN, HIGH); delay(1000);`
- Monitor serial for "Received command" messages

---

## Security Considerations

⚠️ **Current Implementation Risks:**
- No MQTT TLS/SSL encryption
- Hardcoded credentials in source code
- Public broker (no access control)

**TODO:**
- Implement MQTT over TLS (port 8883)
- Store credentials in SPIFFS/NVS (not in code)
- Deploy private MQTT broker with authentication

---

## Next Steps

- [ ] Add timestamp to telemetry (RTC or NTP sync)
- [ ] Implement power calculation on-device (P = I × V × PF)
- [ ] Add Wi-Fi reconnection logic (auto-retry)
- [ ] Store calibration factor in EEPROM
- [ ] Implement OTA (Over-The-Air) firmware updates

---

**⚡ For system architecture, see [../docs/SPEC.md](../docs/SPEC.md)**


