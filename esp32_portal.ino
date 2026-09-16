#include <WiFi.h>
#include <WebServer.h>

// Create a local wifi_secrets.h file next to this sketch with:
//   #define WIFI_SSID "your-network-name"
//   #define WIFI_PASSWORD "your-network-password"
// Do not commit that file to GitHub.
#include "wifi_secrets.h"

const char* PI_URL = "http://192.168.1.165:5000/";

WebServer server(80);

void redirectToPi() {
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Expires", "0");
  server.sendHeader("Location", PI_URL, true);
  server.send(302, "text/plain", "Redirecting to Cotton Flat Quiz...");
}

void connectToWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to ");
  Serial.print(WIFI_SSID);
  Serial.print(" ");

  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 30000) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("ESP32 IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Pi URL: ");
    Serial.println(PI_URL);
  } else {
    Serial.println("Wi-Fi connection failed.");
    Serial.println("Check wifi_secrets.h and the router network.");
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);

  connectToWiFi();

  server.on("/", HTTP_GET, redirectToPi);
  server.onNotFound(redirectToPi);
  server.begin();
  Serial.println("Portal redirect server started.");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    static unsigned long lastRetry = 0;
    if (millis() - lastRetry >= 10000) {
      lastRetry = millis();
      WiFi.reconnect();
    }
  }

  server.handleClient();
}
