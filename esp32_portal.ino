#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

// Cotton Flat Bar Quiz ESP32 captive portal.
//
// This ESP32 runs in AP+STA mode:
//   1. It creates its own OPEN Wi-Fi access point ("Cotton Flat Bar Quiz") for
//      patrons to join and reach the quiz portal/menu.
//   2. It ALSO joins your home/venue Wi-Fi network ("Arris-E491") as a
//      station, so the ESP32 (and, if you want, the Pi) can stay online for
//      updates, remote access, etc.
//
// IMPORTANT: Fill in ARRIS_E491_PASSWORD below with the real passphrase
// before flashing. Do not commit the real passphrase to a public repo.
//
// The Raspberry Pi should join the "Cotton Flat Bar Quiz" AP network and be
// configured with a fixed IP of 192.168.4.4 so the menu links below remain
// stable.

// ---------- EDIT THESE BEFORE FLASHING ----------
const char* AP_SSID = "Cotton Flat Bar Quiz";     // Open network patrons join
const char* HOME_SSID = "Arris-E491";             // Existing home/venue Wi-Fi
const char* HOME_PASSWORD = "TYPE_PASSPHRASE_HERE"; // <-- put Arris-E491 password here
// -------------------------------------------------

const char* PI_HOST = "192.168.4.4";
const uint16_t PI_PORT = 5000;

const byte DNS_PORT = 53;
IPAddress AP_IP(192, 168, 4, 1);
IPAddress AP_GATEWAY(192, 168, 4, 1);
IPAddress AP_SUBNET(255, 255, 255, 0);

// How often to check/retry the home Wi-Fi connection (milliseconds).
const unsigned long STA_RETRY_INTERVAL_MS = 15000;
unsigned long lastStaRetry = 0;

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
  json += "\"home_ssid\":\"" + String(HOME_SSID) + "\",";
  json += "\"home_status\":\"" + staState + "\",";
  json += "\"home_ip\":\"" + WiFi.localIP().toString() + "\"";
  json += "}";
  server.send(200, "application/json", json);
}

void handleNotFound() {
  // DNS is redirected to this ESP32, so return the menu for Android, iOS,
  // Windows, and any other captive-portal detection request.
  handleMenu();
}

void connectHomeWifi() {
  Serial.print("Connecting to home Wi-Fi: ");
  Serial.println(HOME_SSID);
  WiFi.begin(HOME_SSID, HOME_PASSWORD);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("Cotton Flat Bar Quiz portal starting...");

  // Run as both an access point (for patrons) and a station (joins home Wi-Fi).
  WiFi.mode(WIFI_AP_STA);

  if (!WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET)) {
    Serial.println("Warning: could not configure AP address.");
  }
  if (!WiFi.softAP(AP_SSID)) {
    Serial.println("ERROR: Could not start Wi-Fi access point.");
  }

  connectHomeWifi();

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
  Serial.println("Pi must be connected to the patron Wi-Fi and have a fixed IP of 192.168.4.4.");
  Serial.print("Also attempting to join home Wi-Fi: ");
  Serial.println(HOME_SSID);
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();

  // Periodically retry the home Wi-Fi connection if it drops or never
  // connected (e.g., router restarted, out of range temporarily, etc.).
  // This does not affect the patron-facing AP, which keeps running
  // regardless of home Wi-Fi status.
  if (WiFi.status() != WL_CONNECTED) {
    unsigned long nowMs = millis();
    if (nowMs - lastStaRetry >= STA_RETRY_INTERVAL_MS) {
      lastStaRetry = nowMs;
      connectHomeWifi();
    }
  }
}
