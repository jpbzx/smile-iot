# SMILE-IoT — Bench Rig v1 (hand-wired SCT-013 monitor + switch)

> ⚠️ **This rig carries 230 V AC.** The SELV side is safe to touch; the mains
> compartment is not. Nothing here should be energised until §7 has been walked
> through, and the mains side should be reviewed by someone qualified before
> first power-on.

**Status:** design recorded 2026-08-07, **not yet built**.
**Relationship to [`PCB_DESIGN_v1.md`](PCB_DESIGN_v1.md):** same electrical
topology, built from off-the-shelf modules in a project box instead of a fabbed
board. This is the step *before* the PCB — it validates the firmware, the
calibration and the whole telemetry pipeline against a real load, so the PCB is
a layout exercise rather than a first bring-up.

---

## 1. Scope

A hand-wired box that:

- passes 230 V mains through to a controlled outlet,
- **switches the LIVE conductor** via an opto-isolated relay module (GPIO25, active-HIGH),
- senses load current with the existing **SCT-013-030** clamp on the switched live,
- powers the ESP32 from an isolated **HLK-PM01**, so the rig needs no USB brick,
- runs the existing firmware unchanged, except for the optional `CT_TURNS` constant (§6).

Out of scope: voltage sensing, real power, power factor. Grid voltage stays a
server-side configuration value (`PROJECT_GUIDE.md` §5.6).

---

## 2. Does clamping one conductor actually work?

Yes. A CT measures the **net current enclosed by its core**.

```
around both conductors:  +I (live) + −I (neutral) = 0   → reads ≈ nothing
around one conductor:    +I (live only)           = I   → reads the real current
```

In a two-wire circuit both conductors carry the same current, so **either one
works** — clamp live or neutral, the reading is identical. The only wrong answer
is clamping both.

The practical difficulty is *getting at* one conductor: in a normal flex they run
side by side inside one sheath. Three ways to solve it, cheapest first:

| Method | Cost | Notes |
|---|---|---|
| **AC line splitter accessory** | ~€18 | Moulded plug + socket that fans the conductors apart, with ×1 and ×10 clip loops already wound. Zero mains exposure, nothing to build. **Best first step.** |
| This box (§4) | ~€60 | The conductor is separated *inside* your own enclosure |
| Splitting a flex by hand | — | Don't. Cutting the outer sheath to separate cores compromises the insulation system |

---

## 3. ⚠️ Check the cable before anything else

Harmonised EU mains flex is **brown (L) / blue (N) / green-yellow (PE)**.

A **red/black two-core** cable is one of:

- **pre-2006 UK wiring** (red = L, black = N) — mains-rated, but **no earth**
- **a DC / speaker / bell cable** — **not mains-rated**, and the more likely case

Check the sheath print. It must read a cable type and voltage rating —
`H05VV-F 300/500V` or `H07RN-F 450/750V`. No print, or a different print, means
don't put mains through it.

Two-core also means **no protective earth**: acceptable for a double-insulated
Class-II load (fan heater, lamp), not acceptable for anything with a metal
chassis, and not acceptable for a metal enclosure.

**Use a ready-made `H05VV-F 3G1.5` extension lead** cut into two tails. Correct
colours, correct rating, moulded plug, ~€8.

---

## 4. Block diagram

```
   MAINS COMPARTMENT (230 VAC — HAZARDOUS)
   ┌──────────────────────────────────────────────────────────────────────┐
   │  L ──[F1 5A]──┬──[MOV]──┬── relay COM ──[K1]── relay NO ── L_out ────┼──► to
   │               │         │                                  ▲        │    load
   │  N ───────────┴─────────┴───────────────────────── N_out ──┼────────┼──►
   │  PE ──────────────────── pass-through, unswitched ─ PE_out ┼────────┼──►
   │               │                              SCT-013 clamps here    │
   │        ┌──────┴──────┐                                              │
   │        │  HLK-PM01   │  (isolated flyback)                          │
   │        └──────┬──────┘                                              │
   └───────────────┼──────────────────────────────────────────────────────┘
        ═══════════╪═══════ ISOLATION BARRIER (partition) ════════════════
   ┌───────────────┼──────────────────────────────────────────────────────┐
   │      +5V ─────┴──┬── ESP32 VIN        [C1 470µF ‖ C2 100nF on rail]   │
   │                  └── relay module VCC + JD-VCC                        │
   │      GND ────────┬── ESP32 GND                                        │
   │                  └── relay module GND                                 │
   │      GPIO25 ─────────► relay module IN                                │
   │      GPIO34 ◄──── 1.65 V bias network ◄──── 3.5 mm jack ◄── SCT-013   │
   │  SELV COMPARTMENT (5 V / 3V3 — SAFE TO TOUCH)                         │
   └───────────────────────────────────────────────────────────────────────┘
```

**What provides the isolation** (three independent barriers, all inside sealed parts):

| Barrier | Component | Rating |
|---|---|---|
| Mains → 5 V rail | HLK-PM01 flyback transformer | ~3 kV |
| Mains → relay control | K1 coil-to-contact gap | ≥3 kV |
| Mains → measurement | SCT-013 magnetic coupling (no galvanic path) | inherent |

The ESP32 never has a conductive path to mains. That is what makes the SELV side
safe to probe with a scope and safe to plug into a laptop over USB.

---

## 5. The relay module — wiring, power, and what it can switch

### 5.1 Powering it

**Power the coil from the HLK-PM01's 5 V rail, not from the ESP32's 3.3 V pin.**

The coil draws ~70–90 mA and a 5 V relay will not reliably pull in at 3.3 V. The
ESP32 DevKit's `5V`/`VIN` pin is electrically the same rail, so tapping it works —
but taking it from the PSU directly keeps ~80 mA of coil switching current out of
the dev board's traces.

```
HLK-PM01 +5V ──┬── ESP32  VIN (5V pin)
               └── relay  VCC   (JD-VCC jumper left ON)
HLK-PM01 GND ──┬── ESP32  GND
               └── relay  GND
ESP32 GPIO25 ─────► relay  IN
```

Fit **C1 470 µF across the 5 V rail**. The coil energising is a step load that
will brown out an ESP32 mid-WiFi-transmit without bulk capacitance.

### 5.2 The JD-VCC jumper

These modules have a jumper bridging `JD-VCC` to `VCC`:

| Jumper | Effect |
|---|---|
| **ON** (factory) | Coil and logic share one supply. Signal is opto-coupled; grounds are common. |
| OFF | `VCC`/`GND` = logic side, `JD-VCC` = coil side from a *separate* supply → genuine two-rail separation. |

**Leave it ON.** With a single HLK-PM01 both rails come from the same source
anyway, so removing it buys nothing. It matters only if you later add a second
isolated supply — and it is not what protects you from mains. That job belongs to
the relay's coil-to-contact barrier, which is internal to the relay and always
present.

### 5.3 ⚠️ Two gotchas when buying the module

**Active-LOW vs active-HIGH.** Most cheap blue modules are **active-LOW** (IN low
→ relay energises). The firmware is **active-HIGH** (`config.h`, GPIO25 HIGH =
on). Mismatched, the relay is inverted: the load is on whenever the ESP32 says off.

**3.3 V logic into a 5 V module.** On an active-LOW module the opto LED is
referenced to the 5 V rail. Driving IN to 3.3 V leaves ~1.7 V across the LED —
often enough to keep it partly conducting, so the relay never cleanly releases.

Both are avoided by the same purchase: get a module explicitly listed as
**"3.3 V / 5 V compatible, high/low level trigger selectable"** and set the jumper
to **high-level trigger**. ~€4, same price as the broken kind.

### 5.4 Yes — it controls the target device

The relay switches the same load whose current you're measuring.

```
L (after F1) ──► relay COM
relay NO     ──► L_out ──► [ SCT-013 clamps here ] ──► load
N, PE        ──────────── straight through, never switched
```

- **Use NO (normally open).** De-energised relay = load off, so a power cut, a
  crash, or a reset all fail to the safe state. NC would leave the load on.
- **Clamp the CT downstream of the relay.** Then opening the relay drives the
  measured current to zero, and the dashboard confirms the switch actually
  happened through telemetry — which is exactly the round-trip described in
  `PROJECT_GUIDE.md` §7.2.
- Never switch neutral or PE.

> An earlier design note recommended the **NC** contact — that applied to the
> abandoned industrial topology, where the relay interrupted a contactor's coil
> circuit to prevent unexpected restart. In this box the relay switches the load
> directly, so **NO** is correct.

### 5.5 ⚠️ Contact rating — derate it

`SRD-05VDC-SL-C` modules are printed **10 A 250 VAC**. For a €4 module treat that
as a headline, not a spec. Derate to **~5 A resistive ≈ 1150 W at 230 V**.

| Test load | Current | Safe to switch with this module? |
|---|---|---|
| 500 W halogen work light | 2.2 A | ✅ |
| 1000 W heater | 4.3 A | ✅ (at the limit) |
| **2000 W fan heater** | **8.7 A** | ❌ **exceeds it** |

Inductive and incandescent loads are worse than the RMS figure suggests —
filament cold-inrush is ~10× for a few cycles. Keep switched loads **≤1000 W**.
Larger loads can still be *measured*: leave the relay closed, or wire the load
around it.

For real 10–16 A switching, move to a proper relay (Finder 40.61, 16 A) with the
Q1/D1 driver from [`PCB_DESIGN_v1.md`](PCB_DESIGN_v1.md) §3.3 — not a module.

---

## 6. Multi-turn trick — free low-current resolution

A CT measures **ampere-turns**. Pass the conductor through the jaw *N* times and
the sensor sees *N* × the current.

At `CT_CALIBRATION = 30 A/V` with a 12-bit ADC, one count ≈ **24 mA**:

| Load @ 230 V | Current | 1 turn | 5 turns |
|---|---|---|---|
| 2000 W | 8.7 A | 360 counts ✅ | saturates — don't |
| 500 W | 2.2 A | 90 counts ✅ | 450 ✅ |
| 100 W | 0.43 A | 18 counts ⚠️ | 90 ✅ |
| 60 W lamp | 0.26 A | **11 counts** ❌ noise | 55 ✅ |

Below ~100 W a single turn is reading ADC noise. The 13 mm jaw fits roughly 5–8
turns of thin wire; a commercial line splitter has a ×10 loop already wound.

> ⚠️ **Firmware must know the turns count.** With 5 turns and no code change the
> firmware reads 5× high, so `CURRENT_LIMIT_A = 15.0` would trip at **3 A actual**.
> Add to `firmware/include/config.h`:
> ```cpp
> constexpr float CT_TURNS = 1.0f;   // conductor passes through the CT jaw N times
> ```
> and divide by it in `sensor_task.cpp:readCurrentRms()`, after the counts→volts→amps
> conversion. Keep it at `1.0f` until you actually wind turns.

---

## 7. Build order and first power-on

Never energise the mains side and the SELV side for the first time together.

1. **SELV only, USB-powered.** ESP32 + bias network + SCT-013 on the bench, no
   mains anywhere. Confirm firmware boots, the provisioning AP appears, and
   GPIO25 audibly clicks the relay. Verify the trigger polarity here — HIGH must
   mean energised.
2. **Calibrate with no box.** Line splitter → load → clamp meter on the same
   conductor. Compare the clamp meter against `pio device monitor`. This closes
   the open item in `PROJECT_GUIDE.md` §6.8 and needs no enclosure at all.
3. **Wire the mains compartment**, box unpowered and unplugged. Fuse, MOV,
   HLK-PM01, relay contacts, terminals, glands, strain relief. Visually inspect
   every joint; nothing exposed with the lid off.
4. **HLK-PM01 alone.** Mains in, SELV side disconnected. Confirm clean 5 V, no
   heat or arcing at the barrier. Then power down and connect the SELV side.
5. **Full rig into a resistive load ≤1000 W**, on an **RCD-protected** socket.
   Confirm the relay switches, the CT tracks, and telemetry reaches InfluxDB.

Mains-side rules while wiring:

- ≥8 mm creepage between anything mains and anything SELV — a solid partition,
  not "different corners of the box". Full spacing table in
  [`PCB_DESIGN_v1.md`](PCB_DESIGN_v1.md) §6.
- **Separate cable glands** for the mains tails and the CT cable. Never share.
- Strain relief on both mains tails.
- Plastic enclosure. If metal, PE-bond it — which then requires three-core cable.
- Fuse the incoming live. The wall breaker protects the building's wiring, not this box.

---

## 8. Bill of materials

Prices indicative EUR incl. VAT. EU sources: Amazon.es/.de, [Mauser](https://mauser.pt),
[Botnroll](https://botnroll.com), RS Components PT, Farnell PT.

### Already covered by [`hardware_README.md`](hardware_README.md)

| Qty | Part | Purpose |
|---|---|---|
| 1 | ESP32 DevKit V1 | MCU |
| 1 | SCT-013-030 (30 A / 1 V) | Current sensing |
| 2 | 10 kΩ 1% resistor | 1.65 V bias divider |
| 1 | 10 µF electrolytic | Bias rail decoupling |
| 1 | 3.5 mm audio jack breakout | Mates the SCT-013 plug |

### To buy — power

| Qty | Part | ~€ ea | ~€ |
|---|---|---|---|
| 1 | **Hi-Link HLK-PM01** — 230 VAC → 5 V 3 W, isolated | 5.00 | 5.00 |
| 1 | 470 µF / 16 V electrolytic (C1, bulk) | 0.50 | 0.50 |
| 2 | 100 nF ceramic X7R 50 V (C2, rail decoupling) | 0.25 | 0.50 |

> HLK-PM01 is 600 mA at 5 V. ESP32 WiFi-TX peaks ~350 mA + relay coil ~80 mA
> ≈ 430 mA — it fits, but only with C1 fitted. For headroom use **HLK-10M05**
> (2 A), pin-compatible, ~€7.

### To buy — switching

| Qty | Part | ~€ ea | ~€ |
|---|---|---|---|
| 1 | 1-ch opto-isolated relay module, 5 V coil, **3.3 V compatible, high/low trigger selectable** | 4.00 | 4.00 |

### To buy — mains protection & wiring

| Qty | Part | ~€ ea | ~€ |
|---|---|---|---|
| 1 | Panel fuse holder, 5×20 mm, 250 V | 3.00 | 3.00 |
| 5 | Fuse 5 A slow-blow, 5×20 mm, 250 V | 0.40 | 2.00 |
| 1 | MOV S14K275 (275 VAC surge clamp) | 1.00 | 1.00 |
| 2 | Screw terminal block, 3-way, 250 V / 16 A | 2.00 | 4.00 |
| 2 | Cable gland M16 with strain relief | 1.50 | 3.00 |

> 5 A, not the PCB's 10 A — sized to the derated relay module (§5.5).

### To buy — enclosure & mechanical

| Qty | Part | ~€ ea | ~€ |
|---|---|---|---|
| 1 | ABS project box ≥150×110×70 mm, IP54+ | 12.00 | 12.00 |
| 1 | ABS/polycarbonate sheet 2 mm (isolation partition) | 3.00 | 3.00 |
| 1 | M3 nylon standoff + screw assortment | 5.00 | 5.00 |

### To buy — cabling

| Qty | Part | ~€ ea | ~€ |
|---|---|---|---|
| 1 | **H05VV-F 3G1.5 extension lead** (cut into two tails) | 8.00 | 8.00 |
| — | Ferrules / crimp terminals + heatshrink | — | 6.00 |
| — | 22 AWG hookup wire (SELV side) | — | 4.00 |

**Build subtotal ≈ €61**

### Test & calibration — not optional

| Qty | Part | ~€ ea | ~€ |
|---|---|---|---|
| 1 | True-RMS clamp meter (UNI-T UT210E or equiv.) | 35.00 | 35.00 |
| 1 | Resistive load, 500–1000 W (halogen work light) | 15.00 | 15.00 |
| 1 | AC line splitter, ×1 / ×10 loops (UNI-T UT-L1 or generic) | 18.00 | 18.00 |

**Test subtotal ≈ €68 · Grand total ≈ €129**

You cannot calibrate a current sensor without a reference instrument. The clamp
meter is the single most valuable item on this list.

---

## 9. Bring-up validation

Heater on, clamp meter on the same conductor, compared against serial output:

| Observation | Meaning |
|---|---|
| 500 W load reads **~2.2 A**, within ~5% of the clamp meter | ✅ calibration good |
| Reads ≈ 0 | CT around both conductors, or jaw not fully closed |
| Reads ~5× high | turns wound without setting `CT_TURNS` (§6) |
| Reads ~1241× high | the counts→volts step is missing (`PROJECT_GUIDE.md` §6.4) |
| Relay inverted vs. dashboard | module is active-LOW (§5.3) |

Then confirm the full chain: relay opens → CT reads zero → `outlet_state: "OFF"`
lands in InfluxDB → the dashboard chip flips.

---

## 10. What this rig cannot do

- **No voltage measurement.** Power stays `current_A × configured_voltage`, i.e.
  apparent power ignoring power factor. See `PROJECT_GUIDE.md` §5.6.
- **No power factor, no frequency, no on-device energy accumulation.**
- **≤1000 W switched**, limited by the relay module (§5.5).
- **Poor below ~100 W** on a single turn — use turns (§6) or accept the noise floor.
- **Single device.** Multi-plug needs the topic-per-device refactor, not a hardware change.
