#include <WiFi.h>
#include <WiFiMulti.h>
#include <WebServer.h>
#include <DNSServer.h>
#include "lwip/lwip_napt.h"
#include "lwip/dns.h"

// Copy wifi_secrets.example.h to wifi_secrets.h beside this sketch and enter
// your upstream Wi-Fi credentials there. The local file is gitignored.
#include "wifi_secrets.h"

// Cotton Flat Bar Quiz ESP32 captive portal.
//
// The quiz only needs a stable local access point between phones and the Pi.
// Keep upstream routing disabled unless this ESP32 must also provide internet
// access: station-mode scans/reconnects share the ESP32 radio and can make
// phones leave an otherwise healthy access point.

struct UpstreamNetwork {
  const char* ssid;
  const char* password;
};

UpstreamNetwork UPSTREAM_NETWORKS[] = {
  { BAR_WIFI_SSID,  BAR_WIFI_PASSWORD },
  { WORK_WIFI_SSID, WORK_WIFI_PASSWORD },
  { HOME_WIFI_SSID, HOME_WIFI_PASSWORD },
};

const size_t UPSTREAM_NETWORK_COUNT =
  sizeof(UPSTREAM_NETWORKS) / sizeof(UPSTREAM_NETWORKS[0]);

const char* AP_SSID = "Cotton Flat Bar Quiz";
const char* AP_PASSWORD = "";  // Empty password means an open access point.
const uint8_t AP_CHANNEL = 1;
const uint8_t AP_MAX_CLIENTS = 8;

// Leave this false for the reliable quiz-only setup. Set it true only after
// entering real upstream credentials if internet routing is required.
const bool ENABLE_UPSTREAM_ROUTING = false;

const IPAddress PI_IP(192, 168, 4, 4);
const uint16_t PI_PORT = 5000;
const byte DNS_PORT = 53;

const IPAddress AP_IP(192, 168, 4, 1);
const IPAddress AP_GATEWAY(192, 168, 4, 1);
const IPAddress AP_SUBNET(255, 255, 255, 0);

const unsigned long WIFI_CHECK_INTERVAL_MS = 15000;

unsigned long lastWifiCheck = 0;
bool naptStarted = false;

WiFiMulti wifiMulti;
DNSServer dnsServer;
WebServer server(80);

String piUrl(const char* path) {
  return String("http://") + PI_IP.toString() + ":" + String(PI_PORT) + path;
}

String wifiStatusText(wl_status_t status) {
  switch (status) {
    case WL_CONNECTED:
      return "connected";
    case WL_IDLE_STATUS:
      return "idle";
    case WL_NO_SSID_AVAIL:
      return "ssid_not_found";
    case WL_CONNECT_FAILED:
      return "connect_failed";
    case WL_DISCONNECTED:
      return "disconnected";
    default:
      return "unknown";
  }
}

bool isPlaceholderNetwork(const UpstreamNetwork& network) {
  return String(network.ssid).startsWith("YOUR_") ||
         String(network.password).startsWith("YOUR_");
}

void handleMenu() {
  String html;
  html.reserve(2400);

  html += "<!doctype html><html><head>";
  html += "<meta charset='utf-8'>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>Cotton Flat Bar Quiz</title>";
  html += "<style>body{font-family:Arial,sans-serif;background:#0f1115;color:#f4f7ff;";
  html += "margin:0;padding:28px;text-align:center}.card{max-width:520px;margin:auto;";
  html += "padding:28px;border-radius:14px;background:#1b2029}.btn{display:block;";
  html += "margin:14px 0;padding:15px;border-radius:8px;background:#1d8f4d;color:#fff;";
  html += "font-weight:bold;text-decoration:none}.secondary{background:#2d5f9f}.muted{";
  html += "color:#b8c0cc;font-size:.95em}</style></head><body><main class='card'>";
  html += "<h1>🍺 Cotton Flat Bar Quiz</h1>";
  html += "<p>Connected to the quiz network.</p>";
  html += "<a class='btn' href='" + piUrl("/") + "'>Open Quiz Menu</a>";
  html += "<a class='btn secondary' href='" + piUrl("/quiz") + "'>Start Quiz</a>";
  html += "<a class='btn secondary' href='" + piUrl("/answers") + "'>View Answers</a>";
  html += "<p class='muted'>If a button does not open, confirm the Raspberry Pi is on this "
          "Wi-Fi network with static address " + PI_IP.toString() + ".</p>";
  html += "</main></body></html>";

  server.send(200, "text/html", html);
}

void handleStatus() {
  String json = "{";
  json += "\"ap_ssid\":\"" + String(AP_SSID) + "\",";
  json += "\"portal_ip\":\"" + WiFi.softAPIP().toString() + "\",";
  json += "\"pi_url\":\"" + piUrl("/") + "\",";
  json += "\"connected_clients\":" + String(WiFi.softAPgetStationNum()) + ",";
  json += "\"upstream_routing_enabled\":" + String(ENABLE_UPSTREAM_ROUTING ? "true" : "false") + ",";
  json += "\"upstream_ssid\":\"" + WiFi.SSID() + "\",";
  json += "\"upstream_status\":\"" + wifiStatusText(WiFi.status()) + "\",";
  json += "\"upstream_ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"nat_active\":" + String(naptStarted ? "true" : "false");
  json += "}";

  server.send(200, "application/json", json);
}

void startNat() {
  if (!ENABLE_UPSTREAM_ROUTING || naptStarted || WiFi.status() != WL_CONNECTED) {
    return;
  }

  ip_napt_enable(AP_IP, 1);
  dns_setserver(0, dns_getserver(0));
  naptStarted = true;

  Serial.print("NAT routing enabled: Cotton Flat Bar Quiz -> ");
  Serial.print(WiFi.SSID());
  Serial.println(" -> Internet.");
}

void stopNat() {
  if (!naptStarted) {
    return;
  }

  ip_napt_enable(AP_IP, 0);
  naptStarted = false;
  Serial.println("NAT routing disabled.");
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nCotton Flat Bar Quiz portal starting...");

  // AP-only mode is deliberate by default: it prevents background station
  // scans and reconnect attempts from interrupting the quiz access point.
  WiFi.mode(ENABLE_UPSTREAM_ROUTING ? WIFI_AP_STA : WIFI_AP);
  WiFi.setSleep(false);

  if (!WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET)) {
    Serial.println("Warning: could not configure AP address.");
  }

  if (!WiFi.softAP(AP_SSID, AP_PASSWORD, AP_CHANNEL, false, AP_MAX_CLIENTS)) {
    Serial.println("ERROR: Could not start Wi-Fi access point.");
  }

  if (ENABLE_UPSTREAM_ROUTING) {
    WiFi.setAutoReconnect(true);
    for (size_t i = 0; i < UPSTREAM_NETWORK_COUNT; i++) {
      if (isPlaceholderNetwork(UPSTREAM_NETWORKS[i])) {
        continue;
      }
      wifiMulti.addAP(UPSTREAM_NETWORKS[i].ssid, UPSTREAM_NETWORKS[i].password);
      Serial.print("Registered upstream network: ");
      Serial.println(UPSTREAM_NETWORKS[i].ssid);
    }
  }

  // Resolve captive-portal checks to this menu. Do not auto-redirect those
  // checks to the Pi: many phones interpret that as a failed portal and drop
  // or deprioritize the ESP32 network.
  dnsServer.start(DNS_PORT, "*", AP_IP);
  server.on("/", HTTP_GET, handleMenu);
  server.on("/esp32-status", HTTP_GET, handleStatus);
  server.onNotFound(handleMenu);
  server.begin();

  Serial.print("Portal menu available at http://");
  Serial.println(WiFi.softAPIP());
  Serial.print("Quiz server should be available at ");
  Serial.println(piUrl("/"));
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();
  delay(2);

  if (!ENABLE_UPSTREAM_ROUTING) {
    return;
  }

  const unsigned long nowMs = millis();
  if (nowMs - lastWifiCheck < WIFI_CHECK_INTERVAL_MS) {
    return;
  }

  lastWifiCheck = nowMs;

  if (WiFi.status() == WL_CONNECTED) {
    startNat();
    return;
  }

  stopNat();

  // Only scan/reconnect while no quiz players are connected, because the
  // ESP32 has one Wi-Fi radio for both AP and station operation.
  if (WiFi.softAPgetStationNum() == 0) {
    wifiMulti.run();
  }
}
