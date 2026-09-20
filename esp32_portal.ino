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
  { "WTRG18-5G-1",            "wtrg070101" },
  // Home
  { "ATTEI7xz4u",              "t8cvkr6x4x+k" },
};
const size_t UPSTREAM_NETWORK_COUNT = sizeof(UPSTREAM_NETWORKS) / sizeof(UPSTREAM_NETWORKS[0]);
// -------------------------------------------

const char* AP_SSID = "Cotton Flat Bar Quiz"; // open network, no password
const char* PI_HOST = "192.168.4.4";
const uint16_t PI_PORT = 5000;

const byte DNS_PORT = 53;
IPAddress AP_IP(192, 168, 4, 1);
IPAddress AP_GATEWAY(192, 168, 4, 1);
IPAddress AP_SUBNET(255, 255, 255, 0);

// Wi-Fi Check Interval: Check upstream status every 5 seconds.
const unsigned long WIFI_CHECK_INTERVAL_MS = 5000; 
unsigned long lastWifiCheck = 0;
bool naptStarted = false;

WiFiMulti wifiMulti;
DNSServer dnsServer;
WebServer server(80);

String piUrl(const char* path) {
  return String("http://") + PI_HOST + ":" + String(PI_PORT) + path;
}

void handleMenu() {
  server.sendHeader("Location", piUrl("/"), true);
  server.send(302, "text/plain", "Opening Cotton Flat Bar Quiz...");
}

void handlePortalProbe() {
  // Captive Portal Hijack: Send back HTML that forces mobile devices to open their network modal
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
  json += "\"upstream_ssid\":\"" + WiFi.SSID() + "\",";
  json += "\"upstream_status\":\"" + staState + "\",";
  json += "\"upstream_ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"nat_active\":" + String(naptStarted ? "true" : "false");
  json += "}";
  server.send(200, "application/json", json);
}

void startNat() {
  if (naptStarted) return;
  ip_napt_enable(AP_IP, 1);
  dns_setserver(0, dns_getserver(0));
  naptStarted = true;
  Serial.print("NAT routing enabled: Cotton Flat Bar Quiz -> ");
  Serial.print(WiFi.SSID());
  Serial.println(" -> Internet.");
}

// Captive Portal Interceptor
bool captivePortalFilter() {
  String host = server.hostHeader();
  // If the request isn't targeted specifically at the ESP32 IP or the Raspberry Pi host IP,
  // it means a phone is running a background operating system internet check. Intercept it!
  if (host != WiFi.softAPIP().toString() && host != String(PI_HOST)) {
    handlePortalProbe();
    return true;
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nCotton Flat Bar Quiz portal starting...");

  WiFi.mode(WIFI_AP_STA);

  if (!WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET)) {
    Serial.println("Warning: could not configure AP address.");
  }
  if (!WiFi.softAP(AP_SSID)) {
    Serial.println("ERROR: Could not start Wi-Fi access point.");
  }

  for (size_t i = 0; i < UPSTREAM_NETWORK_COUNT; i++) {
    wifiMulti.addAP(UPSTREAM_NETWORKS[i].ssid, UPSTREAM_NETWORKS[i].password);
    Serial.print("Registered upstream network: ");
    Serial.println(UPSTREAM_NETWORKS[i].ssid);
  }
  
  wifiMulti.run();

  dnsServer.start(DNS_PORT, "*", AP_IP);
  
  server.on("/", HTTP_GET, []() {
    if (!captivePortalFilter()) handleMenu();
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
    if (!captivePortalFilter()) handlePortalProbe();
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
      if (!naptStarted) {
        startNat();
      }
    } else {
      naptStarted = false;
      // Protect active phone players: Only scan if no clients are presently active on the quiz
      if (WiFi.softAPgetStationNum() == 0) {
        if (wifiMulti.run() == WL_CONNECTED) {
          startNat();
        }
      }
    }
  }
}
