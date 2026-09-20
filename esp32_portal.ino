#include <WiFi.h>
#include <WiFiMulti.h>
#include <WebServer.h>
#include <DNSServer.h>
#include "lwip/lwip_napt.h"
#include "lwip/dns.h"

// Cotton Flat Bar Quiz ESP32 captive portal + Wi-Fi NAT router.
// ---------- EDIT BEFORE FLASHING ----------
// IMPORTANT: Classic ESP32 supports only 2.4 GHz Wi-Fi. SSIDs labelled "5G"
// are often 5 GHz-only and will not connect on this hardware.
// Security note: the credentials in this file should be treated as compromised.
// Rotate these Wi-Fi passwords and supply local values before flashing.
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

const unsigned long WIFI_STATUS_POLL_INTERVAL_MS = 1000;
const unsigned long WIFI_RETRY_MIN_MS = 3000;
const unsigned long WIFI_RETRY_MAX_MS = 60000;
const uint8_t WIFI_STALE_RESET_RETRY_COUNT = 5;

unsigned long lastWifiPollMs = 0;
unsigned long nextWifiRetryMs = 0;
uint8_t wifiRetryCount = 0;
bool naptStarted = false;
uint8_t lastDisconnectReason = 0;
String lastDisconnectReasonText = "none";

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
  bool upstreamHasIp = (WiFi.status() == WL_CONNECTED) &&
                       (WiFi.localIP() != IPAddress(0, 0, 0, 0));
  unsigned long nowMs = millis();
  unsigned long retryInMs = (nextWifiRetryMs > nowMs) ? (nextWifiRetryMs - nowMs) : 0;

  json += "\"ap_ssid\":\"" + String(AP_SSID) + "\",";
  json += "\"portal_ip\":\"" + WiFi.softAPIP().toString() + "\",";
  json += "\"pi_url\":\"" + piUrl("/") + "\",";
  json += "\"connected_clients\":" + String(WiFi.softAPgetStationNum()) + ",";
  json += "\"upstream_ssid\":\"" + WiFi.SSID() + "\",";
  json += "\"upstream_status\":\"" + staState + "\",";
  json += "\"upstream_ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"upstream_gateway\":\"" + WiFi.gatewayIP().toString() + "\",";
  json += "\"upstream_dns0\":\"" + WiFi.dnsIP(0).toString() + "\",";
  json += "\"upstream_dns1\":\"" + WiFi.dnsIP(1).toString() + "\",";
  json += "\"upstream_has_ip\":" + String(upstreamHasIp ? "true" : "false") + ",";
  json += "\"nat_active\":" + String(naptStarted ? "true" : "false") + ",";
  json += "\"last_disconnect_reason\":\"" + lastDisconnectReasonText + "\",";
  json += "\"last_disconnect_code\":" + String(lastDisconnectReason) + ",";
  json += "\"retry_in_ms\":" + String(retryInMs) + ",";
  json += "\"retry_count\":" + String(wifiRetryCount);
  json += "}";
  server.send(200, "application/json", json);
}

bool hasValidUpstreamIp() {
  return (WiFi.status() == WL_CONNECTED) &&
         (WiFi.localIP() != IPAddress(0, 0, 0, 0)) &&
         (WiFi.gatewayIP() != IPAddress(0, 0, 0, 0));
}

const char* disconnectReasonToText(uint8_t reason) {
  switch (reason) {
    case 1: return "unspecified";
    case 2: return "auth_expired";
    case 4: return "assoc_expired";
    case 8: return "assoc_leave";
    case 15: return "4way_handshake_timeout";
    case 201: return "no_ap_found";
    case 202: return "auth_fail";
    case 203: return "assoc_fail";
    case 204: return "handshake_timeout";
    default: return "other";
  }
}

void configureUpstreamDns() {
  IPAddress dns0 = WiFi.dnsIP(0);
  if (dns0 == IPAddress(0, 0, 0, 0)) {
    return;
  }

  ip_addr_t dnsAddr0;
  ip_addr_t dnsAddr1;
  dnsAddr0.type = IPADDR_TYPE_V4;
  dnsAddr1.type = IPADDR_TYPE_V4;
  dnsAddr0.u_addr.ip4.addr = ipaddr_addr(dns0.toString().c_str());
  dnsAddr1.u_addr.ip4.addr = ipaddr_addr(WiFi.dnsIP(1).toString().c_str());
  dns_setserver(0, &dnsAddr0);
  dns_setserver(1, &dnsAddr1);
}

void clearUpstreamDns() {
  ip_addr_t emptyDns;
  emptyDns.type = IPADDR_TYPE_V4;
  emptyDns.u_addr.ip4.addr = ipaddr_addr("0.0.0.0");
  dns_setserver(0, &emptyDns);
  dns_setserver(1, &emptyDns);
}

void startNatIfReady() {
  if (naptStarted || !hasValidUpstreamIp()) return;
  ip_napt_enable(AP_IP, 1);
  naptStarted = true;
  Serial.print("NAT routing enabled: Cotton Flat Bar Quiz -> ");
  Serial.print(WiFi.SSID());
  Serial.println(" -> Internet.");
}

void stopNat() {
  if (!naptStarted) return;
  ip_napt_enable(AP_IP, 0);
  naptStarted = false;
  Serial.println("NAT routing disabled until upstream reconnects.");
}

void scheduleNextRetry() {
  unsigned long backoffMs = WIFI_RETRY_MIN_MS;
  if (wifiRetryCount > 0) {
    uint8_t exponent = wifiRetryCount > 4 ? 4 : wifiRetryCount;
    backoffMs <<= exponent;
  }
  if (backoffMs > WIFI_RETRY_MAX_MS) {
    backoffMs = WIFI_RETRY_MAX_MS;
  }
  nextWifiRetryMs = millis() + backoffMs;
  wifiRetryCount++;
}

void onWiFiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
    lastDisconnectReason = info.wifi_sta_disconnected.reason;
    lastDisconnectReasonText = disconnectReasonToText(lastDisconnectReason);
    stopNat();
    clearUpstreamDns();
    if (nextWifiRetryMs == 0) {
      scheduleNextRetry();
    }
    Serial.print("Upstream disconnected. reason=");
    Serial.print(lastDisconnectReasonText);
    Serial.print(" (");
    Serial.print(lastDisconnectReason);
    Serial.println(")");
  } else if (event == ARDUINO_EVENT_WIFI_STA_GOT_IP) {
    wifiRetryCount = 0;
    nextWifiRetryMs = 0;
    configureUpstreamDns();
    Serial.print("Upstream connected: ");
    Serial.print(WiFi.SSID());
    Serial.print(" ");
    Serial.println(WiFi.localIP());
  }
}

void attemptUpstreamReconnect() {
  if (hasValidUpstreamIp()) {
    wifiRetryCount = 0;
    nextWifiRetryMs = 0;
    configureUpstreamDns();
    startNatIfReady();
    return;
  }

  unsigned long nowMs = millis();
  if (nextWifiRetryMs == 0) {
    scheduleNextRetry();
  }
  if (nowMs < nextWifiRetryMs) {
    return;
  }

  if (wifiRetryCount >= WIFI_STALE_RESET_RETRY_COUNT) {
    // Clear stale STA state after repeated failures, but keep AP/portal running.
    WiFi.disconnect(false, true);
  }

  wl_status_t state = wifiMulti.run(750);
  if (state == WL_CONNECTED && hasValidUpstreamIp()) {
    wifiRetryCount = 0;
    nextWifiRetryMs = 0;
    configureUpstreamDns();
    startNatIfReady();
    return;
  }

  scheduleNextRetry();
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
  WiFi.setSleep(false);
  WiFi.onEvent(onWiFiEvent);

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
    if (String(UPSTREAM_NETWORKS[i].ssid).indexOf("5G") >= 0) {
      Serial.println("  note: SSID name contains '5G'; classic ESP32 cannot join 5 GHz-only APs.");
    }
  }

  scheduleNextRetry();
  attemptUpstreamReconnect();

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

  if (nowMs - lastWifiPollMs >= WIFI_STATUS_POLL_INTERVAL_MS) {
    lastWifiPollMs = nowMs;
    if (!hasValidUpstreamIp()) {
      stopNat();
    }
    attemptUpstreamReconnect();
  }
}
