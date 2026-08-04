// ---------------------------------------------------------------------------
// Pinout
// ---------------------------------------------------------------------------
#define LED_PIN 2      // Built-in LED on ESP32-DevKit
#define SCT_PIN 34     // SCT-013 analog input (ADC1_CH6)
#define RELAY_PIN 25   // Outlet cutoff relay
#define BOOT_PIN 0     // BOOT button, active low — hold at reset to force re-provisioning

// ---------------------------------------------------------------------------
// ADC / sensor calibration
// ---------------------------------------------------------------------------
constexpr int ADC_RESOLUTION_BITS = 12;
constexpr int ADC_MAX_COUNTS = (1 << ADC_RESOLUTION_BITS) - 1; // 4095
constexpr float ADC_VREF = 3.3f;

// sct-013-000 needs a burden resistor 33ohm -> calib = 60.6
// sct-013-030 has the burden resistor built in -> calib = 30 (A per V)
constexpr float CT_CALIBRATION = 30.0f;

// Sampling is bounded by WALL-CLOCK TIME, not by a sample count. 100 ms is a
// whole number of cycles at both mains frequencies (5 x 50 Hz, 6 x 60 Hz), so
// the RMS estimate carries no partial-cycle (spectral leakage) error.
// A fixed sample count cannot guarantee that: the real per-sample period is
// CT_SAMPLE_SPACING_US *plus* however long analogRead() takes (~10-12 us on
// ESP32), which silently stretched the old 1000-sample window to ~1.6 cycles
// and under-reported current by roughly 5%.
constexpr uint32_t CT_SAMPLE_WINDOW_US = 100000; // 100 ms
constexpr int CT_SAMPLE_SPACING_US = 20;         // target spacing; actual is this + ADC time

constexpr float CURRENT_LIMIT_A = 15.0f; // most EU household circuits
constexpr float GRID_VOLTAGE_V = 230.0f; // assumed nominal — no voltage sensing hardware yet

// ---------------------------------------------------------------------------
// MQTT
// ---------------------------------------------------------------------------
// The LAN address of the machine running docker compose (Mosquitto). The board
// and the server talk directly over the local network -- nothing leaves the LAN.
// NOTE: this is a DHCP-assigned address. If the server's lease changes, the
// board will silently stop reaching the broker; give it a DHCP reservation (or
// a static IP) on the router to make this stable.
constexpr char MQTT_BROKER[] = "192.168.1.254";
constexpr int MQTT_PORT = 1883;
constexpr char MQTT_TOPIC_TELEMETRY[] = "smile-iot/power";
constexpr char MQTT_TOPIC_COMMAND[] = "smile-iot/command";
constexpr char MQTT_USERNAME[] = "1211189";
constexpr char MQTT_PASSWORD[] = "isep";

// ---------------------------------------------------------------------------
// WiFi provisioning
// ---------------------------------------------------------------------------
constexpr char PROVISIONING_AP_PASSWORD[] = "smile1234"; // portal AP password (min 8 chars for WPA2)
constexpr uint32_t BOOT_BUTTON_HOLD_MS = 3000;
constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;
constexpr uint8_t DNS_PORT = 53;
constexpr uint8_t NVS_SSID_MAX_LEN = 32;
constexpr uint8_t NVS_PASS_MAX_LEN = 64;

// ---------------------------------------------------------------------------
// Task scheduling
// ---------------------------------------------------------------------------
constexpr uint32_t SENSOR_TASK_STACK = 4096;
constexpr UBaseType_t SENSOR_TASK_PRIORITY = 2;
constexpr BaseType_t SENSOR_TASK_CORE = 1; // isolated from the WiFi driver task

constexpr uint32_t NETWORK_TASK_STACK = 8192;
constexpr UBaseType_t NETWORK_TASK_PRIORITY = 1;
constexpr BaseType_t NETWORK_TASK_CORE = 0; // co-located with the WiFi driver task

constexpr TickType_t SENSOR_PERIOD_MS = 1000; // matches SCT-013 ~0.5s response delay
constexpr TickType_t MQTT_RECONNECT_BACKOFF_MS = 5000;