#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>

/*
TODO:
    - Connect to Wifi; [establish network link]
    - Define the Host; [sprecify ip addr or url to broker]
    - Connect to the Port; [Open socket (1883 for MQTT)]
    - Write Data;
*/

/*
To test connectivity, attach a btn to turn on the built-in led and send 
a message saying "on" or "off" and then display it on the dashboard
*/

// wifi config
const char *ssid = "João Bessa";
const char *pwd = "tassemnet";

// MQTT
const char *mqtt_broker = "broker.emqx.io";
const char *topic = "pesta/isep";
const char *username = "1211189";
const char *usr_pwd = "isep";
const int port = 1883;

// Built-in LED pin on ESP32-DevKit
#define LED_PIN 2

WiFiClient espClient;
PubSubClient client(espClient);

/*
Might be usefull to have in some commands need to be sent to the esp or smth investigate later

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

void setup() {
    //serial port
    Serial.begin(115200);

    // connecting to wifi
    WiFi.begin(ssid, pwd);
    while (WiFi.status() != WL_CONNECTED) {
        delay(5000);
        Serial.println("Connecting to wifi... make sure network is available\n");
    }
    Serial.println("Connected!");

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

    client.publish(topic, "TEST MESSAGE!");
    
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
}
