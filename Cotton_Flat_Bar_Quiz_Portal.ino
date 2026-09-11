/*
  Cotton Flat Bar Quiz - ESP32 Wi-Fi Portal

  Purpose:
    - Creates the Wi-Fi network: Cotton Flat Bar Quiz
    - Redirects connected phones to the Raspberry Pi quiz page.
    - The Raspberry Pi runs Quiz.py at:
        http://192.168.4.2:5000/

  Important:
    Configure the Raspberry Pi to join this ESP32 Wi-Fi network
    with the static address 192.168.4.2.

  This sketch does NOT need USB serial communication with Quiz.py.
*/

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

// Wi-Fi network shown to guests.
const char *AP_SSID = "Cotton Flat Bar Quiz";

// Must be at least 8 characters for WPA2 Wi-Fi security.
const char *AP_PASSWORD = "CottonFlat2026";

// ESP32 access-point network settings.
const IPAddress AP_IP(192, 168, 4, 1);
const IPAddress AP_GATEWAY(192, 168, 4, 1);
const IPAddress AP_SUBNET(255, 255, 255, 0);

// Raspberry Pi static IP address on this same ESP32 Wi-Fi network.
const IPAddress PI_IP(192, 168, 4, 2);
const uint16_t QUIZ_PORT = 5000;

DNSServer dnsServer;
WebServer webServer(80);

String quizUrl() {
  return "http://" + PI_IP.toString() + ":" + String(QUIZ_PORT) + "/";
}

void redirectToQuiz() {
  webServer.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate");
  webServer.sendHeader("Pragma", "no-cache");
  webServer.sendHeader("Location", quizUrl(), true);
  webServer.send(302, "text/plain", "Opening Cotton Flat Bar Quiz...");
}

void setup() {
  Serial.begin(115200);
  delay(500);

  WiFi.mode(WIFI_AP);

  // Use a fixed ESP32 portal address.
  if (!WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET)) {
    Serial.println("Failed to configure ESP32 access point address.");
  }

  // Channel 1, visible SSID, up to 8 client phones/devices.
  if (!WiFi.softAP(AP_SSID, AP_PASSWORD, 1, false, 8)) {
    Serial.println("Failed to start the Wi-Fi access point.");
    return;
  }

  Serial.println();
  Serial.println("Cotton Flat Bar Quiz portal started.");
  Serial.print("Wi-Fi name: ");
  Serial.println(AP_SSID);
  Serial.print("ESP32 portal address: http://");
  Serial.println(WiFi.softAPIP());
  Serial.print("Quiz redirect target: ");
  Serial.println(quizUrl());

  // Reply to every DNS request with the ESP32 address so captive-portal
  // detection requests arrive here and can be redirected to the Pi.
  dnsServer.start(53, "*", AP_IP);

  // Common captive-portal detection paths.
  webServer.on("/", HTTP_ANY, redirectToQuiz);
  webServer.on("/generate_204", HTTP_ANY, redirectToQuiz);
  webServer.on("/hotspot-detect.html", HTTP_ANY, redirectToQuiz);
  webServer.on("/connecttest.txt", HTTP_ANY, redirectToQuiz);
  webServer.on("/ncsi.txt", HTTP_ANY, redirectToQuiz);
  webServer.on("/success.txt", HTTP_ANY, redirectToQuiz);

  // Redirect all other requests to the quiz page too.
  webServer.onNotFound(redirectToQuiz);
  webServer.begin();
}

void loop() {
  dnsServer.processNextRequest();
  webServer.handleClient();
}
