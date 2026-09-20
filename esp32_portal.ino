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
const unsigned long WIFI_CONNECT_TIMEOUT_MS = 1500;
const uint8_t WIFI_STALE_RESET_RETRY_COUNT = 5;
const uint8_t WIFI_STA_DNS_SLOTS = 2;

unsigned long lastWifiPollMs = 0;
unsigned long nextWifiRetryMs = 0;
bool wifiRetryScheduled = false;
uint8_t wifiRetryCount = 0;
bool naptStarted = false;
uint8_t lastDisconnectReason = 255;
String lastDisconnectReasonText = "unavailable";
bool staleResetApplied = false;
wl_status_t lastStaStatus = WL_DISCONNECTED;

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
  unsigned long retryInMs = 0;
  if (wifiRetryScheduled) {
    unsigned long elapsedSinceRetryPoint = nowMs - nextWifiRetryMs;
    if (elapsedSinceRetryPoint >= 0x80000000UL) {
      unsigned long remainingMs = nextWifiRetryMs - nowMs;
      retryInMs = remainingMs;
    }
  }

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
    case 255: return "unavailable";
    default: return "other";
  }
}

void setDnsSlot(uint8_t slot, IPAddress dns) {
  ip_addr_t dnsAddr;
  if (dns == IPAddress(0, 0, 0, 0)) {
    IP_ADDR4(&dnsAddr, 0, 0, 0, 0);
  } else {
    IP_ADDR4(&dnsAddr, dns[0], dns[1], dns[2], dns[3]);
  }
  dns_setserver(slot, &dnsAddr);
}

void configureUpstreamDns() {
  for (uint8_t i = 0; i < WIFI_STA_DNS_SLOTS; i++) {
    setDnsSlot(i, WiFi.dnsIP(i));
  }
}

void clearUpstreamDns() {
  for (uint8_t i = 0; i < WIFI_STA_DNS_SLOTS; i++) {
    setDnsSlot(i, IPAddress(0, 0, 0, 0));
  }
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
  wifiRetryScheduled = true;
}

void markUpstreamConnected(bool logConnect) {
  wifiRetryCount = 0;
  wifiRetryScheduled = false;
  staleResetApplied = false;
  configureUpstreamDns();
  startNatIfReady();
  if (logConnect) {
    Serial.print("Upstream connected: ");
    Serial.print(WiFi.SSID());
    Serial.print(" ");
    Serial.println(WiFi.localIP());
  }
}

void handleStaStatusTransitions() {
  wl_status_t staStatus = WiFi.status();
  if (staStatus == WL_CONNECTED && hasValidUpstreamIp() && wifiRetryScheduled) {
    markUpstreamConnected(false);
  }
  if (staStatus == lastStaStatus) {
    return;
  }
  lastStaStatus = staStatus;

  if (staStatus == WL_CONNECTED && hasValidUpstreamIp()) {
    markUpstreamConnected(true);
    return;
  }
  if (staStatus == WL_CONNECTED) {
    // Connected state may appear briefly before DHCP/gateway data is available.
    stopNat();
    clearUpstreamDns();
    if (!wifiRetryScheduled) {
      scheduleNextRetry();
    }
    return;
  }

  staleResetApplied = false;
  stopNat();
  clearUpstreamDns();
  if (!wifiRetryScheduled) {
    scheduleNextRetry();
  }
  Serial.println("Upstream disconnected.");
}

void attemptUpstreamReconnect() {
  if (hasValidUpstreamIp()) {
    markUpstreamConnected(false);
    return;
  }

  unsigned long nowMs = millis();
  if (!wifiRetryScheduled) {
    nextWifiRetryMs = millis();
    wifiRetryScheduled = true;
  }
  if ((long)(nowMs - nextWifiRetryMs) < 0) {
    return;
  }

  uint8_t apClients = WiFi.softAPgetStationNum();
  if (apClients > 0 && wifiRetryCount >= WIFI_STALE_RESET_RETRY_COUNT) {
    // Defer heavier stale-state reset while AP clients are active.
    scheduleNextRetry();
    return;
  }

  if (wifiRetryCount >= WIFI_STALE_RESET_RETRY_COUNT && !staleResetApplied) {
    // Reset STA state without leaving AP+STA mode or erasing credentials.
    WiFi.disconnect(false, false);
    WiFi.reconnect();
    wifiRetryCount = 0;
    staleResetApplied = true;
    scheduleNextRetry();
    return;
  }

  wl_status_t state = wifiMulti.run(WIFI_CONNECT_TIMEOUT_MS);
  if (state == WL_CONNECTED && hasValidUpstreamIp()) {
    markUpstreamConnected(false);
    return;
  }

  if (wifiRetryCount < 255) {
    wifiRetryCount++;
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
  Serial.println("Reminder: classic ESP32 STA works only on 2.4 GHz upstream Wi-Fi.");

  nextWifiRetryMs = millis();
  wifiRetryScheduled = true;
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
  handleStaStatusTransitions();

  unsigned long nowMs = millis();

  if (nowMs - lastWifiPollMs >= WIFI_STATUS_POLL_INTERVAL_MS) {
    lastWifiPollMs = nowMs;
    if (!hasValidUpstreamIp()) {
      stopNat();
    }
    attemptUpstreamReconnect();
  }
}
