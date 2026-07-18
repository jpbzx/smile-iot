#include "shared_state.h"

static SemaphoreHandle_t stateMutex = nullptr;
static SensorReading latestReading;
static RelayCommand pendingCommand = RelayCommand::NONE;

void sharedStateInit() {
    stateMutex = xSemaphoreCreateMutex();
}

void sharedStatePublishReading(const SensorReading &reading) {
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    latestReading = reading;
    xSemaphoreGive(stateMutex);
}

SensorReading sharedStateGetReading() {
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    SensorReading copy = latestReading;
    xSemaphoreGive(stateMutex);
    return copy;
}

void sharedStateRequestRelayCommand(RelayCommand cmd) {
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    pendingCommand = cmd;
    xSemaphoreGive(stateMutex);
}

RelayCommand sharedStateConsumeRelayCommand() {
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    RelayCommand cmd = pendingCommand;
    pendingCommand = RelayCommand::NONE;
    xSemaphoreGive(stateMutex);
    return cmd;
}