# Hardware

Circuit schematics, BOM, and physical wiring documentation.

## Bill of Materials (BOM)
* 1x ESP32 DevKit V1
* 1x SCT-013-030 (30A/1V Non-invasive Current Sensor)
* 2x 10kΩ Resistors (Voltage Divider)
* 1x 10µF Electrolytic Capacitor (Noise filtering)
* 1x 3.5mm Audio Jack Breakout Board

## Pinout Mapping
| ESP32 Pin | Connection | Function |
| :--- | :--- | :--- |
| `3V3` | Resistor Network | DC Bias supply (1.65V offset) |
| `GND` | Ground | Common Ground |
| `GPIO 34` | Sensor Output | Analog to Digital Converter (ADC) input |

*(Place schematic exports and wiring diagrams in this directory).*
