#include "sensor_task.h"
#include "config.h"
#include "shared_state.h"

namespace {

// Samples the SCT-013 for one AC-cycle window and returns RMS current in Amps.
//
// The ADC gives raw counts centered on a ~1.65V DC bias (mid-rail from the
// resistor divider). We compute the RMS of the AC component in counts, then
// convert counts -> volts (ADC_VREF / ADC_MAX_COUNTS) before applying the
// CT's current-per-volt calibration factor -- skipping that conversion was
// the bug in the original implementation (it applied the calibration factor
// directly to raw ADC counts).
float readCurrentRms() {
    long sum = 0;
    double sumSquared = 0.0;

    for (int i = 0; i < CT_SAMPLE_COUNT; i++) {
        int sample = analogRead(SCT_PIN);
        sum += sample;
        sumSquared += static_cast<double>(sample) * sample;
        delayMicroseconds(CT_SAMPLE_SPACING_US);
    }

    double mean = static_cast<double>(sum) / CT_SAMPLE_COUNT;
    double meanOfSquares = sumSquared / CT_SAMPLE_COUNT;
    double variance = meanOfSquares - (mean * mean);
    if (variance < 0.0) {
        variance = 0.0;
    }

    double rmsCounts = sqrt(variance);
    double rmsVolts = rmsCounts * (ADC_VREF / ADC_MAX_COUNTS);
    double currentAmps = rmsVolts * CT_CALIBRATION;

    return static_cast<float>(currentAmps);
}

} // namespace

void sensorTask(void *pvParameters) {
    (void)pvParameters;

    pinMode(RELAY_PIN, OUTPUT);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(RELAY_PIN, LOW);
    digitalWrite(LED_PIN, LOW);
    analogReadResolution(ADC_RESOLUTION_BITS);

    bool relayOn = false;
    bool tripLatched = false;

    TickType_t lastWake = xTaskGetTickCount();

    for (;;) {
        float currentA = readCurrentRms();

        RelayCommand cmd = sharedStateConsumeRelayCommand();
        switch (cmd) {
            case RelayCommand::TURN_ON:
                if (!tripLatched) {
                    relayOn = true;
                }
                break;
            case RelayCommand::TURN_OFF:
                relayOn = false;
                tripLatched = false; // an explicit OFF always clears a stale trip
                break;
            case RelayCommand::RESET_TRIP:
                tripLatched = false;
                break;
            case RelayCommand::NONE:
            default:
                break;
        }

        // Safety-critical check: runs immediately after every measurement, in
        // the same task/priority as the sampling itself, so it can never be
        // delayed by MQTT/network work.
        if (currentA > CURRENT_LIMIT_A && relayOn) {
            relayOn = false;
            tripLatched = true;
            Serial.printf("[SAFETY] Current limit exceeded (%.2f A > %.2f A). Relay tripped, latched until RESET/OFF.\n",
                          currentA, CURRENT_LIMIT_A);
        }

        digitalWrite(RELAY_PIN, relayOn ? HIGH : LOW);
        digitalWrite(LED_PIN, relayOn ? HIGH : LOW);

        SensorReading reading;
        reading.current_A = currentA;
        reading.power_W = currentA * GRID_VOLTAGE_V;
        reading.outlet_state = relayOn;
        reading.trip_latched = tripLatched;
        sharedStatePublishReading(reading);

        vTaskDelayUntil(&lastWake, pdMS_TO_TICKS(SENSOR_PERIOD_MS));
    }
}