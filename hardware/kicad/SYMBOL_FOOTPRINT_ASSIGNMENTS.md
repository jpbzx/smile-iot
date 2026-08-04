# SMILE-IoT PCB v1 — KiCad Symbol & Footprint Assignments

Companion to [`smile-iot-v1.net`](smile-iot-v1.net) and
[`../PCB_DESIGN_v1.md`](../PCB_DESIGN_v1.md). Tested against **KiCad 8**
standard libraries.

> The netlist uses **function pin names** (`VIN`, `COM`, `+Vo`, …) so it reads
> as a wiring spec. KiCad auto-associates a netlist node to a footprint pad by
> matching the pad **name string**. Several parts here (ESP32 module, relay,
> HLK-PM01, audio jack) use **numeric pads** in their stock footprints, so the
> function names will NOT auto-match those pads. Two ways to use this:
>
> 1. **Recommended — draw the schematic in eeschema** using the symbols below,
>    wiring per the net list in §2, then let KiCad emit the authoritative
>    netlist. This is the reliable path and takes ~30 min.
> 2. **Import the provided `.net` into Pcbnew** to get footprints + a partial
>    ratsnest, then fix the module/relay/HLK/jack pin associations by hand using
>    the pad-mapping table in §3.

---

## 1. Symbol + footprint per component

| Ref | Symbol (library:part) | Footprint (library:footprint) | Notes |
|-----|-----------------------|-------------------------------|-------|
| U1 | `RF_Module:ESP32-DevKitC-32D` *(or community 30-pin part)* | `Module:ESP32-DevKitC` **or** 2× `Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical` | Stock symbol is 38-pin. For the **30-pin DOIT DevKit V1**, install a community `ESP32_DevKit_V1_30P` symbol/footprint (SnapEDA / Ultra-Librarian), or socket it on two 1×15 female headers 25.4 mm apart. Only VIN, GND, 3V3, GPIO34, GPIO25, GPIO2, GPIO0, GPIO35 are used. |
| PS1 | `Converter_ACDC:HLK-PM01` | `Converter_ACDC:Converter_ACDC_HiLink_HLK-PMxx` | Isolated. Alt part for margin: `HLK-10M05` (2 A) — different footprint. |
| K1 | `Relay:Relay_SPDT` | `Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C` | 5 V coil, 10 A/250 VAC. |
| Q1 | `Transistor_BJT:BC547` | `Package_TO_SOT_THT:TO-92_Inline` | Symbol pins 1=C, 2=B, 3=E. |
| D1 | `Device:D` | `Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal` | Cathode band → `+5V`. |
| F1 | `Device:Fuse` | `Fuse:Fuseholder_Cylinder-5x20mm_Schurter_0031_8201_Horizontal` | 10 A T, 250 V. |
| RV1 | `Device:Varistor` | `Varistor:RV_Disc_D15mm_W5.1mm_P7.5mm` | S14K275. |
| R1 | `Device:R` | `Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal` | 1 kΩ |
| R2 | `Device:R` | *(same)* | 330 Ω |
| R3 | `Device:R` | *(same)* | 10 kΩ |
| R4 | `Device:R` | *(same)* | 10 kΩ |
| R5 | `Device:R` | *(same)* | 100 Ω, optional |
| C1 | `Device:CP` | `Capacitor_THT:CP_Radial_D8.0mm_P3.50mm` | 470 µF/10 V, polarized |
| C2 | `Device:C` | `Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm` | 100 nF |
| C3 | `Device:CP` | `Capacitor_THT:CP_Radial_D5.0mm_P2.00mm` | 10 µF, polarized |
| LED1 | `Device:LED` | `LED_THT:LED_D3.0mm` | Status |
| SW1 | `Switch:SW_Push` | `Button_Switch_THT:SW_PUSH_6mm` | BOOT / re-provision |
| J1 | `Connector:Screw_Terminal_01x03` | `TerminalBlock:TerminalBlock_bornier-3_P5.08mm` | Mains in L/N/PE |
| J2 | `Connector:Screw_Terminal_01x03` | *(same)* | Outlet out L/N/PE |
| J3 | `Connector_Audio:AudioJack3` | `Connector_Audio:Jack_3.5mm_CUI_SJ1-353xN_Horizontal` | SCT-013; tip=signal, sleeve=GND |
| H1 | `Connector:Conn_01x03_Pin` | `Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical` | DNP, voltage-sense reserve |

---

## 2. Net list (human-readable)

| Net | Connections (ref.pin) |
|-----|------------------------|
| **+5V** | PS1.+Vo · C1.+ · C2.1 · U1.VIN · K1.COIL+ · D1.K |
| **GND** | PS1.-Vo · C1.- · C2.2 · C3.- · U1.GND · Q1.E · R4.2 · LED1.K · SW1.2 · J3.Sleeve · H1.3 |
| **+3V3** | U1.3V3 · R3.1 · H1.2 |
| **SCT_BIAS** | J3.Tip · R3.2 · R4.1 · C3.+ · R5.1 |
| **GPIO34_ADC** | R5.2 · U1.GPIO34 |
| **GPIO25_RLY** | U1.GPIO25 · R1.1 |
| **RLY_BASE** | R1.2 · Q1.B |
| **RLY_COIL_LO** | Q1.C · K1.COIL- · D1.A |
| **GPIO2_LED** | U1.GPIO2 · R2.1 |
| **LED_ANODE** | R2.2 · LED1.A |
| **GPIO0_BTN** | U1.GPIO0 · SW1.1 |
| **VSENSE_RSVD** | U1.GPIO35 · H1.1 |
| **L_IN** *(mains)* | J1.LIVE · F1.1 |
| **L_FUSED** *(mains)* | F1.2 · RV1.1 · PS1.AC · K1.COM |
| **N** *(mains)* | J1.NEUTRAL · RV1.2 · PS1.AC · J2.NEUTRAL |
| **PE** *(mains)* | J1.EARTH · J2.EARTH |
| **L_SWITCHED** *(mains)* | K1.NO · J2.LIVE |

`K1.NC` is intentionally unconnected (Form-C relay, normally-open contact used).

---

## 3. Pad-mapping reconciliation (parts with non-numeric function pins)

When importing the `.net` into Pcbnew, associate these function names to the
stock footprint pads:

**PS1 — `Converter_ACDC_HiLink_HLK-PMxx`** (pads 1–4):
| Netlist pin | HLK-PM01 pad | Meaning |
|---|---|---|
| ACL | 1 | AC input |
| ACN | 2 | AC input (L/N interchangeable on primary) |
| -Vo | 3 | 0 V / GND out |
| +Vo | 4 | +5 V out |

**K1 — `Relay_SPDT_SANYOU_SRD_Series_Form_C`** — verify against the SRD datasheet
silk; the SANYOU SRD Form-C pad order is:
| Netlist pin | Function | Typical SRD pad |
|---|---|---|
| COIL+ / COILA | coil | coil pin (one end) |
| COIL- / COILB | coil | coil pin (other end) |
| COM | contact common / pole | center contact |
| NO | normally-open | switched-live out |
| NC | normally-closed | *(unused)* |

**U1 — ESP32 DevKit V1** — with a 30-pin community symbol, map by GPIO label
(`VIN`, `GND`, `3V3`, `D34/GPIO34`, `D25/GPIO25`, `D2/GPIO2`, `D0/GPIO0`,
`D35/GPIO35`). If socketing on 1×15 headers instead, place two `Conn_01x15`
and wire those 8 signals to the matching header pads.

**J3 — audio jack** — `Tip` → tip pad, `Sleeve` → sleeve/ground pad; ring pad
left floating.

**D1 / LED1 / C1 / C3 polarity** — `Device:D`/`LED` pin `A`=anode, `K`=cathode;
`Device:CP` pin `+`=positive. Confirm silk orientation before soldering.

---

## 4. After import — must-do checks

1. Run **DRC** with a custom rule enforcing the mains clearances from
   `PCB_DESIGN_v1.md` §6 (≥8 mm mains↔SELV, ≥2.5 mm L-N).
2. Confirm **no auto-router traces cross the isolation slot** — set a keep-out
   zone along the barrier.
3. Widen mains nets (`L_IN`, `L_FUSED`, `N`, `L_SWITCHED`) to §7 trace widths
   and pour/expose them.
4. Verify **GND is NOT connected to `N` or `PE`** anywhere (floating SELV).
