#include <Arduino.h>
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
unsigned long last_precise_reading = 0;
const long FAST_CHECK_INTERVAL = 1000;      // 1 segundo - check rápido
const long PRECISE_READING_INTERVAL = 5000; // 5 segundos - leitura precisa (2500 amostras)
const long MQTT_PUBLISH_INTERVAL = 5000;    // publica a cada 5s
unsigned long last_publish = 0;

bool relay_state = false; // False por default
double last_current = 0.0;
double precise_current = 0.0;  // Última leitura precisa (2500 amostras)
double accumulated_current = 0.0;
int reading_count = 0;

// Callback para receber comandos do Dashboard (Streamlit)
void callback(char *topic, byte *payload, unsigned int length) {
    String msg = "";
    for (int i = 0; i < length; i++) {
        msg += (char)payload[i];
    }
    
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

double get_Irms_fast() {
    //I_rms calculations - 100 amostras para resposta rápida (~40ms)
    return emon.calcIrms(100); //arg -> number of samples
}

double get_Irms_precise() {
    //I_rms calculations - 2500 amostras para máxima precisão (~1s)
    //Executa apenas a cada 5 segundos
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
    // Não bloqueia com loop infinito - tenta apenas UMA vez por chamada
    if (client.connected()) return;
    
    static unsigned long last_attempt = 0;
    // Limita tentativas: não tenta a cada ms
    if (millis() - last_attempt < 5000) return;
    last_attempt = millis();
    
    String client_id = "esp32-1-";
    client_id += String(WiFi.macAddress());
    
    Serial.printf("Connecting to MQTT broker as: %s\n", client_id.c_str());
    
    if (client.connect(client_id.c_str(), username, usr_pwd)) {
        Serial.println("MQTT connected!");
        client.subscribe(sub_topic);
    } else {
        Serial.printf("Connection error. Code: %d\n", client.state());
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

    unsigned long now = millis();
    
    // ✅ 2a. LEITURA RÁPIDA a cada 1s - para segurança imediata
    if (now - last_reading >= FAST_CHECK_INTERVAL) {
        last_reading = now;
        
        double current_fast = get_Irms_fast();  // 100 amostras (~40ms)
        last_current = current_fast;
        
        // Safety logic - sempre ativo, independente de MQTT
        if (current_fast > CURRENT_LIMIT && relay_state == true) {
            relay_state = false;
            digitalWrite(RELAY_PIN, LOW);
            digitalWrite(LED_PIN, LOW);
            Serial.println("Safety: Relay disabled - overcurrent!");
        }
        
        // Acumular para cálculo de média
        accumulated_current += current_fast;
        reading_count++;
    }
    
    // ✅ 2b. LEITURA PRECISA a cada 5s - qualidade máxima
    // Executa em background sem bloquear porque é rara
    if (now - last_precise_reading >= PRECISE_READING_INTERVAL) {
        last_precise_reading = now;
        precise_current = get_Irms_precise();  // 2500 amostras (~1s) - PRECISO!
        Serial.printf("Precise reading: %.2f A\n", precise_current);
    }
    
    // ✅ 3. Publicar com BATCHING a cada 5s
    // Formato: "current_fast,precise,state,avg"
    // Exemplo: "5.23,5.18,1,5.20"
    if (client.connected() && now - last_publish >= MQTT_PUBLISH_INTERVAL) {
        last_publish = now;
        
        // Calcular média dos últimos 5 segundos
        double avg_current = reading_count > 0 ? accumulated_current / reading_count : 0;
        
        // Payload compacto em formato fixo (sem JSON)
        char buffer[64];
        snprintf(buffer, sizeof(buffer), 
                 "%.2f,%.2f,%d,%.2f",
                 last_current,           // Última leitura rápida
                 precise_current,        // Leitura precisa com 2500 amostras
                 relay_state ? 1 : 0,    // Estado: 1=ON, 0=OFF
                 avg_current);           // Média dos últimos 5s
        
        Serial.printf("Publishing: %s\n", buffer);
        client.publish(topic, buffer);
        
        // Reset acumulador
        accumulated_current = 0.0;
        reading_count = 0;
    }
    
    // ✅ 4. Yield ao watchdog
    yield();
}
