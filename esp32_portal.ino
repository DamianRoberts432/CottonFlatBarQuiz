#include <WiFi.h>
#include <WiFiMulti.h>
#include <WebServer.h>
#include <DNSServer.h>
#include "lwip/lwip_napt.h"
#include "lwip/dns.h"

// Cotton Flat Bar Quiz ESP32 captive portal + Wi-Fi NAT router.
//
// IMPORTANT:
// - Replace the placeholder upstream Wi-Fi credentials below before flashing.
// - Do not commit real Wi-Fi passwords to GitHub.
// - This file must be named CottonFlatBarQuiz.ino when it is in the
//   CottonFlatBarQuiz repository/sketch folder.

struct UpstreamNetwork {
  const char* ssid;
  const char* password;
};

UpstreamNetwork UPSTREAM_NETWORKS[] = {
  { "YOUR_BAR_WIFI_SSID",  "YOUR_BAR_WIFI_PASSWORD" },
  { "YOUR_WORK_WIFI_SSID", "YOUR_WORK_WIFI_PASSWORD" },
  { "YOUR_HOME_WIFI_SSID", "YOUR_HOME_WIFI_PASSWORD" },
};

const size_t UPSTREAM_NETWORK_COUNT =
  sizeof(UPSTREAM_NETWORKS) / sizeof(UPSTREAM_NETWORKS[0]);

const char* AP_SSID = "Cotton Flat Bar Quiz";
const char* AP_PASSWORD = "";  // Empty password means an open access point.

const char* PI_HOST = "192.168.4.4";
const uint16_t PI_PORT = 5000;

const byte DNS_PORT = 53;

const IPAddress AP_IP(192, 168, 4, 1);
const IPAddress AP_GATEWAY(192, 168, 4, 1);
const IPAddress AP_SUBNET(255, 255, 255, 0);

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
  html += "<title>Cotton Flat Bar Quiz</title></head>";
  html += "<body style='font-family:Arial;text-align:center;padding:50px;'>";
  html += "<h2>Cotton Flat Bar Quiz</h2>";
  html += "<p>Opening quiz panel automatically...</p>";
  html += "<p><a href='" + piUrl("/");
  html += "' style='display:inline-block;padding:12px;background:#1565c0;";
  html += "color:white;text-decoration:none;border-radius:5px;'>";
  html += "Tap here to open Quiz</a></p>";
  html += "</body></html>";

  server.send(200, "text/html", html);
}

void handleStatus() {
  String json = "{";
  json += "\"ap_ssid\":\"" + String(AP_SSID) + "\",";
  json += "\"portal_ip\":\"" + WiFi.softAPIP().toString() + "\",";
  json += "\"pi_url\":\"" + piUrl("/") + "\",";
  json += "\"connected_clients\":" + String(WiFi.softAPgetStationNum()) + ",";
  json += "\"upstream_ssid\":\"" + WiFi.SSID() + "\",";
  json += "\"upstream_status\":\"" + wifiStatusText(WiFi.status()) + "\",";
  json += "\"upstream_ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"nat_active\":" + String(naptStarted ? "true" : "false");
  json += "}";

  server.send(200, "application/json", json);
}

void startNat() {
  if (naptStarted || WiFi.status() != WL_CONNECTED) {
    return;
  }

  ip_napt_enable(AP_IP, 1);

  // Preserve the currently configured DNS server while NAT is enabled.
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

bool captivePortalFilter() {
  String host = server.hostHeader();
  host.toLowerCase();

  const String apHost = WiFi.softAPIP().toString();
  const String piHost = String(PI_HOST);

  // Allow direct access to the ESP32 and Raspberry Pi quiz server.
  if (host == apHost || host == piHost || host == "localhost") {
    return false;
  }

  // Treat all other hosts as captive-portal detection requests.
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

  // Attempt to connect immediately.
  wifiMulti.run();

  // Resolve every requested domain to the portal IP.
  dnsServer.start(DNS_PORT, "*", AP_IP);

  server.on("/", HTTP_GET, []() {
    if (captivePortalFilter()) {
      handlePortalProbe();
    } else {
      handleMenu();
    }
  });

  server.on("/esp32-status", HTTP_GET, handleStatus);

  // Common captive portal detection endpoints.
  server.on("/generate_204", HTTP_GET, handlePortalProbe);
  server.on("/gen_204", HTTP_GET, handlePortalProbe);
  server.on("/hotspot-detect.html", HTTP_GET, handlePortalProbe);
  server.on("/library/test/success.html", HTTP_GET, handlePortalProbe);
  server.on("/ncsi.txt", HTTP_GET, handlePortalProbe);
  server.on("/connecttest.txt", HTTP_GET, handlePortalProbe);

  server.onNotFound([]() {
    if (captivePortalFilter()) {
      handlePortalProbe();
    } else {
      handleMenu();
    }
  });

  server.begin();

  Serial.print("Portal Engine active at http://");
  Serial.println(WiFi.softAPIP());
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();

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

  // Do not interrupt active quiz players with a new upstream scan.
  if (WiFi.softAPgetStationNum() == 0 && wifiMulti.run() == WL_CONNECTED) {
    startNat();
  }
}
