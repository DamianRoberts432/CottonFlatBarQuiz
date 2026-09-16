#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

// ---------------------------------------------------------------------------
// Cotton Flat Bar Quiz - ESP32 Captive Portal Menu
// ---------------------------------------------------------------------------
// The ESP32 creates its OWN Wi-Fi network named "Cotton Flat Bar Quiz".
// Guests connect to this network with their phone and are shown a menu with
// four options that link straight into the Flask app (Quiz.py) running on
// the Raspberry Pi:
//   - Take Quiz         -> PI_URL/quiz
//   - See Answers        -> PI_URL/answers
//   - Submit Question    -> PI_URL/submit-question
//   - Admin              -> PI_URL/admin   (protected by code 1346 in Quiz.py)
//
// The Raspberry Pi must be reachable at PI_HOST on this same network. If the
// ESP32 is running as its own access point (AP mode, default below), the Pi
// needs to join that AP with a static IP (e.g. 192.168.4.2) and PI_HOST
// should be updated to match.
// ---------------------------------------------------------------------------

const char* AP_SSID = "Cotton Flat Bar Quiz"; // Open network, no password
const char* PI_HOST  = "192.168.4.2";          // Raspberry Pi IP on the ESP32 AP
const int   PI_PORT  = 5000;

String piUrl(const String& path) {
  return "http://" + String(PI_HOST) + ":" + String(PI_PORT) + path;
}

const byte DNS_PORT = 53;
DNSServer dnsServer;
WebServer server(80);

IPAddress apIP(192, 168, 4, 1);
IPAddress apGW(192, 168, 4, 1);
IPAddress apSN(255, 255, 255, 0);

const char* MENU_STYLE =
  "<style>"
  "body{font-family:Arial,sans-serif;background:#0f1115;color:#f4f7ff;"
  "padding:20px;text-align:center;margin:0;min-height:100vh;display:flex;"
  "align-items:center;justify-content:center}"
  ".card{background:#171b24;border:1px solid #2a3242;max-width:420px;width:100%;"
  "padding:28px;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,0.25);"
  "box-sizing:border-box}"
  "h1{font-size:22px;margin-bottom:6px}"
  "p.sub{opacity:0.7;font-size:13px;margin-top:0;margin-bottom:22px}"
  "a.btn{display:block;width:100%;margin:12px 0;padding:16px;border:none;"
  "border-radius:10px;background:#2f7cf6;color:white;text-decoration:none;"
  "font-size:17px;font-weight:bold;box-sizing:border-box}"
  "a.btn:active{background:#1a63d9}"
  ".btn-answers{background:#28a745}"
  ".btn-submit{background:#f0a500}"
  ".btn-admin{background:#495057;font-size:13px;padding:10px;opacity:0.85;margin-top:26px}"
  "</style>";

void handleMenu() {
  String html;
  html += "<!doctype html><html><head><meta charset='utf-8'>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>Cotton Flat Bar Quiz</title>";
  html += MENU_STYLE;
  html += "</head><body><div class='card'>";
  html += "<h1>🍺 Cotton Flat Bar Quiz</h1>";
  html += "<p class='sub'>Pick an option to get started</p>";
  html += "<a class='btn' href='" + piUrl("/quiz") + "'>▶️ Take Quiz</a>";
  html += "<a class='btn btn-answers' href='" + piUrl("/answers") + "'>📋 See Answers</a>";
  html += "<a class='btn btn-submit' href='" + piUrl("/submit-question") + "'>💡 Submit Question</a>";
  html += "<a class='btn btn-admin' href='" + piUrl("/admin") + "'>Admin (code required)</a>";
  html += "</div></body></html>";

  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.send(200, "text/html", html);
}

bool isCaptiveProbe(const String& path) {
  return (path == "/generate_204" ||
          path == "/gen_204" ||
          path == "/hotspot-detect.html" ||
          path == "/library/test/success.html" ||
          path == "/success.txt" ||
          path == "/ncsi.txt" ||
          path == "/connecttest.txt");
}

void handleNotFound() {
  // Captive portal probes and any other unknown path land on the menu too,
  // so phones/laptops pop the menu open automatically after connecting.
  handleMenu();
}

void setup() {
  Serial.begin(115200);
  delay(300);

  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(apIP, apGW, apSN);
  WiFi.softAP(AP_SSID); // Open access point, no password

  dnsServer.start(DNS_PORT, "*", apIP);

  server.on("/", HTTP_GET, handleMenu);
  server.onNotFound(handleNotFound);
  server.begin();

  Serial.println();
  Serial.println("Cotton Flat Bar Quiz portal started.");
  Serial.print("AP SSID: ");
  Serial.println(AP_SSID);
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());
  Serial.print("Expecting Pi at: ");
  Serial.println(piUrl("/"));
  Serial.println("Make sure the Raspberry Pi joins this network with a static IP matching PI_HOST.");
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();
}
