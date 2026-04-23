# Firmware

ESP32 C++ codebase for the SMILE-IoT edge node. 

## Overview
Responsible for analog signal acquisition, RMS calculation, and MQTT telemetry publishing. The firmware reads data from the SCT-013 current transformer, calculates the estimated power consumption, and streams JSON payloads over Wi-Fi.

## Stack
* **Environment:** PlatformIO
* **Framework:** Arduino Core (C++)
* **Dependencies:** `PubSubClient` (MQTT), `EmonLib` (Energy Monitoring)

## Quickstart

Initialize the PlatformIO environment and compile the database for `clangd` (Neovim):
```bash
pio run -t compiledb
```

Build, flash to the ESP32, and open the serial monitor

```bash
pio run -t upload && pio device monitor -b 115200
```


