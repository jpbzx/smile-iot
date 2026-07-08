#pragma once

#include <Arduino.h>

// FreeRTOS task entry point. Owns ADC sampling, RMS calculation, and the
// overcurrent safety trip. Runs at higher priority than networkTask and is
// pinned to its own core so a stalled WiFi/MQTT stack can never delay the
// cutoff decision.
void sensorTask(void *pvParameters);