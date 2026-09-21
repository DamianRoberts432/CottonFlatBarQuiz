#include <WiFi.h>
#include <WiFiMulti.h>
#include <WebServer.h>
#include <DNSServer.h>
#include "lwip/lwip_napt.h"
#include "lwip/dns.h"

// Copy wifi_secrets.example.h to wifi_secrets.h beside this sketch and enter
// your upstream Wi-Fi credentials there. The local file is gitignored.
#include "wifi_secrets.h"

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

// Keep upstream routing disabled unless you explicitly need internet on the Pi
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
    case WL_CONNECTED: return "connected";
    case WL_IDLE_STATUS: return "idle";
    case WL_NO_SSID_AVAIL: return "ssid_not_found";
    case WL_CONNECT_FAILED: return "connect_failed";
    case WL_DISCONNECTED: return "disconnected";
    default: return "unknown";
  }
}

bool isPlaceholderNetwork(const UpstreamNetwork& network) {
  return String(network.ssid).startsWith("YOUR_") ||
         String(network.password).startsWith("YOUR_");
}

void handleMenu() {
  String html;
  html.reserve(2800);

  html += "<!doctype html><html><head>";
  html += "<meta charset='utf-8'>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>Cotton Flat Bar Quiz</title>";
  html += "<style>body{font-family:Arial,sans-serif;background:#0f1115;color:#f4f7ff;";
  html += "margin:0;padding:28px;text-align:center}.card{max-width:520px;margin:auto;";
  html += "padding:28px;border-radius:14px;background:#1b2029}.btn{display:block;";
  html += "margin:14px 0;padding:15px;border-radius:8px;background:#1d8f4d;color:#fff;";
  html += "font-weight:bold;text-decoration:none}.secondary{background:#2d5f9f}.gold{background:#d4af37}.admin{background:#455a64}.muted{";
  html += "color:#b8c0cc;font-size:.95em}</style></head><body><main class='card'>";
  html += "<h1>🍺 Cotton Flat Bar Quiz</h1>";
  html += "<p>Connected to the quiz network.</p>";
  
  // RESTORED WORKING SCHEMATIC WITH CUSTOM BUTTON NAMES AND GOLD USERS PLACEHOLDER
  html += "<a class='btn' href='/quiz'>Take Quiz</a>";
  html += "<a class='btn secondary' href='/answers'>See Answers</a>";
  html += "<a class='btn secondary' href='/submit-question'>Submit Question</a>";
  html += "<a class='btn gold' href='/gold-users'>Gold Users</a>"; 
  html += "<a class='btn admin' href='/admin'>Admin</a>";
  
  html += "<p class='muted'>If a button does not open, confirm the Raspberry Pi is active at " + PI_IP.toString() + ".</p>";
  html += "</main></body></html>";

  server.send(200, "text/html", html);
}

void handlePortalProbe() {
  String html;
  html.reserve(1000);
  html += "<!doctype html><html><head>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<meta http-equiv='refresh' content='0;url=/'>";
  html += "<title>Cotton Flat Bar Quiz</title></head><body style='font-family:Arial;text-align:center;padding:50px;'>";
  html += "<h2>Cotton Flat Bar Quiz</h2>";
  html += "<p>Opening quiz panel automatically...</p>";
  html += "<p><a href='/' style='display:inline-block;padding:12px;background:#1565c0;color:white;text-decoration:none;border-radius:5px;'>Tap here to open Quiz</a></p>";
  html += "</body></html>";
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

// Your verified captive portal filter logic that tracks destination strings
bool captivePortalFilter() {
  String host = server.hostHeader();
  host.toLowerCase();

  if (host == WiFi.softAPIP().toString() || host == String(PI_IP.toString()) || host == "localhost") {
    return false;
  }
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nCotton Flat Bar Quiz portal starting...");

  WiFi.mode(ENABLE_UPSTREAM_ROUTING ? WIFI_AP_STA : WIFI_AP);
  WiFi.setSleep(false);

  if (!WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET)) {
    Serial.println("Warning: could not configure AP address.");
  }

  if (!WiFi.softAP(AP_SSID, AP_PASSWORD, AP_CHANNEL, false, AP_MAX_CLIENTS)) {
    Serial.println("ERROR: Could not start Wi-Fi access point.");
  }

  dnsServer.start(DNS_PORT, "*", AP_IP);
  
  server.on("/", HTTP_GET, []() {
    if (!captivePortalFilter()) {
      handleMenu();
    } else {
      handlePortalProbe();
    }
  });
  
  server.on("/esp32-status", HTTP_GET, handleStatus);
  
  server.onNotFound([]() {
    if (!captivePortalFilter()) {
      handleMenu();
    } else {
      handlePortalProbe();
    }
  });
  
  server.begin();
  Serial.print("Local Hotspot Ready at http://");
  Serial.println(WiFi.softAPIP());
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();
  delay(2);
}
