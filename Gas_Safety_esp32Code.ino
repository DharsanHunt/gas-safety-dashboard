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

const unsigned long GAS_ON_TIME  = 8000;   // 8 sec above threshold to activate
const unsigned long GAS_OFF_TIME = 60000;  // 60 sec below threshold to reset system
const unsigned long BUZZER_OFF_DELAY = 5000; // 5 sec below threshold to stop buzzer

Servo gasServo;

/* ================= STATE ================= */
bool systemActive = false;
bool buzzerActive = false;
bool buzzerMuted = false;   // Muted via cloud dashboard

unsigned long aboveStartTime = 0;
unsigned long belowStartTime = 0;
unsigned long buzzerBelowStart = 0;  // Tracks when gas went below for buzzer off
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

    // Check if server sent a mute command
    if (httpResponseCode == 200) {
      String response = http.getString();
      if (response.indexOf("\"mute\":true") >= 0) {
        digitalWrite(BUZZER_PIN, LOW);
        buzzerActive = false;
        buzzerMuted = true;
        Serial.println(">>> Buzzer MUTED via cloud dashboard");
      }
    }

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
    buzzerBelowStart = 0;  // Reset buzzer-off timer

    if (aboveStartTime == 0)
      aboveStartTime = currentTime;

    if (!systemActive && (currentTime - aboveStartTime >= GAS_ON_TIME)) {
      gasServo.write(90);

      // RELAY ON (Active Low Logic)
      digitalWrite(RELAY_PIN, LOW);

      // BUZZER ON + reset mute (new alarm = new mute cycle)
      buzzerMuted = false;
      digitalWrite(BUZZER_PIN, HIGH);
      buzzerActive = true;

      systemActive = true;
      Serial.println("--- ALERT: SYSTEM ACTIVE ---");
    }

    // Keep buzzer ringing continuously while above threshold (unless muted)
    if (systemActive && !buzzerMuted) {
      digitalWrite(BUZZER_PIN, HIGH);
      buzzerActive = true;
    }
  }
  else {
    aboveStartTime = 0;

    /* ===== BUZZER OFF after 5 sec below threshold ===== */
    if (buzzerActive) {
      if (buzzerBelowStart == 0)
        buzzerBelowStart = currentTime;

      if (currentTime - buzzerBelowStart >= BUZZER_OFF_DELAY) {
        digitalWrite(BUZZER_PIN, LOW);
        buzzerActive = false;
        buzzerMuted = false;  // Reset mute for next activation
        buzzerBelowStart = 0;
        Serial.println("Buzzer OFF (5s below threshold)");
      }
    }

    /* ===== SYSTEM RESET after 60 sec below threshold ===== */
    if (systemActive) {
      if (belowStartTime == 0)
        belowStartTime = currentTime;

      if (currentTime - belowStartTime >= GAS_OFF_TIME) {
        gasServo.write(0);

        // RELAY OFF (Active Low Logic)
        digitalWrite(RELAY_PIN, HIGH);

        // Ensure buzzer is also off
        digitalWrite(BUZZER_PIN, LOW);
        buzzerActive = false;

        systemActive = false;
        belowStartTime = 0;
        Serial.println("--- SAFE: SYSTEM RESET ---");
      }
    }
  }

  /* ===== SEND DATA ===== */
  if (currentTime - lastSendTime > 5000) {
    sendToCloud(gasValue);
    lastSendTime = currentTime;
  }

  delay(200);
}