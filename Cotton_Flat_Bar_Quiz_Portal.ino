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

bool isCaptiveProbe(const String& u) {
  return (u == "/generate_204" ||
          u == "/gen_204" ||
          u == "/hotspot-detect.html" ||
          u == "/library/test/success.html" ||
          u == "/success.txt" ||
          u == "/ncsi.txt" ||
          u == "/connecttest.txt");
}

void redirectToPi() {
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Location", PI_URL, true);
  server.send(302, "text/plain", "Redirecting...");
}

void setup() {
  Serial.begin(115200);

  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(apIP, apGW, apSN);
  WiFi.softAP(AP_SSID); // open AP
  dnsServer.start(DNS_PORT, "*", apIP);

  // No landing page: root goes straight to Pi
  server.on("/", HTTP_GET, redirectToPi);

  server.onNotFound([]() {
    // For captive probes and all other paths, redirect to Pi directly
    redirectToPi();
  });

  server.begin();
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();
}
