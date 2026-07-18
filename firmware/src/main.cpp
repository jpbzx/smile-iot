#include <Arduino.h>
#include <WiFi.h>

#include "config.h"
#include "shared_state.h"
#include "provisioning.h"
#include "sensor_task.h"
#include "network_task.h"

// SMILE-IoT edge node.
//
// setup() only handles boot-time WiFi provisioning, then hands off to two
// FreeRTOS tasks (sensor_task.cpp, network_task.cpp) with explicit
// priorities/core pinning -- there is no ongoing work in loop(). Sensing and
// the overcurrent safety cutoff run on their own core at higher priority so
// they can never be delayed by MQTT/network stalls.

void setup() {
    Serial.begin(115200);
    delay(200); // let USB-serial settle before the first log lines

    bool forceProvision = bootButtonHeld(BOOT_BUTTON_HOLD_MS);
    if (forceProvision) {
        Serial.println("[Boot] BOOT button held -> clearing stored WiFi credentials.");
        clearWifiCredentials();
    }

    char ssid[NVS_SSID_MAX_LEN + 1] = {0};
    char pass[NVS_PASS_MAX_LEN + 1] = {0};
    bool haveCreds = loadWifiCredentials(ssid, sizeof(ssid), pass, sizeof(pass));

    bool connected = false;
    if (haveCreds && !forceProvision) {
        Serial.printf("[Boot] Trying stored network '%s'...\n", ssid);
        connected = connectToWifi(ssid, pass, WIFI_CONNECT_TIMEOUT_MS);
    }

    if (!connected) {
        Serial.println("[Boot] No usable stored network -- entering provisioning portal.");
        runProvisioningPortal(); // blocks; saves credentials and reboots, never returns
    }

    Serial.printf("[Boot] WiFi connected. IP: %s\n", WiFi.localIP().toString().c_str());

    sharedStateInit();

    xTaskCreatePinnedToCore(sensorTask, "sensor_safety", SENSOR_TASK_STACK, nullptr,
                             SENSOR_TASK_PRIORITY, nullptr, SENSOR_TASK_CORE);
    xTaskCreatePinnedToCore(networkTask, "network_mqtt", NETWORK_TASK_STACK, nullptr,
                             NETWORK_TASK_PRIORITY, nullptr, NETWORK_TASK_CORE);
}

void loop() {
    // All work happens in sensorTask/networkTask; the default Arduino loop
    // task has nothing left to do, so it deletes itself.
    vTaskDelete(nullptr);
}
