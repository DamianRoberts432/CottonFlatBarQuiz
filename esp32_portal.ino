#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

// Cotton Flat Bar Quiz ESP32 captive portal.
//
// The ESP32 creates the OPEN "Cotton Flat Bar Quiz" Wi-Fi network for patrons
// and for the Raspberry Pi's local quiz connection.
//
// The Raspberry Pi must use a SECOND network interface for Arris-E491 and
// GitHub updates: either Ethernet to the Arris router or a USB Wi-Fi adapter.
// A Raspberry Pi 3B+'s single built-in Wi-Fi radio cannot join both independent
// Wi-Fi networks at the same time. The ESP32 USB cable supplies power/serial;
// it is not a network connection.
//
// Configure the Pi's interface connected to this AP with the fixed address:
//   IP address: 192.168.4.4
//   Netmask:    255.255.255.0
//   Gateway:    none
//   DNS:        none

const char* AP_SSID = "Cotton Flat Bar Quiz";
const char* PI_HOST = "192.168.4.4";
const uint16_t PI_PORT = 5000;

const byte DNS_PORT = 53;
IPAddress AP_IP(192, 168, 4, 1);
IPAddress AP_GATEWAY(192, 168, 4, 1);
IPAddress AP_SUBNET(255, 255, 255, 0);

DNSServer dnsServer;
WebServer server(80);

String piUrl(const char* path) {
  return String("http://") + PI_HOST + ":" + String(PI_PORT) + path;
}

const char MENU_STYLE[] PROGMEM = R"rawliteral(
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;padding:20px;display:flex;align-items:center;justify-content:center;font-family:Arial,sans-serif;color:#f4f7ff;background:#0f1115}.card{width:100%;max-width:420px;background:#181b22;border-radius:16px;padding:28px;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,.4)}h1{margin:0 0 6px;font-size:1.6rem}.subtitle{color:#9aa4b2;margin:0 0 20px}.button{display:block;text-decoration:none;color:#0f1115;background:#f4f7ff;padding:14px 18px;border-radius:12px;font-weight:700;margin:10px 0}.button.quiz{background:#4ade80}.button.answers{background:#60a5fa}.button.submit{background:#fbbf24}.button.admin{background:#94a3b8}.footer{margin-top:18px;color:#6b7280;font-size:.85rem}
</style>
)rawliteral";

void handleMenu() {
  String html;
  html.reserve(3500);
  html += "<!doctype html><html><head><meta charset='utf-8'>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>Cotton Flat Bar Quiz</title>";
  html += MENU_STYLE;
  html += "</head><body><main class='card'>";
  html += "<h1>Cotton Flat Bar Quiz</h1>";
  html += "<p class='subtitle'>Choose an option below</p>";
  html += "<a class='button quiz' href='" + piUrl("/quiz") + "'>Take Quiz</a>";
  html += "<a class='button answers' href='" + piUrl("/answers") + "'>See Answers</a>";
  html += "<a class='button submit' href='" + piUrl("/submit-question") + "'>Submit Question</a>";
  html += "<a class='button admin' href='" + piUrl("/admin") + "'>Admin</a>";
  html += "<p class='footer'>Connected to Cotton Flat Bar Quiz</p>";
  html += "</main></body></html>";

  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Expires", "0");
  server.send(200, "text/html", html);
}

void handleStatus() {
  String json = "{";
  json += "\"ssid\":\"" + String(AP_SSID) + "\",";
  json += "\"portal_ip\":\"" + WiFi.softAPIP().toString() + "\",";
  json += "\"pi_url\":\"" + piUrl("/") + "\",";
  json += "\"connected_clients\":" + String(WiFi.softAPgetStationNum());
  json += "}";
  server.send(200, "application/json", json);
}

void handleNotFound() {
  // DNS is redirected to this ESP32, so return the menu for Android, iOS,
  // Windows, and other captive-portal detection requests.
  handleMenu();
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("Cotton Flat Bar Quiz portal starting...");

  WiFi.mode(WIFI_AP);
  if (!WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET)) {
    Serial.println("Warning: could not configure AP address.");
  }
  if (!WiFi.softAP(AP_SSID)) {
    Serial.println("ERROR: Could not start Wi-Fi access point.");
    return;
  }

  dnsServer.start(DNS_PORT, "*", AP_IP);
  server.on("/", HTTP_GET, handleMenu);
  server.on("/esp32-status", HTTP_GET, handleStatus);
  server.onNotFound(handleNotFound);
  server.begin();

  Serial.print("Patron Wi-Fi name: ");
  Serial.println(AP_SSID);
  Serial.print("Portal menu: http://");
  Serial.println(WiFi.softAPIP());
  Serial.print("Raspberry Pi quiz: ");
  Serial.println(piUrl("/"));
  Serial.println("Pi portal-side IP must be 192.168.4.4.");
  Serial.println("Pi needs Ethernet or a USB Wi-Fi adapter for Arris-E491/GitHub.");
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();
}
