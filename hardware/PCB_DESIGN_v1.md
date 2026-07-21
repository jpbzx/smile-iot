# SMILE-IoT — PCB Design v1 (mains-powered outlet monitor + switch)

> ⚠️ **This board switches and is powered directly from 230 V AC mains.** The
> design below follows IEC 62368-1 / IPC-2221 spacing for basic + reinforced
> insulation, but **it must be reviewed by someone qualified before fabrication
> or energisation.** Never bench-test the mains side without an isolation
> transformer and RCD. When in doubt, keep the low-voltage side USB-powered and
> populate only the SELV zone.

---

## 1. Scope

A single self-contained board that:

- is powered from mains via an **isolated** AC-DC module (no external USB brick),
- **switches the outlet's LIVE conductor** through an on-board relay (GPIO25, active-HIGH),
- senses load current with the existing **SCT-013-030** clamp via a 3.5 mm jack,
- runs the existing ESP32 firmware unchanged (same pinout as `include/config.h`),
- carries a fuse + surge suppression on the mains inlet.

Voltage sensing (ZMPT101B / real power) is **deliberately out of scope** for v1 —
see §10. The board reserves an unpopulated header so it can be added later without
a respin.

---

## 2. Two-zone architecture

The board is split by a physical **isolation barrier** into two galvanically
separate zones. Nothing but the isolation barrier crosses between them.

```
        ┌──────────────── MAINS ZONE (230 VAC, HAZARDOUS) ─────────────────┐
 L ─[F1]─┬─[MOV]─┬─────────────────────[ RELAY K1 contacts ]──── L_out ───┐ │
         │       │                                                        │ │
 N ──────┴───────┴──────────────────────────────────────────── N_out ────┤ │
 PE ─────────────────────────────────(pass-through, unswitched)── PE_out ─┘ │
         │                                                                   │
         └──[ HLK-PM01 AC-DC, ISOLATED ]══╪══ isolation barrier ══╪══► +5V   │
        └───────────────────────────────╪══════════════════════╪────────────┘
                                         │  (transformer + opto only paths    │
                                         │   allowed to cross the slot)       │
        ┌──────────── SELV ZONE (5 V / 3V3, SAFE-TO-TOUCH) ─────────────────┐
        │  +5V ─► ESP32 DevKit ─► 3V3 ─► SCT bias network ─► GPIO34         │
        │  GPIO25 ─► relay driver (Q1) ─► K1 coil (5 V side)                │
        │  GPIO0 ─► BOOT btn   GPIO2 ─► status LED                          │
        └───────────────────────────────────────────────────────────────────┘
```

Key safety facts that make this topology sound:

- **HLK-PM01 is an isolated flyback** — its transformer is the only power path
  crossing into SELV. The 5 V/GND rail therefore floats relative to mains (SELV).
- **The relay isolates coil from contacts internally** (≥3 kV). The MCU never
  touches mains.
- **The SCT-013 is a clamp CT** — inductively coupled, no galvanic contact.
- **No earth on the SELV side.** This is a Class-II (double-insulated) design;
  do NOT tie mains N or PE to signal GND. PE passes straight through, unswitched.
- Only **LIVE** is switched (K1) and it is also the conductor the SCT clamps.

---

## 3. Schematic (by net)

### 3.1 Mains inlet & protection
```
J1-L (screw terminal, LIVE in)
   └─ F1 (fuse, 5×20mm, 10 A slow-blow, 250 V) ─┬─ RV1 (MOV, 275 VAC S14K275) ─ N
                                                 ├─ HLK-PM01  Vac(L)
                                                 └─ K1 COM (relay common)
J1-N (screw terminal, NEUTRAL in) ─┬─ RV1 other leg
                                   ├─ HLK-PM01  Vac(N)
                                   └─ J2-N (NEUTRAL out, pass-through)
J1-PE (EARTH in) ────────────────── J2-PE (EARTH out, pass-through, unswitched)

K1 NO (normally-open) ─ J2-L  (switched LIVE out to controlled outlet)
```
Optional across K1 COM–NO for inductive loads: **RC snubber** R=100 Ω 2 W + C=100 nF X2 (footprint provided, DNP by default).

### 3.2 Isolated power supply
```
HLK-PM01  +Vo ─┬─ C1 470 µF/10 V (bulk) ─┬─ C2 100 nF ─ +5V rail
               │                          │
HLK-PM01  -Vo ─┴──────────────────────────┴─ GND (SELV)
```
The 470 µF bulk cap covers the ESP32's WiFi-TX current bursts (HLK-PM01 = 600 mA;
bursts can hit ~500 mA). If you see brownout resets, swap to **HLK-10M05** (5 V/2 A,
same isolation, larger footprint — see alt footprint on board).

### 3.3 ESP32 + I/O (SELV) — matches `include/config.h`
```
+5V ──► ESP32 DevKit VIN
GND ──► ESP32 DevKit GND
ESP32 3V3 ──► SCT bias divider + jack sleeve reference

Current sense (GPIO34, ADC1_CH6, input-only):
  J3 (3.5 mm jack)  TIP  ─┬─ R3 10 kΩ ─ 3V3
                          ├─ R4 10 kΩ ─ GND        (mid-rail 1.65 V bias)
                          ├─ C3 10 µF ─ GND        (bias decoupling)
                          └─ R5 (optional 100 Ω series) ─ GPIO34
  J3 SLEEVE ─ GND

Relay driver (GPIO25, active-HIGH):
  GPIO25 ─ R1 1 kΩ ─ Q1 base (BC547 / 2N2222 NPN)
  Q1 emitter ─ GND
  Q1 collector ─ K1 coil(-) 
  K1 coil(+) ─ +5V
  D1 1N4007 flyback across K1 coil (cathode to +5V)

Status LED (GPIO2):
  GPIO2 ─ R2 330 Ω ─ LED1 ─ GND     (GPIO2 is a strapping pin; LED to GND
                                      keeps it low at boot — safe)
Provisioning button (GPIO0):
  GPIO0 ─ SW1 ─ GND                  (GPIO0 strapping; idle HIGH via internal
                                      pull-up, pressed = re-provision)
Reserved (voltage sense, DNP):
  H1 3-pin header → GPIO35 / 3V3 / GND  for future ZMPT101B
```

---

## 4. Bill of Materials

| Ref | Part | Value / Spec | Zone | Notes |
|-----|------|--------------|------|-------|
| U1 | ESP32-DevKitC V1 | 30-pin module | SELV | On 2×15 female headers (socketed, not soldered flat) |
| PS1 | Hi-Link **HLK-PM01** | 230 VAC→5 V 3 W, isolated | barrier | Alt footprint: HLK-10M05 (2 A) |
| K1 | Relay **SRD-05VDC-SL-C** | 5 V coil, 10 A/250 VAC SPDT | barrier | Coil↔contact ≥3 kV |
| Q1 | NPN transistor | BC547 / 2N2222 | SELV | Relay coil driver |
| D1 | Diode | 1N4007 | SELV | Coil flyback |
| F1 | Fuse + holder | 10 A slow-blow, 5×20 mm, 250 V | MAINS | Size ≤ relay & trace rating |
| RV1 | Metal-oxide varistor | S14K275 (275 VAC) | MAINS | L-N surge clamp |
| R1 | Resistor | 1 kΩ | SELV | Q1 base |
| R2 | Resistor | 330 Ω | SELV | LED |
| R3, R4 | Resistor | 10 kΩ (×2) | SELV | ADC mid-rail bias |
| R5 | Resistor | 100 Ω (optional) | SELV | GPIO34 series protection |
| C1 | Electrolytic cap | 470 µF / 10 V | SELV | 5 V bulk |
| C2 | Ceramic cap | 100 nF | SELV | 5 V decouple |
| C3 | Electrolytic cap | 10 µF | SELV | Bias decoupling (existing BOM) |
| LED1 | LED | 3 mm | SELV | Status |
| SW1 | Tactile switch | 6 mm | SELV | BOOT / re-provision |
| J1 | Screw terminal, 3-way | 5.08 mm pitch, ≥300 V | MAINS | L / N / PE in |
| J2 | Screw terminal, 3-way | 5.08 mm pitch, ≥300 V | MAINS | L_out / N_out / PE_out |
| J3 | 3.5 mm jack | PJ-320 breakout | SELV | SCT-013-030 input |
| H1 | Pin header, 1×3 | 2.54 mm | SELV | Voltage-sense reserve (DNP) |
| — | RC snubber (R,C) | 100 Ω 2 W + 100 nF X2 | MAINS | DNP; for inductive loads |

The **SCT-013-030, 2×10 kΩ, 10 µF, and 3.5 mm jack** from the current
`hardware_README.md` BOM are carried over unchanged. New for the PCB:
HLK-PM01, relay + driver (Q1/D1/R1), fuse, MOV, terminals.

---

## 5. Board floorplan (component placement)

Two-layer FR-4, ~**100 × 75 mm**. Mains zone on the left, SELV on the right,
separated by a **routed isolation slot** running the full height of the board.

```
  100 mm
┌───────────────────────────────────────────────────────────────┐
│  MAINS ZONE (hatched, silk-outlined, "⚡230V")   ║ SELV ZONE    │
│                                                  ║              │
│  ┌─────┐   ┌──────────┐        ┌──────────┐      ║  ┌────────┐  │ 
│  │ J1  │   │   F1     │        │   K1     │      ║  │  J3    │  │ 75
│  │L N PE│  │  fuse    │        │  relay   │      ║  │ jack   │  │ mm
│  └─────┘   └──────────┘        └────┬─────┘      ║  └────────┘  │
│    │  RV1                           │ COM/NO     ║  R3 R4 C3    │
│   ┌──────────┐                 ┌────┴─────┐      ║   bias net   │
│   │ HLK-PM01 │                 │   J2     │      ║ ┌──────────┐ │
│   │  AC-DC   │═══► +5V ─────────╫──────────╫─────►║ │  U1      │ │
│   └──────────┘   isolation      ║ L_out    ║      ║ │  ESP32   │ │
│                  barrier ══════►║ N N PE   ║      ║ │ DevKitC  │ │
│         creepage slot (milled)  ║          ║  Q1 D1║ └──────────┘ │
│                                 ║          ║  R1   ║ SW1  LED1 H1 │
└───────────────────────────────────────────────────────────────┘
     ◄──────── ≥8 mm slot between mains copper and SELV copper ─────►
```

Placement rules:
- **All mains-referenced copper stays left of the slot.** The only things crossing
  are the HLK-PM01 transformer (inside the module) and — if you later add the opto
  option — the opto-coupler straddling the slot.
- Relay **coil pins face SELV**, **contact pins face mains** — orient K1 so the
  internal barrier lines up with the board slot.
- ESP32 antenna end **overhangs the board edge** (keep-out under the PCB antenna:
  no copper pour beneath it).
- Screw terminals J1/J2 at the board edge for wire entry; **live entry (J1) and
  switched-live exit (J2-L) on the mains side only.**

---

## 6. Isolation, creepage & clearance — the critical rules

At 230 VAC RMS (325 V peak), pollution degree 2, IEC 62368-1:

| Gap | Type | Minimum | This design |
|-----|------|---------|-------------|
| Mains L ↔ N (functional) | clearance | 2.0 mm | **2.5 mm** |
| Mains ↔ SELV (barrier) | creepage | 6.4 mm (reinforced) | **≥8.0 mm + milled slot** |
| Mains ↔ SELV (barrier) | clearance | 4.0 mm | **≥8.0 mm** |
| Fuse/MOV mains pads | creepage | 2.5 mm | 3.0 mm |

Enforcement:
- **Milled isolation slot** (routed cut-out, 1.5–2 mm wide) under the HLK-PM01 and
  under the relay, along the whole barrier. A slot increases *creepage* beyond the
  straight-line clearance and gives a visible safety boundary.
- No copper pour, silkscreen, or via inside the barrier keep-out.
- Silkscreen: hatched fill + "⚡ 230 V — HAZARDOUS" on the mains zone; a solid line
  marking the barrier.

---

## 7. Stackup, copper & trace widths

- **2-layer FR-4, 1.6 mm, but 2 oz (70 µm) copper** (or 1 oz with widened mains traces).
- Mains current path (L → F1 → K1 → J2-L), for **10 A, 10 °C rise, IPC-2221**:
  - 2 oz copper → **≥2.5 mm** trace, or
  - 1 oz copper → **≥4.0 mm** trace.
  - Use **filled copper pours** on mains traces and leave them **exposed (no
    soldermask) + reinforce with solder** to boost current capacity.
- SELV signal/power traces: 0.3–0.5 mm is ample (logic-level, <0.6 A).
- **Star-ground the SELV zone** at the HLK-PM01 -Vo; keep the ADC bias ground
  return (R4/C3) short and away from the relay-coil switching current.
- Mounting holes: 4× M3, all in SELV or mains corners (no hole in the barrier).

---

## 8. DRC / fab spec (hand to the board house)

```
Layers:            2
Copper:            2 oz (70 µm)  [preferred]
Min trace/space:   0.25 mm (SELV);  mains per §6/§7
Min drill:         0.3 mm
Slots:             routed isolation slot, 1.5 mm (specify as board cut-out)
Finish:            HASL or ENIG
Soldermask:        both sides; mains power traces = mask opening (tinnable)
Silkscreen:        mains hazard hatch + barrier line + refdes
Board outline:     100 × 75 mm (adjust to enclosure)
```

---

## 9. Assembly & first-power sequence

1. **Populate SELV zone only.** Power the ESP32 from **USB** (not the HLK-PM01).
   Verify firmware boots, provisioning AP appears, relay driver toggles K1 (you'll
   hear the click), SCT reads current via the jack. This validates everything
   dangerous-free.
2. Populate mains zone (F1, RV1, HLK-PM01, K1 contacts, J1/J2). **Visually inspect
   the isolation slot** — no solder bridges, no stray copper.
3. First mains power **through an isolation transformer + RCD**, current-limited.
   Confirm HLK-PM01 gives clean 5 V, no arcing/heat at the barrier.
4. Confirm relay switches J2-L and the SCT (clamped on the J2-L output cable) tracks
   the load. Verify the firmware overcurrent trip fires below the fuse rating.

---

## 10. Limitations & next steps

- **Apparent power only.** No voltage sensing → `power = I × 230 V` (see firmware
  `sensor_task.cpp`). Accurate for resistive loads, high for reactive ones. Header
  **H1** reserves GPIO35 for a future ZMPT101B; adding it turns the barrier design
  into a *two* mains-referenced-sensor problem and warrants its own review.
- **SCT-013 is external** — it clamps the J2-L output cable outside the enclosure
  (matches the current jack-based design). If you want it fully internal, leave a
  short LIVE pigtail loop between K1-NO and J2-L for the clamp to close around.
- **Supply margin.** HLK-PM01 (600 mA) is adequate but not generous for WiFi bursts;
  the alt HLK-10M05 footprint is the safe upgrade.
- This is a design *specification*, not routed Gerbers. Next step is transcribing
  §3–§8 into KiCad (I can generate the netlist/symbol assignments) and a review
  pass with the `hardware-advisor` agent before you send it to a fab.
