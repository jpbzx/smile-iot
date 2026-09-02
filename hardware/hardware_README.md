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

## Bench rig (build this first)
[BENCH_RIG_v1.md](BENCH_RIG_v1.md) is the hand-wired version of the same circuit,
assembled from off-the-shelf modules in a project box — full buy-today BOM (~€129
including a clamp meter), relay-module wiring, the multi-turn CT trick for small
loads, and the bring-up sequence. It validates the firmware and calibration
against a real load *before* committing to a fabbed board.

## PCB Design
A full board design package (mains-powered outlet monitor + relay switch) —
schematic by net, BOM, floorplan, mains isolation rules, and fab spec — is in
[PCB_DESIGN_v1.md](PCB_DESIGN_v1.md). The BOM above covers the current-sense
front end only; the PCB adds the isolated AC-DC supply, on-board relay, fuse,
and surge suppression.

A KiCad-format netlist and the symbol/footprint assignment table are under
[kicad/](kicad/) — [`smile-iot-v1.net`](kicad/smile-iot-v1.net) plus
[`SYMBOL_FOOTPRINT_ASSIGNMENTS.md`](kicad/SYMBOL_FOOTPRINT_ASSIGNMENTS.md).
