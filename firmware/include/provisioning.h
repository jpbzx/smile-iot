#include <Arduino.h>

// Returns true if the BOOT button (GPIO0) is held low for at least holdMs,
// checked from power-on/reset. Used to force re-provisioning on demand.
bool bootButtonHeld(uint32_t holdMs);

// Loads stored WiFi credentials from NVS into the given buffers.
// Returns false if no credentials have been saved yet.
bool loadWifiCredentials(char *ssidOut, size_t ssidLen, char *passOut, size_t passLen);

// Erases stored WiFi credentials from NVS.
void clearWifiCredentials();

// Attempts to join the given network, blocking up to timeoutMs.
// Returns true on success (WiFi is left connected, STA mode).
bool connectToWifi(const char *ssid, const char *pass, uint32_t timeoutMs);

// Blocking captive portal: brings up a SoftAP + DNS redirect + web form,
// waits for the user to submit target-network credentials, persists them
// to NVS, then reboots the device. Never returns.
void runProvisioningPortal();