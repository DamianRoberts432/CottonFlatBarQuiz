#include <WiFi.h>
#include <WiFiMulti.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <HTTPClient.h>
#include "lwip/lwip_napt.h"
#include "lwip/dns.h"

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
const char* AP_PASSWORD = ""; 
const uint8_t AP_CHANNEL = 1;
const uint8_t AP_MAX_CLIENTS = 8;

const bool ENABLE_UPSTREAM_ROUTING = false;

const IPAddress PI_IP(192, 168, 4, 4);
const uint16_t PI_PORT = 5000;
const byte DNS_PORT = 53;
const unsigned long PI_HEALTH_TIMEOUT_MS = 1200;
const unsigned long PI_HEALTH_CACHE_MS = 5000;

const IPAddress AP_IP(192, 168, 4, 1);
const IPAddress AP_GATEWAY(192, 168, 4, 1);
const IPAddress AP_SUBNET(255, 255, 255, 0);

WiFiMulti wifiMulti;
DNSServer dnsServer;
WebServer server(80);

unsigned long lastPiHealthCheck = 0;
bool piHealthy = false;
bool piHealthChecked = false;

String piUrl(const char* path) {
  return String("http://") + PI_IP.toString() + ":" + String(PI_PORT) + path;
}

bool checkPiHealth() {
  HTTPClient http;
  http.setConnectTimeout(PI_HEALTH_TIMEOUT_MS);
  http.setTimeout(PI_HEALTH_TIMEOUT_MS);
  if (!http.begin(piUrl("/health"))) return false;
  int statusCode = http.GET(); 
  http.end();
  return statusCode == HTTP_CODE_OK;
}

void refreshPiHealthIfNeeded() {
  unsigned long currentMillis = millis();
  if (piHealthChecked && currentMillis - lastPiHealthCheck < PI_HEALTH_CACHE_MS) return;
  piHealthy = checkPiHealth();
  piHealthChecked = true;
  lastPiHealthCheck = currentMillis;
}

String piHealthIndicator() {
  if (piHealthy) return "<p class='health online'>● Quiz server online</p>";
  return "<p class='health offline'>● Quiz server unreachable — check the Raspberry Pi.</p>";
}

void handleMenu() {
  refreshPiHealthIfNeeded();
  String html;
  html.reserve(3400);
  html += "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>Cotton Flat Bar Quiz</title>";
  html += "<style>body{font-family:Arial,sans-serif;background:#0f1115;color:#f4f7ff;margin:0;padding:28px;text-align:center}.card{max-width:520px;margin:auto;padding:28px;border-radius:14px;background:#1b2029}.btn{display:block;margin:14px 0;padding:15px;border-radius:8px;background:#1d8f4d;color:#fff;font-weight:bold;text-decoration:none}.secondary{background:#2d5f9f}.gold{background:#d4af37}.admin{background:#455a64}.muted{color:#b8c0cc;font-size:.95em}.health{padding:12px;border-radius:8px;font-weight:bold}.online{background:#123f26;color:#80efad}.offline{background:#4b1f26;color:#ffb4bd}</style></head><body><main class='card'>";
  html += "<h1>🍺 Cotton Flat Bar Quiz</h1><p>Connected to the quiz network.</p>";
  html += piHealthIndicator();
  
  html += "<a class='btn' href='" + piUrl("/quiz") + "'>Take Quiz</a>";
  html += "<a class='btn secondary' href='" + piUrl("/answers") + "'>See Answers</a>";
  html += "<a class='btn secondary' href='" + piUrl("/submit-question") + "'>Submit Question</a>";
  html += "<a class='btn gold' href='" + piUrl("/gold-users") + "'>Gold Users</a>"; 
  html += "<a class='btn admin' href='" + piUrl("/admin") + "'>Admin</a>";
  
  html += "<p class='muted'>Quiz System Pipeline Active.</p></main></body></html>";
  server.send(200, "text/html", html);
}

void handlePortalProbe() {
  String html = "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='refresh' content='0;url=/'></head></html>";
  server.send(200, "text/html", html);
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);
  WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET);
  WiFi.softAP(AP_SSID, AP_PASSWORD, AP_CHANNEL, false, AP_MAX_CLIENTS);
  dnsServer.start(DNS_PORT, "*", AP_IP);

  server.on("/", HTTP_GET, []() {
    String host = server.hostHeader();
    if (host == WiFi.softAPIP().toString() || host.startsWith("192.168.4.1")) handleMenu();
    else handlePortalProbe();
  });

  server.onNotFound([]() {
    String host = server.hostHeader();
    // Drop all background lookups meant for the Pi IP so the phone routes them naturally over the local channel
    if (host.startsWith("192.168.4.4") || server.method() == HTTP_POST) {
      server.send(404, "text/plain", "Passthrough");
    } else {
      handlePortalProbe();
    }
  });

  server.begin();
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();
  delay(2);
}
