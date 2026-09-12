#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

const char* AP_SSID = "CottonFlatBar Quiz";
const char* PI_URL  = "http://192.168.4.2:5000/";
const byte DNS_PORT = 53;

DNSServer dnsServer;
WebServer server(80);
IPAddress apIP(192, 168, 4, 1);
IPAddress apGW(192, 168, 4, 1);
IPAddress apSN(255, 255, 255, 0);

void redirectToPi() {
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Expires", "0");
  server.sendHeader("Location", PI_URL, true);
  server.send(302, "text/plain", "Redirecting...");
}

void setup() {
  Serial.begin(115200);

  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(apIP, apGW, apSN);
  WiFi.softAP(AP_SSID);
  dnsServer.start(DNS_PORT, "*", apIP);

  // No portal UI page at all: always jump straight to Pi app
  server.on("/", HTTP_GET, redirectToPi);
  server.onNotFound(redirectToPi);

  server.begin();
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();
}
