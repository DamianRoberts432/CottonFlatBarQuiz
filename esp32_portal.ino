#include <WiFi.h>
#include <WiFiMulti.h>
#include <WebServer.h>
#include <DNSServer.h>
#include "lwip/lwip_napt.h"
#include "lwip/dns.h"

// Cotton Flat Bar Quiz ESP32 captive portal + Wi-Fi NAT router.
//
// The ESP32 does two jobs at once:
//   1. STATION: joins whichever upstream Wi-Fi is available (tries every
//      network in UPSTREAM_NETWORKS, strongest signal wins) for internet
//      access. This covers all three locations: Cotton Flat, work, and home.
//   2. ACCESS POINT: broadcasts the open "Cotton Flat Bar Quiz" network for
//      the Raspberry Pi and patrons.
//
// Traffic from the AP side is NAT-forwarded out through whichever upstream
// Wi-Fi connected, so anything joined to "Cotton Flat Bar Quiz" -- including
// the Raspberry Pi -- gets real internet access (for `git pull`, etc.) while
// still being on the same local network as patrons for the quiz itself.
//
// This lets you power on the ESP32 + Pi at any of the three locations and
// have it "just work" using whichever upstream network is reachable, with no
// manual reconfiguration required.
//
// The USB cable to the Pi is power/serial only and is NOT used for
// networking; all traffic moves over Wi-Fi.
//
// IMPORTANT: Fill in all passwords below before flashing.

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
// This prevents background scanning from killing the AP broadcast.
const unsigned long WIFI_CHECK_INTERVAL_MS = 5000; 
unsigned long lastWifiCheck = 0;
bool naptStarted = false;

WiFiMulti wifiMulti;
DNSServer dnsServer;
WebServer server(80);

String piUrl(const char* path) {
  return String("http://") + PI_HOST + ":" + String(PI_PORT) + path;
}

const char MENU_STYLE[] PROGMEM = R"rawliteral(
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;padding:20px;display:flex;align-items:center;justify-content:center;font-family:Arial,sans-serif;color:#f4f7ff;background:#0f1115}.card{width:min(420px,100%);background:#1a1d24;border-radius:16px;padding:28px;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,.4)}h1{margin-top:0}.button{display:block;margin:14px 0;padding:14px;border-radius:10px;color:#fff;text-decoration:none;font-weight:bold}.quiz{background:#2e7d32}.answers{background:#1565c0}.submit{background:#8e24aa}.admin{background:#455a64}.subtitle{opacity:.8}.footer{opacity:.6;font-size:.85em;margin-top:10px}
</style>
)rawliteral";

void handleMenu() {
  // Send users directly to the Raspberry Pi quiz home page.
  server.sendHeader("Location", piUrl("/"), true);
  server.send(302, "text/plain", "Opening Cotton Flat Bar Quiz...");
}

void handlePortalProbe() {
  // Return a normal portal page for phone/OS connectivity checks, with an
  // immediate redirect and a manual fallback link if auto-opening is blocked.
  String html;
  html.reserve(1800);
  html += "<!doctype html><html><head>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<meta http-equiv='refresh' content='0;url=" + piUrl("/") + "'>";
  html += "<title>Cotton Flat Bar Quiz</title></head><body>";
  html += "<p>Opening Cotton Flat Bar Quiz...</p>";
  html += "<p><a href='" + piUrl("/") + "'>Tap here if it does not open automatically.</a></p>";
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
  // Enable IP forwarding + NAPT so devices on the "Cotton Flat Bar Quiz" AP
  // (192.168.4.0/24) can reach the internet through whichever upstream
  // network connected.
  ip_napt_enable(AP_IP, 1);
  // Point the AP-side DNS at whatever DNS the upstream network handed us so
  // clients (like the Pi) can resolve github.com, etc.
  dns_setserver(0, dns_getserver(0));
  naptStarted = true;
  Serial.print("NAT routing enabled: Cotton Flat Bar Quiz -> ");
  Serial.print(WiFi.SSID());
  Serial.println(" -> Internet.");
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

  // Register every known upstream network (Cotton Flat, work, home).
  for (size_t i = 0; i < UPSTREAM_NETWORK_COUNT; i++) {
    wifiMulti.addAP(UPSTREAM_NETWORKS[i].ssid, UPSTREAM_NETWORKS[i].password);
    Serial.print("Registered upstream network: ");
    Serial.println(UPSTREAM_NETWORKS[i].ssid);
  }
  
  // Initial check at startup
  wifiMulti.run();

  dnsServer.start(DNS_PORT, "*", AP_IP);
  server.on("/", HTTP_GET, handleMenu);
  server.on("/esp32-status", HTTP_GET, handleStatus);

  // Common captive-portal probe URLs. Serve the direct-to-quiz portal page.
  server.on("/generate_204", HTTP_GET, handlePortalProbe);
  server.on("/gen_204", HTTP_GET, handlePortalProbe);
  server.on("/hotspot-detect.html", HTTP_GET, handlePortalProbe);
  server.on("/library/test/success.html", HTTP_GET, handlePortalProbe);
  server.on("/ncsi.txt", HTTP_GET, handlePortalProbe);
  server.on("/connecttest.txt", HTTP_GET, handlePortalProbe);
  server.onNotFound(handlePortalProbe);
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

  unsigned long nowMs = millis();

  // Non-blocking timer: evaluate network status every 5 seconds.
  // This stops WiFiMulti from forcing continuous radio scans that disconnect clients.
  if (nowMs - lastWifiCheck >= WIFI_CHECK_INTERVAL_MS) {
    lastWifiCheck = nowMs;

    if (WiFi.status() == WL_CONNECTED) {
      if (!naptStarted) {
        startNat();
      }
    } else {
      // Station disconnected or hasn't found a network yet.
      naptStarted = false;
      Serial.println("Upstream Wi-Fi disconnected. Attempting background scan/reconnect...");
      
      // Safe to run scanning now because we are already disconnected upstream.
      if (wifiMulti.run() == WL_CONNECTED) {
        startNat();
      } else {
        Serial.println("Still scanning for an available upstream network...");
      }
    }
  }
}
