#include "provisioning.h"
#include "config.h"

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>

namespace {

Preferences prefs;
DNSServer dnsServer;
WebServer server(80);

volatile bool credentialsSubmitted = false;
char submittedSsid[NVS_SSID_MAX_LEN + 1];
char submittedPass[NVS_PASS_MAX_LEN + 1];

String apSsid() {
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char buf[24];
    snprintf(buf, sizeof(buf), "SMILE-IoT-%02X%02X%02X", mac[3], mac[4], mac[5]);
    return String(buf);
}

String buildPortalPage() {
    int found = WiFi.scanComplete();
    if (found == WIFI_SCAN_FAILED || found < 0) {
        found = WiFi.scanNetworks();
    }

    String options;
    for (int i = 0; i < found; i++) {
        options += "<option value=\"" + WiFi.SSID(i) + "\">" + WiFi.SSID(i) +
                   " (" + String(WiFi.RSSI(i)) + " dBm)</option>";
    }

    String page;
    page.reserve(1024 + options.length());
    page += "<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>";
    page += "<title>SMILE-IoT Setup</title></head><body style='font-family:sans-serif;max-width:420px;margin:2em auto;'>";
    page += "<h2>SMILE-IoT WiFi Setup</h2>";
    page += "<p>Choose the network this device should join.</p>";
    page += "<form action='/save' method='POST'>";
    page += "<label>Network</label><br><select name='ssid_select' style='width:100%;padding:6px;'>";
    page += options;
    page += "</select><br><br>";
    page += "<label>Or enter SSID manually</label><br>";
    page += "<input type='text' name='ssid_manual' style='width:100%;padding:6px;'><br><br>";
    page += "<label>Password</label><br>";
    page += "<input type='password' name='pass' style='width:100%;padding:6px;'><br><br>";
    page += "<button type='submit' style='width:100%;padding:10px;'>Connect</button>";
    page += "</form></body></html>";
    return page;
}

void handleRoot() {
    server.send(200, "text/html", buildPortalPage());
}

void handleSave() {
    String ssid = server.arg("ssid_manual");
    if (ssid.length() == 0) {
        ssid = server.arg("ssid_select");
    }
    String pass = server.arg("pass");

    if (ssid.length() == 0 || ssid.length() > NVS_SSID_MAX_LEN || pass.length() > NVS_PASS_MAX_LEN) {
        server.send(400, "text/plain", "Invalid SSID/password length.");
        return;
    }

    strncpy(submittedSsid, ssid.c_str(), sizeof(submittedSsid) - 1);
    submittedSsid[sizeof(submittedSsid) - 1] = '\0';
    strncpy(submittedPass, pass.c_str(), sizeof(submittedPass) - 1);
    submittedPass[sizeof(submittedPass) - 1] = '\0';

    server.send(200, "text/html",
                "<html><body style='font-family:sans-serif;text-align:center;margin-top:3em;'>"
                "<h3>Saved. Rebooting into the target network...</h3></body></html>");
    credentialsSubmitted = true;
}

} // namespace

bool bootButtonHeld(uint32_t holdMs) {
    pinMode(BOOT_PIN, INPUT_PULLUP);
    if (digitalRead(BOOT_PIN) != LOW) {
        return false;
    }
    uint32_t start = millis();
    while (digitalRead(BOOT_PIN) == LOW) {
        if (millis() - start >= holdMs) {
            return true;
        }
        delay(20);
    }
    return false;
}

bool loadWifiCredentials(char *ssidOut, size_t ssidLen, char *passOut, size_t passLen) {
    prefs.begin("wifi", true); // read-only
    size_t ssidBytes = prefs.getString("ssid", ssidOut, ssidLen);
    size_t passBytes = prefs.getString("pass", passOut, passLen);
    prefs.end();
    return ssidBytes > 0;
}

void clearWifiCredentials() {
    prefs.begin("wifi", false);
    prefs.clear();
    prefs.end();
}

bool connectToWifi(const char *ssid, const char *pass, uint32_t timeoutMs) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, pass);

    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - start >= timeoutMs) {
            return false;
        }
        delay(250);
    }
    return true;
}

void runProvisioningPortal() {
    WiFi.mode(WIFI_AP);
    String ssid = apSsid();
    WiFi.softAP(ssid.c_str(), PROVISIONING_AP_PASSWORD);
    IPAddress apIP = WiFi.softAPIP();

    Serial.printf("[Provisioning] AP '%s' up. Connect and browse to %s (pwd: %s)\n",
                  ssid.c_str(), apIP.toString().c_str(), PROVISIONING_AP_PASSWORD);

    dnsServer.start(DNS_PORT, "*", apIP);

    server.on("/", handleRoot);
    server.on("/save", HTTP_POST, handleSave);
    server.onNotFound(handleRoot); // any unknown path serves the portal -> triggers OS captive portal popup
    server.begin();

    credentialsSubmitted = false;
    while (!credentialsSubmitted) {
        dnsServer.processNextRequest();
        server.handleClient();
        delay(5);
    }

    // Give the HTTP response time to flush before tearing the AP down.
    delay(500);

    prefs.begin("wifi", false);
    prefs.putString("ssid", submittedSsid);
    prefs.putString("pass", submittedPass);
    prefs.end();

    Serial.println("[Provisioning] Credentials saved. Rebooting...");
    ESP.restart();
}