#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include "lwip/lwip_napt.h"
#include "lwip/dns.h"

// Cotton Flat Bar Quiz ESP32 captive portal + Wi-Fi NAT router.
//
// The ESP32 does two jobs at once:
//   1. STATION: joins your existing "Arris-E491" Wi-Fi for internet access.
//   2. ACCESS POINT: broadcasts the open "Cotton Flat Bar Quiz" network for
//      the Raspberry Pi and patrons.
//
// Traffic from the AP side is NAT-forwarded out through the STA (Arris)
// connection, so anything joined to "Cotton Flat Bar Quiz" -- including the
// Raspberry Pi -- gets real internet access (for `git pull`, etc.) while
// still being on the same local network as patrons for the quiz itself.
//
// The USB cable to the Pi is power/serial only and is NOT used for
// networking; all traffic moves over Wi-Fi, which is faster and far more
// reliable than trying to route packets over a serial line.
//
// IMPORTANT: Set ARRIS_PASSWORD below before flashing.

// ---------- EDIT BEFORE FLASHING ----------
const char* ARRIS_SSID = "Arris-E491";
const char* ARRIS_PASSWORD = "TYPE_PASSPHRASE_HERE"; // <-- put real Arris-E491 password here
// -------------------------------------------

const char* AP_SSID = "Cotton Flat Bar Quiz"; // open network, no password
const char* PI_HOST = "192.168.4.4";
const uint16_t PI_PORT = 5000;

const byte DNS_PORT = 53;
IPAddress AP_IP(192, 168, 4, 1);
IPAddress AP_GATEWAY(192, 168, 4, 1);
IPAddress AP_SUBNET(255, 255, 255, 0);

const unsigned long STA_RETRY_INTERVAL_MS = 15000;
unsigned long lastStaRetry = 0;
bool naptStarted = false;

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
  String staState;
  switch (WiFi.status()) {
    case WL_CONNECTED: staState = "connected"; break;
    case WL_IDLE_STATUS: staState = "idle"; break;
    case WL_NO_SSID_AVAIL: staState = "ssid_not_found"; break;
    case WL_CONNECT_FAILED: staState = "connect_failed"; break;
    case WL_DISCONNECTED: staState = "disconnected"; break;
    default: staState = "unknown"; break;
  }

  String json = "{";
  json += "\"ap_ssid\":\"" + String(AP_SSID) + "\",";
  json += "\"portal_ip\":\"" + WiFi.softAPIP().toString() + "\",";
  json += "\"pi_url\":\"" + piUrl("/") + "\",";
  json += "\"connected_clients\":" + String(WiFi.softAPgetStationNum()) + ",";
  json += "\"arris_ssid\":\"" + String(ARRIS_SSID) + "\",";
  json += "\"arris_status\":\"" + staState + "\",";
  json += "\"arris_ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"nat_active\":" + String(naptStarted ? "true" : "false");
  json += "}";
  server.send(200, "application/json", json);
}

void handleNotFound() {
  // DNS is redirected to this ESP32, so return the menu for Android, iOS,
  // Windows, and any other captive-portal detection request.
  handleMenu();
}

void connectArris() {
  Serial.print("Connecting to Arris Wi-Fi: ");
  Serial.println(ARRIS_SSID);
  WiFi.begin(ARRIS_SSID, ARRIS_PASSWORD);
}

void startNat() {
  if (naptStarted) return;
  // Enable IP forwarding + NAPT so devices on the "Cotton Flat Bar Quiz" AP
  // (192.168.4.0/24) can reach the internet through the Arris connection.
  ip_napt_enable(AP_IP, 1);
  // Point the AP-side DNS at whatever DNS the Arris network handed us so
  // clients (like the Pi) can resolve github.com, etc.
  dns_setserver(0, dns_getserver(0));
  naptStarted = true;
  Serial.println("NAT routing enabled: Cotton Flat Bar Quiz -> Arris-E491 -> Internet.");
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("Cotton Flat Bar Quiz portal + NAT router starting...");

  WiFi.mode(WIFI_AP_STA);

  if (!WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET)) {
    Serial.println("Warning: could not configure AP address.");
  }
  if (!WiFi.softAP(AP_SSID)) {
    Serial.println("ERROR: Could not start Wi-Fi access point.");
  }

  connectArris();

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
  Serial.println("Pi (and patrons) should join Cotton Flat Bar Quiz.");
  Serial.println("Pi should use IP 192.168.4.4, gateway/DNS 192.168.4.1.");
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();

  if (WiFi.status() == WL_CONNECTED) {
    if (!naptStarted) {
      startNat();
    }
  } else {
    naptStarted = false;
    unsigned long nowMs = millis();
    if (nowMs - lastStaRetry >= STA_RETRY_INTERVAL_MS) {
      lastStaRetry = nowMs;
      connectArris();
    }
  }
}
