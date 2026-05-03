#include <ESP8266WiFi.h>
#include <Firebase_ESP_Client.h>
#include <Servo.h>

// WiFi
#define WIFI_SSID "YOUR_WIFI"
#define WIFI_PASSWORD "WIFI-PASSWORD"

// Firebase
#define API_KEY "YOUR_API_KEY"
#define DATABASE_URL "https://DATABASE_URL"  // ⚠️ MUST END WITH /

FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

Servo myServo;
#define SERVO_PIN D4

String lastState = "";

void setup() {
  Serial.begin(115200);
  delay(2000);   // 🔥 IMPORTANT
  Serial.println("\n🚀 ESP STARTED");

  myServo.attach(SERVO_PIN);
  myServo.write(0);

  // WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\n✅ WiFi Connected");

  // 🔥 CRITICAL FIX
  config.api_key = API_KEY;
  config.database_url = DATABASE_URL;

  // Required for new library
  auth.user.email = "amulya@gmail.com";
  auth.user.password = "Amulya@12";

  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  Serial.println("🔥 Firebase Ready");
}

void loop() {

  if (Firebase.RTDB.getString(&fbdo, "/DOORLOCK/DOOR")) {

    String state = fbdo.stringData();
    Serial.println("Door: " + state);

    if (state != lastState) {

      if (state == "OPEN") {
        Serial.println("🔓 OPEN");
        myServo.write(90);
      } else {
        Serial.println("🔒 CLOSE");
        myServo.write(0);
      }

      lastState = state;
    }

  } else {
    Serial.println("❌ ERROR: " + fbdo.errorReason());
  }

  delay(500);
}