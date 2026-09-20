#include <WiFi.h>
#include <WiFiMulti.h>
#include <WebServer.h>
#include <DNSServer.h>
#include "lwip/lwip_napt.h"
#include "lwip/dns.h"

// Cotton Flat Bar Quiz ESP32 captive portal + Wi-Fi NAT router.
// ---------- EDIT BEFORE FLASHING ----------
struct UpstreamNetwork {
  const char* ssid;
  const char* password;
};

UpstreamNetwork UPSTREAM_NETWORKS[] = {
  // Cotton Flat (bar)
  { "suddenlink.net-3680-5G", "251159005545" },
  // Work
  { "WTRG_2GEXT",            "wtrg070101" },
  { "WTRG18-5G-1",            "wtrg070101" },
  // Home
  { "ATTEI7xz4u",              "t8cvkr6x4x+k" },
};
const size_t UPSTREAM_NETWORK_COUNT = sizeof(UPSTREAM_NETWORKS) / sizeof(UPSTREAM_NETWORKS[0]);
// -------------------------------------------

const char* AP_SSID = "Cotton Flat Bar Quiz"; // open network, no password
const char* AP_PASSWORD = "";                 // empty password = open AP
const char* PI_HOST = "192.168.4.4";
const uint16_t PI_PORT = 5000;

const byte DNS_PORT = 53;
const IPAddress AP_IP(192, 168, 4, 1);
const IPAddress AP_GATEWAY(192, 168, 4, 1);
const IPAddress AP_SUBNET(255, 255, 255, 0);

// Wi-Fi check interval: check upstream status every 5 seconds.
const unsigned long WIFI_CHECK_INTERVAL_MS = 5000;
unsigned long lastWifiCheck = 0;
bool naptStarted = false;

WiFiMulti wifiMulti;
DNSServer dnsServer;
WebServer server(80);

String piUrl(const char* path) {
  return String("http://") + PI_HOST + ":" + String(PI_PORT) + path;
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

void handleMenu() {
  server.sendHeader("Location", piUrl("/"), true);
  server.send(302, "text/plain", "Opening Cotton Flat Bar Quiz...");
}

void handlePortalProbe() {
  String html;
  html.reserve(1800);
  html += "<!doctype html><html><head>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<meta http-equiv='refresh' content='0;url=" + piUrl("/") + "'>";
  html += "<title>Cotton Flat Bar Quiz</title></head><body style='font-family:Arial;text-align:center;padding:50px;'>";
  html += "<h2>Cotton Flat Bar Quiz</h2>";
  html += "<p>Opening quiz panel automatically...</p>";
  html += "<p><a href='" + piUrl("/") + "' style='display:inline-block;padding:12px;background:#1565c0;color:white;text-decoration:none;border-radius:5px;'>Tap here to open Quiz</a></p>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleStatus() {
  String staState = wifiStatusText(WiFi.status());

  String json = "{";
  json += "\"ap_ssid\":\"" + String(AP_SSID) + "\",";
  json += "\"portal_ip\":\"" + WiFi.softAPIP().toString() + "\",";
  json += "\"pi_url\":\"" + piUrl("/") + "\",";
  json += "\"connected_clients\":" + String(WiFi.softAPgetStationNum()) + ",";
  json += "\"upstream_ssid\":\"" + WiFi.SSID() + "\",";
  json += "\"upstream_status\":\"" + staState + "\",";
  json += "\"upstream_ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"nat_active\":" + String(naptStarted ? "true" : "false");
  json += "}";

  server.send(200, "application/json", json);
}

void startNat() {
  if (naptStarted || WiFi.status() != WL_CONNECTED) {
    return;
  }

  // Enable NAT only after the ESP32 has an upstream internet connection.
  ip_napt_enable(AP_IP, 1);

  // Make sure the AP can still resolve DNS while NAT is active.
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

// Captive Portal Interceptor
bool captivePortalFilter() {
  String host = server.hostHeader();
  host.toLowerCase();

  // Allow access to the ESP32 AP and the Raspberry Pi.
  if (host == WiFi.softAPIP().toString() || host == String(PI_HOST)) {
    return false;
  }

  // Also allow direct local access to the Pi host if requested by IP.
  if (host == String(PI_HOST) || host == "localhost") {
    return false;
  }

  // Everything else looks like an OS background check or a captive portal probe.
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nCotton Flat Bar Quiz portal starting...");

  WiFi.mode(WIFI_AP_STA);
  WiFi.setSleep(false);

  if (!WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET)) {
    Serial.println("Warning: could not configure AP address.");
  }

  if (!WiFi.softAP(AP_SSID, AP_PASSWORD, 1, false, 8)) {
    Serial.println("ERROR: Could not start Wi-Fi access point.");
  }

  for (size_t i = 0; i < UPSTREAM_NETWORK_COUNT; i++) {
    wifiMulti.addAP(UPSTREAM_NETWORKS[i].ssid, UPSTREAM_NETWORKS[i].password);
    Serial.print("Registered upstream network: ");
    Serial.println(UPSTREAM_NETWORKS[i].ssid);
  }

  // Try to join the strongest known Wi-Fi immediately.
  wifiMulti.run();

  dnsServer.start(DNS_PORT, "*", AP_IP);

  server.on("/", HTTP_GET, []() {
    if (!captivePortalFilter()) {
      handleMenu();
    } else {
      handlePortalProbe();
    }
  });

  server.on("/esp32-status", HTTP_GET, handleStatus);

  // Catch-all OS probe endpoints to force portal popups
  server.on("/generate_204", HTTP_GET, handlePortalProbe);
  server.on("/gen_204", HTTP_GET, handlePortalProbe);
  server.on("/hotspot-detect.html", HTTP_GET, handlePortalProbe);
  server.on("/library/test/success.html", HTTP_GET, handlePortalProbe);
  server.on("/ncsi.txt", HTTP_GET, handlePortalProbe);
  server.on("/connecttest.txt", HTTP_GET, handlePortalProbe);

  server.onNotFound([]() {
    if (!captivePortalFilter()) {
      handleMenu();
    } else {
      handlePortalProbe();
    }
  });

  server.begin();
  Serial.println("Portal Engine active.");
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();

  unsigned long nowMs = millis();

  if (nowMs - lastWifiCheck >= WIFI_CHECK_INTERVAL_MS) {
    lastWifiCheck = nowMs;

    if (WiFi.status() == WL_CONNECTED) {
      startNat();
    } else {
      stopNat();

      // Protect active phone players: only scan if no clients are on the quiz AP.
      if (WiFi.softAPgetStationNum() == 0) {
        if (wifiMulti.run() == WL_CONNECTED) {
          startNat();
        }
      }
    }
  }
}
