#include <WiFi.h>
#include <HTTPClient.h>
#include <ESP32Servo.h>

/* ================= WIFI ================= */
const char* ssid = "iQOO Z9 5G";
const char* password = "dharsan2";

/* ================= CLOUD ================= */
const char* serverName = "https://gas-safety-dashboard.onrender.com/update";

/* ================= PINS ================= */
#define GAS_SENSOR 34
#define SERVO_PIN  18
#define RELAY_PIN  27
#define BUZZER_PIN 26

/* ================= SETTINGS ================= */
int GAS_THRESHOLD = 2000;
int RESET_THRESHOLD = 1800;

const unsigned long GAS_ON_TIME  = 8000;   // 5 sec above threshold
const unsigned long GAS_OFF_TIME = 60000;  // 10 sec below threshold
const unsigned long BUZZER_DURATION = 5000;

Servo gasServo;

/* ================= STATE ================= */
bool systemActive = false;
bool buzzerActive = false;

unsigned long aboveStartTime = 0;
unsigned long belowStartTime = 0;
unsigned long buzzerStartTime = 0;
unsigned long lastSendTime = 0;

/* ================= WIFI ================= */
void connectWiFi() {
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected!");
}

/* ================= CLOUD ================= */
void sendToCloud(int gasValue) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverName);
    http.addHeader("Content-Type", "application/json");

    String jsonData = "{";
    jsonData += "\"gas\":" + String(gasValue) + ",";
    jsonData += "\"state\":\"" + String(systemActive ? "ACTIVE" : "SAFE") + "\",";
    jsonData += "\"buzzer\":" + String(buzzerActive ? "true" : "false");
    jsonData += "}";

    int httpResponseCode = http.POST(jsonData);
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);
    http.end();
  }
}

/* ================= SETUP ================= */
void setup() {
  Serial.begin(115200);

  // IMPORTANT: Set Relay HIGH before pinMode to prevent initial click
  digitalWrite(RELAY_PIN, HIGH); 
  pinMode(RELAY_PIN, OUTPUT);
  
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW); // Buzzer stays OFF initially

  gasServo.attach(SERVO_PIN);
  gasServo.write(0);

  connectWiFi();
}

/* ================= LOOP ================= */
void loop() {
  int gasValue = analogRead(GAS_SENSOR);
  unsigned long currentTime = millis();

  Serial.print("Gas Value: ");
  Serial.println(gasValue);

  /* ===== GAS ABOVE THRESHOLD ===== */
  if (gasValue > GAS_THRESHOLD) {
    if (aboveStartTime == 0)
      aboveStartTime = currentTime;

    if (!systemActive && (currentTime - aboveStartTime >= GAS_ON_TIME)) {
      gasServo.write(90);

      // RELAY ON (Active Low Logic)
      digitalWrite(RELAY_PIN, LOW);  
      
      // BUZZER ON (Active High Logic)
      digitalWrite(BUZZER_PIN, HIGH);

      buzzerStartTime = currentTime;
      buzzerActive = true;
      systemActive = true;
      Serial.println("--- ALERT: SYSTEM ACTIVE ---");
    }
  }
  else {
    aboveStartTime = 0;

    if (systemActive) {
      if (belowStartTime == 0)
        belowStartTime = currentTime;

      if (currentTime - belowStartTime >= GAS_OFF_TIME) {
        gasServo.write(0);

        // RELAY OFF (Active Low Logic)
        digitalWrite(RELAY_PIN, HIGH); 
        
        // BUZZER OFF
        digitalWrite(BUZZER_PIN, LOW);

        systemActive = false;
        belowStartTime = 0;
        Serial.println("--- SAFE: SYSTEM RESET ---");
      }
    }
  }

  /* ===== BUZZER AUTO OFF ===== */
  if (buzzerActive && (currentTime - buzzerStartTime >= BUZZER_DURATION)) {
    digitalWrite(BUZZER_PIN, LOW);
    buzzerActive = false;
    Serial.println("Buzzer timed out (Auto-OFF)");
  }

  /* ===== SEND DATA ===== */
  if (currentTime - lastSendTime > 5000) {
    sendToCloud(gasValue);
    lastSendTime = currentTime;
  }

  delay(200);
}