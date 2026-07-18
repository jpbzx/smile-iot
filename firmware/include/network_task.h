#pragma once

#include <Arduino.h>

// FreeRTOS task entry point. Owns the MQTT connection lifecycle, telemetry
// publishing, and inbound command handling. Runs at lower priority than
// sensorTask and never touches the relay directly -- it only posts a
// RelayCommand through shared_state for sensorTask to apply.
void networkTask(void *pvParameters);
