#include "network_task.h"
#include "config.h"
#include "shared_state.h"

#include <WiFi.h>
#include <PubSubClient.h>

namespace {

void mqttCallback(char *topic, byte *payload, unsigned int length) {
    String msg;
    msg.reserve(length);
    for (unsigned int i = 0; i < length; i++) {
        msg += static_cast<char>(payload[i]);
    }

    Serial.printf("[MQTT] Command on %s: %s\n", topic, msg.c_str());

    if (msg == "ON") {
        sharedStateRequestRelayCommand(RelayCommand::TURN_ON);
    } else if (msg == "OFF") {
        sharedStateRequestRelayCommand(RelayCommand::TURN_OFF);
    } else if (msg == "RESET") {
        sharedStateRequestRelayCommand(RelayCommand::RESET_TRIP);
    }
}

void mqttReconnect(PubSubClient &client) {
    String clientId = "esp32-1-" + WiFi.macAddress();
    Serial.printf("[MQTT] Connecting as %s...\n", clientId.c_str());

    if (client.connect(clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD)) {
        Serial.println("[MQTT] Connected.");
        client.subscribe(MQTT_TOPIC_COMMAND);
    } else {
        Serial.printf("[MQTT] Connect failed, rc=%d. Retrying in %lums\n",
                      client.state(), static_cast<unsigned long>(MQTT_RECONNECT_BACKOFF_MS));
        vTaskDelay(pdMS_TO_TICKS(MQTT_RECONNECT_BACKOFF_MS));
    }
}

// Hand-rolled JSON -- payload shape is small and fixed,
// so a formatted string keeps the firmware's only external dependency
// scoped to the MQTT client itself.
void publishReading(PubSubClient &client) {
    SensorReading reading = sharedStateGetReading();

    char payload[160];
    snprintf(payload, sizeof(payload),
             "{\"current_A\":%.3f,\"power_W\":%.1f,\"voltage_V\":%.1f,\"outlet_state\":\"%s\",\"trip_latched\":%s}",
             reading.current_A,
             reading.power_W,
             GRID_VOLTAGE_V,
             reading.outlet_state ? "ON" : "OFF",
             reading.trip_latched ? "true" : "false");

    client.publish(MQTT_TOPIC_TELEMETRY, payload);
}

} // namespace

void networkTask(void *pvParameters) {
    (void)pvParameters;

    WiFiClient espClient;
    PubSubClient client(espClient);
    client.setServer(MQTT_BROKER, MQTT_PORT);
    client.setCallback(mqttCallback);

    TickType_t lastPublish = xTaskGetTickCount();

    for (;;) {
        if (WiFi.status() != WL_CONNECTED) {
            // Arduino's WiFi stack handles low-level reconnection; just wait it out.
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }

        if (!client.connected()) {
            mqttReconnect(client);
        }
        client.loop();

        TickType_t now = xTaskGetTickCount();
        if (now - lastPublish >= pdMS_TO_TICKS(SENSOR_PERIOD_MS)) {
            lastPublish = now;
            publishReading(client);
        }

        vTaskDelay(pdMS_TO_TICKS(20));
    }
}