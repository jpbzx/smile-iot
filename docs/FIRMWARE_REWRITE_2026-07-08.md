# Firmware Rewrite: FreeRTOS Task Architecture + WiFi Provisioning

**Date created:** 2026-07-08
**Author context:** jpbzx (via pair-programming session)

**Files changed:**

| File | Change |
|---|---|
| `firmware/src/main.cpp` | Rewritten — was a single `setup()`/`loop()` sketch, now boots WiFi then spawns two FreeRTOS tasks |
| `firmware/include/config.h` | **New** — all pins, calibration, MQTT, provisioning, and task-scheduling constants |
| `firmware/include/shared_state.h` | **New** — cross-task data contract (declarations only) |
| `firmware/src/shared_state.cpp` | **New** — mutex-protected shared state implementation |
| `firmware/include/sensor_task.h` | **New** — sensor/safety task entry point declaration |
| `firmware/src/sensor_task.cpp` | **New** — ADC sampling, RMS calculation, overcurrent trip logic |
| `firmware/include/network_task.h` | **New** — network/MQTT task entry point declaration |
| `firmware/src/network_task.cpp` | **New** — MQTT connect/reconnect, publish, inbound command handling |
| `firmware/include/provisioning.h` | **New** — WiFi provisioning API declarations |
| `firmware/src/provisioning.cpp` | **New** — SoftAP + captive portal + NVS credential storage |
| `firmware/platformio.ini` | Modified — dropped `ArduinoJson` and the dead `EmonLib` reference, kept only `pubsubclient` |

---

## 1. Why this rewrite happened

The original `main.cpp` was a classic Arduino sketch: one `loop()` function doing WiFi/MQTT housekeeping, a ~20ms blocking ADC sampling burst, and a safety check, all serialized on a single default FreeRTOS task (`loopTask`, priority 1, core 1) that the Arduino core creates for you. Two problems with that shape, given this device's job:

1. **No priority separation.** If `client.loop()` or a reconnect attempt ever blocks or takes a while, the overcurrent check that follows it in the same `loop()` iteration is delayed by exactly that much. For a device whose whole justification is "trip the relay before something bad happens," that coupling is the wrong risk to take.
2. **Not actually using what FreeRTOS gives you.** The Arduino framework on ESP32 *is* FreeRTOS underneath — `loop()` is just one task among others the scheduler already runs (WiFi driver task, `loopTask`, etc.). Writing everything into `loop()` ignores that and forces sensing and networking to interleave on the same priority/core by accident rather than by design.

The fix: split the work into two explicit FreeRTOS tasks with different priorities and different CPU cores, connected only through a small mutex-guarded shared-state module. Sensing/safety gets deterministic priority; networking gets whatever's left.

---

## 2. Architecture overview

```
                    ┌─────────────────────────┐
                    │        setup()          │
                    │  (runs once, on boot)   │
                    │                         │
                    │ 1. bootButtonHeld()     │
                    │ 2. loadWifiCredentials()│
                    │ 3. connectToWifi() OR   │
                    │    runProvisioningPortal│
                    │ 4. sharedStateInit()    │
                    │ 5. xTaskCreatePinned... │
                    │    x2                   │
                    └───────────┬─────────────┘
                                │
                 ┌──────────────┴───────────────┐
                 ▼                               ▼
      ┌─────────────────────┐         ┌──────────────────────┐
      │     sensorTask       │         │     networkTask       │
      │  priority 2, core 1  │         │  priority 1, core 0   │
      │                      │         │                       │
      │ loop:                │         │ loop:                 │
      │  read ADC (1000      │         │  ensure WiFi/MQTT up   │
      │   samples)            │         │  client.loop()         │
      │  compute RMS current │         │  publish latest        │
      │  consume RelayCommand│◄──cmd───│   reading periodically │
      │  apply trip logic    │         │  on message -> post    │
      │  drive relay+LED     │         │   RelayCommand          │
      │  publish reading  ───┼──state─►│                         │
      │  vTaskDelayUntil()   │         │  vTaskDelay(20ms)       │
      └─────────────────────┘         └──────────────────────┘
                 │                               │
                 └───────────┬───────────────────┘
                              ▼
                  shared_state.cpp (one mutex,
                  SensorReading + RelayCommand)
```

`loop()` itself still exists (the Arduino core requires it to be defined), but it runs exactly once and then calls `vTaskDelete(nullptr)` to delete itself — after that point the only code running is `sensorTask` and `networkTask`, plus whatever background tasks the ESP-IDF/Arduino core itself owns (WiFi driver, idle tasks, etc.).

---

## 3. `firmware/include/config.h` — centralized constants

Previously all constants (`calib`, `CURRENT_LIMIT`, pin numbers, MQTT broker/topic/credentials) were scattered as loose globals at the top of `main.cpp`. They're now grouped by concern in one header, using `constexpr` instead of `#define` or bare `const` where possible:

```cpp
constexpr float CT_CALIBRATION = 30.0f;
constexpr int CT_SAMPLE_COUNT = 1000;
```

**Why `constexpr` over `#define`:** `#define` is a textual substitution done by the preprocessor — it has no type, doesn't respect scope, and produces confusing compiler errors if misused. `constexpr` is a real, typed, compile-time constant that participates in normal C++ name lookup and type checking. Pin numbers (`LED_PIN`, `SCT_PIN`, etc.) were left as `#define` because that's the idiom the Arduino ecosystem (and most example code you'll find for this hardware) uses, and because some Arduino core macros expect a raw preprocessor token in that position — mixing conventions here isn't a bug, it's matching each constant's actual usage site.

New constants added in this rewrite that didn't exist before:
- `ADC_VREF`, `ADC_MAX_COUNTS` — needed for the calibration fix (see §5).
- `BOOT_PIN`, `PROVISIONING_AP_PASSWORD`, `BOOT_BUTTON_HOLD_MS`, `WIFI_CONNECT_TIMEOUT_MS`, `DNS_PORT`, `NVS_SSID_MAX_LEN`, `NVS_PASS_MAX_LEN` — provisioning.
- `SENSOR_TASK_STACK`, `SENSOR_TASK_PRIORITY`, `SENSOR_TASK_CORE`, `NETWORK_TASK_STACK`, `NETWORK_TASK_PRIORITY`, `NETWORK_TASK_CORE`, `SENSOR_PERIOD_MS`, `MQTT_RECONNECT_BACKOFF_MS` — task scheduling.

Note the types used for the FreeRTOS-facing constants: `UBaseType_t` for priorities, `BaseType_t` for core IDs, `TickType_t` for tick-based durations. These are the actual FreeRTOS types the task-creation and delay APIs expect — using them (instead of, say, `int`) means the compiler will flag a mismatch if one of these constants is ever passed to the wrong argument.

---

## 4. `firmware/include/shared_state.h` / `shared_state.cpp` — the only channel between tasks

### The data contract

```cpp
struct SensorReading {
    float current_A = 0.0f;
    float power_W = 0.0f;
    bool outlet_state = false;
    bool trip_latched = false;
};

enum class RelayCommand {
    NONE,
    TURN_ON,
    TURN_OFF,
    RESET_TRIP,
};
```

`SensorReading` flows **sensorTask → networkTask** (the latest measurement, for MQTT publishing). `RelayCommand` flows **networkTask → sensorTask** (a request originating from an inbound MQTT message, e.g. `"ON"`).

`enum class` (a "scoped enum," C++11) is used instead of a plain `enum` so the values (`RelayCommand::TURN_ON`, etc.) don't leak into the surrounding namespace and can't accidentally compare equal to an unrelated integer or another enum's members. It costs nothing at runtime — this is a compile-time-only safety improvement.

### Why a mutex, not just `volatile`

The original firmware was single-task, so `bool relay_state` as a plain global was fine — there was only ever one thread of execution touching it. Now, `sensorTask` runs on core 1 and `networkTask` runs on core 0 — genuinely concurrent, on different physical cores, not just time-sliced on one core. `volatile` only tells the compiler "don't cache this in a register, always re-read from memory" — it says nothing about atomicity or memory ordering across cores, and a `SensorReading` struct is 4 fields wide, so a "torn read" (one task reading some old fields and some new fields mid-update by the other task) is a real possibility without synchronization.

`shared_state.cpp` uses a single `SemaphoreHandle_t` created via `xSemaphoreCreateMutex()` to guard **both** the reading and the pending command:

```cpp
static SemaphoreHandle_t stateMutex = nullptr;
static SensorReading latestReading;
static RelayCommand pendingCommand = RelayCommand::NONE;

void sharedStatePublishReading(const SensorReading &reading) {
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    latestReading = reading;
    xSemaphoreGive(stateMutex);
}
```

`xSemaphoreTake(handle, portMAX_DELAY)` blocks the calling task until the mutex is available, then acquires it; `portMAX_DELAY` means "wait forever" (there's no scenario here where giving up on the lock is the right behavior — both tasks hold it only for a few field copies, never across a blocking call, so contention is always brief). `xSemaphoreGive` releases it. Every accessor function in this file takes the mutex, does a plain struct copy (cheap — a handful of floats/bools), and releases it immediately; no accessor ever does I/O or blocking work while holding the lock, which is what keeps contention bounded.

`sharedStateGetReading()` and `sharedStateConsumeRelayCommand()` **return copies**, not references or pointers — this is deliberate. If they returned a pointer into `latestReading`, the caller could read it after releasing the mutex, racing the next write. Returning by value means the copy happens *inside* the locked section, and what the caller holds afterward is entirely their own.

`sharedStateConsumeRelayCommand()` also **clears** `pendingCommand` back to `NONE` as part of the same locked operation:

```cpp
RelayCommand sharedStateConsumeRelayCommand() {
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    RelayCommand cmd = pendingCommand;
    pendingCommand = RelayCommand::NONE;
    xSemaphoreGive(stateMutex);
    return cmd;
}
```

This makes it a proper single-slot mailbox: `sensorTask` calling this once per loop iteration is guaranteed to see each command exactly once, never reprocess a stale command from three iterations ago, and never miss one that arrived between iterations (it's still sitting in `pendingCommand` until consumed).

---

## 5. `firmware/src/sensor_task.cpp` — sampling, RMS math, and the safety trip

### RMS calculation, and the calibration bug that got fixed

The sampling loop itself is unchanged from the previous version — it still takes `CT_SAMPLE_COUNT` (1000) raw `analogRead()` samples spaced `CT_SAMPLE_SPACING_US` (20µs) apart, computes the mean (the ADC's DC bias point, ~1.65V/half-scale) and the mean of squares, derives variance (`E[x²] − E[x]²`), and takes the square root to get the RMS value **in raw ADC counts**:

```cpp
double mean = static_cast<double>(sum) / CT_SAMPLE_COUNT;
double meanOfSquares = sumSquared / CT_SAMPLE_COUNT;
double variance = meanOfSquares - (mean * mean);
if (variance < 0.0) variance = 0.0;   // guards against float rounding producing a tiny negative
double rmsCounts = sqrt(variance);
```

The bug: the previous code then did `currentAmps = rmsCounts * calib;` directly. `rmsCounts` is a raw 0–4095 ADC count, not a voltage — the CT's "30A/1V" calibration factor is defined in terms of **volts** at the sensor, not ADC counts. The fix inserts the missing conversion step:

```cpp
double rmsVolts = rmsCounts * (ADC_VREF / ADC_MAX_COUNTS);  // counts -> volts, e.g. 3.3V / 4095
double currentAmps = rmsVolts * CT_CALIBRATION;              // volts -> amps, 30 A per V
```

Concretely: the old code's output was too large by a factor of `ADC_MAX_COUNTS / ADC_VREF` ≈ 1241× (since it was effectively treating each ADC count as if it were one volt). A real reading of, say, 2A would have been reported as roughly 2482A — nowhere near the `CURRENT_LIMIT_A` check's expected range, meaning the safety trip could never have fired correctly in practice with the old formula, since real currents would never approach a threshold that's only reachable by fictitiously huge readings, or conversely, could trip on completely nominal current depending on how numbers landed. Either way it was silently wrong.

### The safety trip, and why it's *inline*

```cpp
if (currentA > CURRENT_LIMIT_A && relayOn) {
    relayOn = false;
    tripLatched = true;
    Serial.printf("[SAFETY] Current limit exceeded ...");
}
```

This check runs in the same task, same priority, same loop iteration as the measurement that feeds it — there is no queue, no cross-task hop, no dependency on `networkTask` being alive or MQTT being connected, between "we just measured an overcurrent condition" and "the relay pin physically goes low." That's the entire point of separating this task from networking: nothing network-related can add latency to this path.

### The trip latch (new behavior, not in the original)

The original firmware had a gap: once tripped, `relay_state` was simply `false`. If a new `"ON"` MQTT message arrived afterward (e.g. a stale/queued command, or a naive dashboard retry), the callback would set `relay_state = true` again unconditionally — silently re-closing the relay onto a circuit that had just been flagged as overcurrent, with the only protection being that it would take another full ~1s sampling window to trip again. For a device whose stated job includes preventing fires, a trip that clears itself on the next arbitrary "ON" is not a safety feature.

The rewrite adds a `bool tripLatched` local to `sensorTask` (mirrored into the published `SensorReading.trip_latched` field so the dashboard can see it) and a small state machine driven by the consumed `RelayCommand`:

```cpp
switch (cmd) {
    case RelayCommand::TURN_ON:
        if (!tripLatched) relayOn = true;   // ON is refused while latched
        break;
    case RelayCommand::TURN_OFF:
        relayOn = false;
        tripLatched = false;                // explicit OFF always clears a stale trip
        break;
    case RelayCommand::RESET_TRIP:
        tripLatched = false;                // clears the latch WITHOUT turning the relay on
        break;
    case RelayCommand::NONE:
    default:
        break;
}
```

So: after a trip, the relay stays open no matter how many `"ON"` commands arrive, until either an explicit `"OFF"` (which also clears the latch — a deliberate manual power-down always resets state) or a new `"RESET"` command (clears the latch but leaves the relay off — the operator has to send a *second*, deliberate `"ON"` afterward to re-energize). This is a two-step re-arm by design: acknowledging a fault and re-energizing the circuit are different decisions and now require different messages.

### `vTaskDelayUntil` instead of a fixed `delay()`

```cpp
TickType_t lastWake = xTaskGetTickCount();
for (;;) {
    // ... sampling (~20ms) + logic (negligible) ...
    vTaskDelayUntil(&lastWake, pdMS_TO_TICKS(SENSOR_PERIOD_MS));
}
```

`vTaskDelayUntil` computes the delay as "however long is left until `lastWake + period`," and updates `lastWake` to the new target — as opposed to `vTaskDelay`/`delay()`, which always wait the *full* requested duration regardless of how long the preceding work took. Given the sampling burst itself takes a variable ~20ms depending on scheduler jitter, `vTaskDelayUntil` keeps the loop's overall cadence locked to a steady 1-per-`SENSOR_PERIOD_MS` (1 second) instead of slowly drifting later every iteration.

---

## 6. `firmware/src/network_task.cpp` — MQTT, decoupled from sensing

`networkTask` owns a `WiFiClient` and `PubSubClient` locally (not shared globally — only this task ever touches the MQTT client object, so no locking is needed around it).

### Reconnect logic

```cpp
void mqttReconnect(PubSubClient &client) {
    String clientId = "esp32-1-" + WiFi.macAddress();
    if (client.connect(clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD)) {
        client.subscribe(MQTT_TOPIC_COMMAND);
    } else {
        vTaskDelay(pdMS_TO_TICKS(MQTT_RECONNECT_BACKOFF_MS));
    }
}
```

Functionally the same retry-with-backoff idea as the original `mqtt_reconnect()`, but two changes: it's no longer a `while (!client.connected())` loop that blocks this task indefinitely on its own (the outer `networkTask` `for (;;)` loop already retries every iteration, so a single attempt per call is enough — it naturally becomes an outer retry loop instead of a nested one), and the backoff delay is `vTaskDelay` (yields the CPU to other tasks/the scheduler) rather than the original `delay()` (which is a busy/blocking wait implemented on top of `vTaskDelay` in the Arduino-ESP32 core anyway, but expressing it directly in FreeRTOS terms here is more consistent with the rest of the task).

### Publishing — hand-rolled JSON

```cpp
char payload[160];
snprintf(payload, sizeof(payload),
         "{\"current_A\":%.3f,\"power_W\":%.1f,\"voltage_V\":%.1f,\"outlet_state\":\"%s\",\"trip_latched\":%s}",
         reading.current_A, reading.power_W, GRID_VOLTAGE_V,
         reading.outlet_state ? "ON" : "OFF",
         reading.trip_latched ? "true" : "false");
client.publish(MQTT_TOPIC_TELEMETRY, payload);
```

The previous firmware used `ArduinoJson` (`JsonDocument` + `serializeJson`) to build the MQTT payload. This project's stated constraint is that MQTT (`pubsubclient`) should be the *only* external firmware dependency — `ArduinoJson`, however small, was a second one. Since the payload shape is small, flat, and fixed (five fields, no nesting, no arrays), a `snprintf` format string is a complete, correct substitute: no heap allocation, no dynamic document sizing, and the field types are all trivially formattable (`%f`-family for floats, fixed string literals for the two enum-like fields). This is the sense in which the firmware is now "closer to raw C++" — the JSON construction has no dependency beyond the C standard library's `stdio.h`.

Note the payload now also includes `voltage_V` and `trip_latched`, neither of which the old firmware sent. `voltage_V` is currently always `GRID_VOLTAGE_V` (the assumed-nominal 230V constant from `config.h`) since there's no voltage-sensing hardware yet (see the SCT-013 investigation — a CT cannot measure voltage; that needs a separate isolated sensor, a follow-up hardware task). `trip_latched` lets the dashboard distinguish "relay is off because nobody turned it on" from "relay is off because it tripped and is waiting for an explicit reset."

### Inbound commands

```cpp
void mqttCallback(char *topic, byte *payload, unsigned int length) {
    String msg;
    for (unsigned int i = 0; i < length; i++) msg += static_cast<char>(payload[i]);

    if (msg == "ON") sharedStateRequestRelayCommand(RelayCommand::TURN_ON);
    else if (msg == "OFF") sharedStateRequestRelayCommand(RelayCommand::TURN_OFF);
    else if (msg == "RESET") sharedStateRequestRelayCommand(RelayCommand::RESET_TRIP);
}
```

This callback runs on `networkTask` (PubSubClient invokes it from inside `client.loop()`). Critically, it **never touches `RELAY_PIN` or any relay state directly** — it only posts a `RelayCommand` through the shared-state mutex. `sensorTask` is the only code anywhere in the firmware that writes to the relay GPIO. This is a deliberate ownership rule, not an accident of how the code happened to get split: exactly one task decides the physical output pin state, and it does so only after applying the safety/latch logic in §5. `"RESET"` is a new command that didn't exist in the original firmware — it exists solely to clear `tripLatched` (see the trip-latch state machine above).

### The 20ms idle delay

```cpp
vTaskDelay(pdMS_TO_TICKS(20));
```

At the bottom of the loop, this yields the CPU briefly on every iteration (whether or not a publish happened that iteration). Without it, an `networkTask` with nothing blocking it (WiFi connected, MQTT connected, not yet time to publish) would spin as fast as the scheduler allows, burning CPU on core 0 for no benefit — 20ms is short enough that `client.loop()` (which needs to service incoming MQTT packets/keepalives promptly) still runs frequently, but long enough to not matter for a device publishing once a second.

---

## 7. `firmware/src/provisioning.cpp` — WiFi captive portal

This is entirely new — the original firmware had `ssid`/`pwd` as hardcoded `const char*` globals.

### Boot flow (implemented across `provisioning.cpp` + `main.cpp`)

```
power-on / reset
      │
      ▼
bootButtonHeld(3000ms)?  ──yes──► clearWifiCredentials()
      │no                              │
      ▼                                ▼
loadWifiCredentials() found?  ◄────────┘
      │
   ┌──yes──────────────┐   no / forced
   ▼                    │        │
connectToWifi()          │        │
(15s timeout)             │        │
   │                      │        │
 success?                 │        │
   │yes          │no◄─────┴────────┘
   ▼               ▼
proceed to    runProvisioningPortal()
create tasks   (blocks until form submit,
                saves creds, ESP.restart())
```

### `bootButtonHeld()` — forcing re-provisioning

```cpp
bool bootButtonHeld(uint32_t holdMs) {
    pinMode(BOOT_PIN, INPUT_PULLUP);
    if (digitalRead(BOOT_PIN) != LOW) return false;
    uint32_t start = millis();
    while (digitalRead(BOOT_PIN) == LOW) {
        if (millis() - start >= holdMs) return true;
        delay(20);
    }
    return false;
}
```

`BOOT_PIN` is GPIO0, the same pin every ESP32 DevKit's "BOOT" button is wired to (it's also the pin that must be pulled low to enter the bootloader's flashing mode — reusing it as a user-provisioning button is standard practice on this hardware since it's already broken out and doesn't need extra wiring). `INPUT_PULLUP` means the pin reads `HIGH` when untouched and `LOW` when the button is physically pressed (it shorts the pin to ground). This function is called once at the very start of `setup()`, before WiFi/tasks exist, so it's simple polling with plain `delay()` — there's no task-scheduling concern yet at this point in boot.

### NVS storage via `Preferences`

```cpp
bool loadWifiCredentials(char *ssidOut, size_t ssidLen, char *passOut, size_t passLen) {
    prefs.begin("wifi", true); // true = read-only
    size_t ssidBytes = prefs.getString("ssid", ssidOut, ssidLen);
    prefs.getString("pass", passOut, passLen);
    prefs.end();
    return ssidBytes > 0;
}
```

`Preferences` is the Arduino-ESP32 core's wrapper around NVS (Non-Volatile Storage) — a key-value store living in a dedicated flash partition, designed for exactly this kind of small persistent settings data, and it survives power loss/reflashing of the application partition. `prefs.begin("wifi", true)` opens (or creates) a namespace called `"wifi"`; the `true` flag opens it read-only, which matters here because `loadWifiCredentials` should never be able to accidentally write. Saving (`runProvisioningPortal`, at the end) opens the same namespace with `false` (read-write) and calls `putString` for both keys.

### `connectToWifi()` — bounded-time connection attempt

```cpp
bool connectToWifi(const char *ssid, const char *pass, uint32_t timeoutMs) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, pass);
    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - start >= timeoutMs) return false;
        delay(250);
    }
    return true;
}
```

The original firmware's `wifi_connection()` looped forever (`while (WiFi.status() != WL_CONNECTED) { delay(1000); }`) — if the stored network was ever out of range, mistyped, or the router's password changed, the device would hang at boot forever with no way to recover short of re-flashing. The rewrite bounds this to `WIFI_CONNECT_TIMEOUT_MS` (15s) and, on failure, `main.cpp` falls through to `runProvisioningPortal()` automatically — the device self-heals into a recoverable state instead of bricking itself at boot.

### The captive portal itself

Three bundled ESP32-core components are composed here, none of them the project's one allowed external dependency:

- **`WiFi.h` (`WiFi.softAP(...)`)** — brings up the ESP32 as its own access point, `SMILE-IoT-XXXXXX` where `XXXXXX` is the last 3 bytes of the device's MAC address (via `WiFi.macAddress()`), so multiple devices provisioned in the same room don't collide on SSID. The AP is password-protected (`PROVISIONING_AP_PASSWORD`) — WPA2 requires at least 8 characters, hence the placeholder `"smile1234"`.
- **`DNSServer.h` (`dnsServer.start(DNS_PORT, "*", apIP)`)** — a wildcard DNS resolver: *any* hostname a connected phone/laptop looks up resolves to the ESP32's own AP IP (`192.168.4.1` by default). This is what makes phones/laptops pop up a "Sign in to network" captive-portal prompt automatically, the same UX pattern hotel/airport WiFi uses.
- **`WebServer.h` (`server.on(...)`, `server.onNotFound(...)`)** — a small synchronous HTTP server. `server.onNotFound(handleRoot)` means *any* path the OS's captive-portal detector probes (`/generate_204`, `/hotspot-detect.html`, etc. — every OS uses a different one) gets served the same provisioning page instead of a 404, which is what reliably triggers the captive-portal popup across different phones/laptops without hand-enumerating every OS's specific probe URL.

```cpp
void handleSave() {
    String ssid = server.arg("ssid_manual");
    if (ssid.length() == 0) ssid = server.arg("ssid_select");
    String pass = server.arg("pass");

    if (ssid.length() == 0 || ssid.length() > NVS_SSID_MAX_LEN || pass.length() > NVS_PASS_MAX_LEN) {
        server.send(400, "text/plain", "Invalid SSID/password length.");
        return;
    }
    strncpy(submittedSsid, ssid.c_str(), sizeof(submittedSsid) - 1);
    submittedSsid[sizeof(submittedSsid) - 1] = '\0';
    // ... same for pass ...
    server.send(200, "text/html", "...Saved. Rebooting...");
    credentialsSubmitted = true;
}
```

The form offers **both** a dropdown (populated from `WiFi.scanNetworks()`, showing each SSID with its RSSI in dBm) and a manual text field, and the manual field takes precedence if non-empty — this covers hidden networks (which don't appear in a scan) without forcing every user through manual entry. Length validation guards the fixed-size `char` buffers (`submittedSsid[NVS_SSID_MAX_LEN + 1]`) against overflow — `strncpy` plus an explicit trailing `'\0'` is used rather than trusting the source string's length, since `strncpy` does not guarantee null-termination if the source is exactly as long as the buffer.

`credentialsSubmitted` is a `volatile bool` used as the exit condition for the portal's blocking loop:

```cpp
while (!credentialsSubmitted) {
    dnsServer.processNextRequest();
    server.handleClient();
    delay(5);
}
delay(500); // let the HTTP response flush before tearing the AP down
prefs.begin("wifi", false);
prefs.putString("ssid", submittedSsid);
prefs.putString("pass", submittedPass);
prefs.end();
ESP.restart();
```

`volatile` is sufficient here (unlike the cross-core `SensorReading`/`RelayCommand` case in §4) because this is single-task, single-core, synchronous code — `handleSave()` and this loop both run on whichever task called `runProvisioningPortal()` (the Arduino main/setup task), never concurrently with each other. There's no race to guard against, just a need to tell the compiler not to optimize the flag into a register and never re-read it.

Everything in `provisioning.cpp` outside the public functions declared in `provisioning.h` (the `Preferences`/`DNSServer`/`WebServer` objects, the page-building helpers, the callbacks, `submittedSsid`/`submittedPass`/`credentialsSubmitted`) is wrapped in an anonymous `namespace { ... }`. This gives all of it internal linkage — it cannot be referenced from any other `.cpp` file, even accidentally, which is the C++ equivalent of marking everything `static` at file scope but is the more idiomatic modern-C++ way to express "this is private to this translation unit."

---

## 8. `firmware/src/main.cpp` — boot sequence and task handoff

```cpp
void setup() {
    Serial.begin(115200);
    delay(200);

    bool forceProvision = bootButtonHeld(BOOT_BUTTON_HOLD_MS);
    if (forceProvision) clearWifiCredentials();

    char ssid[NVS_SSID_MAX_LEN + 1] = {0};
    char pass[NVS_PASS_MAX_LEN + 1] = {0};
    bool haveCreds = loadWifiCredentials(ssid, sizeof(ssid), pass, sizeof(pass));

    bool connected = false;
    if (haveCreds && !forceProvision) {
        connected = connectToWifi(ssid, pass, WIFI_CONNECT_TIMEOUT_MS);
    }
    if (!connected) {
        runProvisioningPortal(); // never returns on this boot
    }

    sharedStateInit();

    xTaskCreatePinnedToCore(sensorTask, "sensor_safety", SENSOR_TASK_STACK, nullptr,
                             SENSOR_TASK_PRIORITY, nullptr, SENSOR_TASK_CORE);
    xTaskCreatePinnedToCore(networkTask, "network_mqtt", NETWORK_TASK_STACK, nullptr,
                             NETWORK_TASK_PRIORITY, nullptr, NETWORK_TASK_CORE);
}

void loop() {
    vTaskDelete(nullptr);
}
```

Reading `xTaskCreatePinnedToCore`'s arguments left to right, for the sensor task: the function to run (`sensorTask`), a human-readable name for debugging (`"sensor_safety"` — shows up in tools like `vTaskList()` or the IDF monitor), the stack size in bytes (`SENSOR_TASK_STACK` = 4096 — sized generously since the sampling loop uses local `double` accumulators and `Serial.printf` format buffers), a parameter pointer passed into the task function (`nullptr` — neither task needs one, both read everything they need from `config.h` constants and `shared_state`), the priority (`SENSOR_TASK_PRIORITY` = 2, higher than `networkTask`'s 1 — under FreeRTOS's default scheduler, a higher-priority ready task always preempts a lower-priority one), an output handle pointer (`nullptr` — nothing in this firmware ever needs to reference the task after creation, e.g. to delete or suspend it, so there's no need to capture its `TaskHandle_t`), and the core to pin it to (`SENSOR_TASK_CORE` = 1).

**Why pin to specific cores at all**, rather than letting the scheduler place tasks freely: the ESP32's WiFi/BT stack runs its own driver task, and Espressif's guidance (and general embedded practice) is to keep timing-sensitive work off the same core as that driver task where possible. Pinning `sensorTask` to core 1 and `networkTask` to core 0 (alongside the WiFi driver) means the sampling loop's timing is never contending with WiFi interrupt/task handling for the same core's cycles — it's a second, independent layer of isolation on top of the priority difference.

`loop()` calling `vTaskDelete(nullptr)`: passing `nullptr` (equivalently `NULL`) to `vTaskDelete` means "delete the calling task" — i.e., `loop()` deletes the very Arduino-core-provided task it's running on, the first (and only) time it's called. This is a documented, intentional pattern for Arduino-ESP32 projects that move all real work into custom-created tasks: it frees the (modest) stack memory that `loopTask` was holding, and makes it explicit in the code that `loop()` is not where anything happens.

---

## 9. `firmware/platformio.ini` — dependency change

```ini
; MQTT is the only external firmware dependency by design -- JSON payloads
; are hand-rolled (network_task.cpp) and WiFi provisioning uses WiFi.h /
; WebServer.h / DNSServer.h / Preferences.h, all bundled with the Arduino-ESP32 core.
lib_deps =
	pubsubclient
```

Removed: `bblanchon/ArduinoJson` (replaced by hand-rolled `snprintf` JSON, §6) and `openenergymonitor/EmonLib@^1.1.0` (this was already dead — a prior commit had removed the `#include <EmonLib.h>` and the `EnergyMonitor emon` object from `main.cpp` but left the library declared in `platformio.ini`, so PlatformIO was still downloading and linking against a library nothing in the source referenced).

`WiFi`, `WebServer`, `DNSServer`, and `Preferences` don't appear in `lib_deps` at all — they don't need to. They ship as part of the `arduino` framework package for the `espressif32` platform (visible as `framework-arduinoespressif32` when PlatformIO installs the toolchain), the same way `Arduino.h` itself does. Only genuinely external, separately-versioned registry packages belong in `lib_deps`.

---

## 10. Build verification

Built via PlatformIO (`pio run`) against `env:esp32dev` (platform `espressif32`, board `esp32dev`, framework `arduino`) on 2026-07-08: clean compile, no warnings, no errors.

```
RAM:   14.0% (45,868 / 327,680 bytes)
Flash: 61.1% (800,757 / 1,310,720 bytes)
```

`pio run -t compiledb` was also run to regenerate `firmware/compile_commands.json` so editor IntelliSense (clangd, VS Code's C/C++ extension, etc.) resolves the Arduino/ESP-IDF include paths correctly for the new files.

**Not yet done:** this has only been compiled, not flashed to a physical board. The provisioning portal's captive-portal popup behavior, the BOOT-button hold-to-reset flow, and the trip-latch behavior under a real overcurrent condition all still need to be exercised on real hardware before this is trusted in the field.

---

## 11. Known follow-ups (not addressed in this pass)

- `PROVISIONING_AP_PASSWORD` in `config.h` is a shared hardcoded placeholder (`"smile1234"`) — fine for bench testing, not for anything leaving the bench.
- `voltage_V` in the MQTT payload is still the assumed-nominal `GRID_VOLTAGE_V` constant, not a measurement — the SCT-013 physically cannot provide voltage (see the dedicated investigation from earlier in this session); real voltage sensing needs separate isolated hardware (ZMPT101B or an AC-AC adapter).
- No mechanism yet for a device to report/track "how many devices are connected" at the fleet level — that's a backend/dashboard concern, not firmware, but the MQTT client ID (`"esp32-1-" + MAC`) is already unique per device and usable as a fleet key when that's built.
