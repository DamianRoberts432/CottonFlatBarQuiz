#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

// Cotton Flat Bar Quiz ESP32 captive portal.
// The ESP32 creates an OPEN Wi-Fi network. The Raspberry Pi must join it and
// run Quiz.py on port 5000. Update PI_HOST if the Pi is assigned a new IP.

const char* AP_SSID = "Cotton Flat Bar Quiz";
const char* PI_HOST = "192.168.4.3";
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
*{box-sizing:border-box}body{margin:0;min-height:100vh;padding:20px;display:flex;align-items:center;justify-content:center;font-family:Arial,sans-serif;color:#f4f7ff;background:#0f1115}.card{width:100%;max-width:430px;padding:28px;text-align:center;background:#171b24;border:1px solid #2a3242;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.3)}h1{margin:0 0 8px;font-size:25px}.subtitle{margin:0 0 24px;color:#aeb8c8;font-size:14px}.button{display:block;width:100%;margin:12px 0;padding:16px;border-radius:10px;color:white;text-decoration:none;font-size:17px;font-weight:bold}.quiz{background:#2f7cf6}.answers{background:#28a745}.submit{background:#f0a500}.admin{margin-top:26px;padding:12px;background:#495057;font-size:14px}.footer{margin-top:20px;color:#7f8a9d;font-size:11px}
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
  String json = "{\"ssid\":\"" + String(AP_SSID) + "\",\"portal_ip\":\"" + WiFi.softAPIP().toString() + "\",\"pi_url\":\"" + piUrl("/") + "\"}";
  server.send(200, "application/json", json);
}

void handleNotFound() {
  // DNS is redirected to this ESP32, so return the menu for Android, iOS,
  // Windows, and any other captive-portal detection request.
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

  Serial.print("Wi-Fi name: ");
  Serial.println(AP_SSID);
  Serial.print("Portal menu: http://");
  Serial.println(WiFi.softAPIP());
  Serial.print("Raspberry Pi quiz: ");
  Serial.println(piUrl("/"));
  Serial.println("Pi must be connected to this Wi-Fi and running Quiz.py.");
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();
}
