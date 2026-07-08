#pragma once

#include <Arduino.h>

// Latest sensor reading, published by sensorTask and consumed by networkTask.
struct SensorReading {
    float current_A = 0.0f;
    float power_W = 0.0f;
    bool outlet_state = false;
    bool trip_latched = false;
};

// Command requested by networkTask (from an MQTT message), consumed by sensorTask.
enum class RelayCommand {
    NONE,
    TURN_ON,
    TURN_OFF,
    RESET_TRIP,
};

// All cross-task access goes through these functions — a single mutex
// protects both structs so sensorTask and networkTask never race on the
// relay/trip state across cores.
void sharedStateInit();

void sharedStatePublishReading(const SensorReading &reading);
SensorReading sharedStateGetReading();

void sharedStateRequestRelayCommand(RelayCommand cmd);
RelayCommand sharedStateConsumeRelayCommand(); // returns and clears the pending command