#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <EmonLib.h>

//Energy monitoring
//sct-013-000 neededs a burden resis 33ohm -> calib = 60.6
//sct-013-030 no burnden resisteor needed -> calib = 30
const double calib = 30;
const double CURRENT_LIMIT = 15.0;  //15 Amps on most european houses

// wifi config
const char *ssid = "João Bessa";
const char *pwd = "tassemnet";

// MQTT
const char *mqtt_broker = "broker.emqx.io";
const char *topic = "smile-iot/power";
//topic to recieve commands
const char *sub_topic = "smile-iot/command";
const char *username = "1211189";
const char *usr_pwd = "isep";
const int port = 1883;

// PINOUT
#define LED_PIN 2 // Built-in LED pin on ESP32-DevKit
#define SCT_PIN 34 //sct-013 -> gpio 34
#define RELAY_PIN 25  

WiFiClient espClient;
PubSubClient client(espClient);
EnergyMonitor emon;

// Control variables
unsigned long last_reading = 0;
const long _delay = 1000; // um segundo
bool relay_state = false; // Flase por default

// Callback para receber comandos do Dashboard (Streamlit)
void callback(char *topic, byte *payload, unsigned int length) {
    String msg = "";
    for (int i = 0; i < length; i++) {
        msg += (char)payload[i];
    }
    
    Serial.printf("Received commad on topic -> %s: %s\n", topic, msg.c_str());

    // Atualiza o estado do relay
    if (msg == "ON") {
        relay_state = true;
        digitalWrite(RELAY_PIN, HIGH);
        digitalWrite(LED_PIN, HIGH); // Feedback visual
    } else if (msg == "OFF") {
        relay_state = false;
        digitalWrite(RELAY_PIN, LOW);
        digitalWrite(LED_PIN, LOW);
    }
}

double get_Irms() {
    //I_rms calculations
    return emon.calcIrms(2500); //arg -> number of samples
}

void wifi_connection() {
    // connecting to wifi
    WiFi.begin(ssid, pwd);
    while (WiFi.status() != WL_CONNECTED) {
        delay(1000);
        Serial.println("Connecting to wifi... make sure network is available\n");
    }
    Serial.println("Connected!");
}

void mqtt_reconnect() {
    // Loop until connection
    while (!client.connected()) {
        String client_id = "esp32-1-";
        client_id += String(WiFi.macAddress());
        
        Serial.printf("Connecting to a MQTT broker as: %s\n", client_id.c_str());
        
        if (client.connect(client_id.c_str(), username, usr_pwd)) {
            Serial.println("LIGADO!");
            // Subscrever ao tópico de comandos
            client.subscribe(sub_topic);
        } else {
            Serial.printf("Connection error. Error: %d. Trying again in 5s...\n", client.state());
            delay(5000);
        }        
    }
}

void setup() {
    //serial port
    Serial.begin(115200);

    // pin setup
    pinMode(LED_PIN, OUTPUT);
    pinMode(RELAY_PIN, OUTPUT);
    digitalWrite(RELAY_PIN, LOW);
    
    //Config adc pin and calib
    emon.current(SCT_PIN, calib);

    //WIFI CONNECTION
    wifi_connection();

    //mqtt connection
    client.setServer(mqtt_broker, port);
    //to receive message uncomment this line
    client.setCallback(callback);
}

void loop() {

    if (!client.connected()) {
        mqtt_reconnect();
    }

    client.loop(); //message processing & keep connection

    unsigned long nowTimeStamp = millis();

    if (nowTimeStamp - last_reading >= _delay) {
        last_reading = nowTimeStamp;
    }
    
    double current_Irms = get_Irms();

    //safty logic
    if (current_Irms > CURRENT_LIMIT && relay_state == true) {
        relay_state = false;
        digitalWrite(RELAY_PIN, LOW);
        digitalWrite(LED_PIN, LOW);
    }

    StaticJsonDocument<200> doc;
    doc["current"] = current_Irms;
    doc["outlet_state"] = relay_state ? "ON" : "OFF";

    char jsonBuffer[256];
    serializeJson(doc, jsonBuffer);

    client.publish(topic, jsonBuffer);
        
}
