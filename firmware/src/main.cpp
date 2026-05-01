#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <EmonLib.h>

//Energy monitoring
//sct-013-000 neededs a burden resis 33ohm -> calib = 60.6
//sct-013-030 no burnden resisteor needed -> calib = 30
const double calib = 30;

// wifi config
const char *ssid = "João Bessa";
const char *pwd = "tassemnet";

// MQTT
const char *mqtt_broker = "broker.emqx.io";
const char *topic = "smile-iot/power";
const char *username = "1211189";
const char *usr_pwd = "isep";
const int port = 1883;

// Built-in LED pin on ESP32-DevKit
#define LED_PIN 2
#define SCT_PIN 34 //sct-013 -> gpio 34

WiFiClient espClient;
PubSubClient client(espClient);
EnergyMonitor emon;

/*
Might be usefull to have to send commands to the esp or smth, investigate later

//callback function to receive mqtt messages
void callback(char *topic, byte *payload, unsigned int length) {
    Serial.print("Message arrived in topic: ");
    Serial.println(topic);
    Serial.print("Message:");
    for (int i = 0; i < length; i++) {
        Serial.print((char) payload[i]);
    }
    Serial.println();
    Serial.println("-----------------------");
}
*/

double get_Irms() {
    //I_rms calculations
    double I_rms = emon.calcIrms(2500); //arg -> number of samples
    return I_rms;
}

void wifi_connection() {
    // connecting to wifi
    WiFi.begin(ssid, pwd);
    while (WiFi.status() != WL_CONNECTED) {
        delay(5000);
        Serial.println("Connecting to wifi... make sure network is available\n");
    }
    Serial.println("Connected!");
}

void setup() {
    //serial port
    Serial.begin(115200);
    
    //Config adc pin and calib
    emon.current(SCT_PIN, calib);

    //WIFI CONNECTION
    wifi_connection();

    //mqtt connection
    client.setServer(mqtt_broker, port);

    //to receive message uncomment this line
    //client.setCallback(callback);

    while (!client.connected()) {
        String client_id = "esp32-Publisher";
        client_id += String(WiFi.macAddress());

        Serial.printf("this client is: %s", client_id.c_str());
        
        if (client.connect(client_id.c_str(), username, pwd)) {
            Serial.println("Broker connected!");
        } else {
            Serial.printf("failed with state: %d", client.state());
            delay(5000);
        }        
    }

    double current = get_Irms();
    client.publish(topic, current);
    
    // Initialize the LED pin as an output
    pinMode(LED_PIN, OUTPUT);

    
}

void loop() {
    // Turn LED on
    digitalWrite(LED_PIN, HIGH);
    delay(1000);  // Wait 1 second
    
    // Turn LED off
    digitalWrite(LED_PIN, LOW);
    delay(1000);  // Wait 1 second

    double current = get_Irms();
}
