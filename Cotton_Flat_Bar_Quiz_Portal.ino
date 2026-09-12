#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

// =====================================================
// CottonFlatBar ESP32 Captive Portal (AP + optional STA)
// =====================================================
//
// USER EXPERIENCE GOAL:
// - User joins open Wi-Fi: CottonFlatBar (no password)
// - Captive portal pops up automatically
// - User taps Continue -> goes to Pi quiz URL
//
// NOTES:
// - AP_PASSWORD is intentionally not used (open network).
// - STA credentials are only for ESP32 uplink to another AP (optional).
// - This sketch is for portal/onboarding, not full production routing.
//
// =====================================================

// ===== USER CONFIG =====
const char* AP_SSID = "CottonFlatBar";  // Open SSID (no password)

// Optional upstream Wi-Fi (ESP32 as station)
// Leave STA_SSID empty ("") to skip STA connect entirely.
const char* STA_SSID     = "YOUR_PI_WIFI_SSID";
const char* STA_PASSWORD = "";  // empty is valid for open upstream Wi-Fi

// Raspberry Pi quiz/service URL (update to your actual Pi endpoint)
const char* PI_URL = "http://192.168.4.2/";

// Captive DNS
const byte DNS_PORT = 53;
DNSServer dnsServer;
WebServer server(80);

// SoftAP IP settings
IPAddress apIP(192, 168, 4, 1);
IPAddress apGW(192, 168, 4, 1);
IPAddress apSN(255, 255, 255, 0);

// -------- HTML portal --------
String portalPage() {
  String html = R"HTML(
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>CottonFlatBar Quiz</title>
  <style>
    :root { color-scheme: light dark; }
    body{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
      background:#0f1115; color:#f4f7ff;
    }
    .card{
      width:min(92vw, 460px);
      background:#171b24; border:1px solid #2a3242; border-radius:14px;
      padding:22px;
      box-shadow:0 8px 30px rgba(0,0,0,.25);
    }
    h1{ margin:0 0 10px; font-size:1.2rem; }
    p{ margin:.4rem 0; line-height:1.45; opacity:.95; }
    .btn{
      display:inline-block; margin-top:14px; padding:11px 16px;
      border-radius:10px; text-decoration:none; font-weight:700;
      background:#2f7cf6; color:white;
    }
    .muted{ margin-top:12px; font-size:.92rem; opacity:.75; word-break:break-all; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Welcome to CottonFlatBar Quiz</h1>
    <p>You’re connected. Tap continue to start the quiz.</p>
    <a class="btn" href="%PI_URL%">Continue</a>
    <p class="muted">If needed, open this URL manually:<br>%PI_URL%</p>
  </div>
</body>
</html>
)HTML";

  html.replace("%PI_URL%", PI_URL);
  return html;
}

// -------- Captive helper --------
bool isCaptiveProbePath(const String& uri) {
  // Android
  if (uri == "/generate_204" || uri == "/gen_204") return true;
  // Apple
  if (uri == "/hotspot-detect.html" || uri == "/library/test/success.html") return true;
  // Windows / misc
  if (uri == "/connecttest.txt" || uri == "/ncsi.txt" || uri == "/success.txt" || uri == "/redirect") return true;

  return false;
}

void sendNoCacheHeaders() {
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Expires", "0");
}

void handlePortal() {
  sendNoCacheHeaders();
  server.send(200, "text/html", portalPage());
}

void handleRedirectToPortal() {
  sendNoCacheHeaders();
  server.sendHeader("Location", "http://192.168.4.1/", true);
  server.send(302, "text/plain", "Redirecting to portal...");
}

void handleContinue() {
  sendNoCacheHeaders();
  server.sendHeader("Location", PI_URL, true);
  server.send(302, "text/plain", "Opening quiz...");
}

void handleNotFound() {
  // Captive behavior: unknown host/path lands on portal
  if (isCaptiveProbePath(server.uri())) {
    if (server.uri() == "/generate_204" || server.uri() == "/gen_204") {
      // Force captive assistant to appear
      handleRedirectToPortal();
      return;
    }

    // Known probe paths can just show portal
    handlePortal();
    return;
  }

  // Minimal friction: instead of 404, show portal
  handlePortal();
}

void setupRoutes() {
  server.on("/", HTTP_GET, handlePortal);
  server.on("/continue", HTTP_GET, handleContinue);

  // Common captive probe endpoints
  server.on("/generate_204", HTTP_GET, handleRedirectToPortal);
  server.on("/gen_204", HTTP_GET, handleRedirectToPortal);
  server.on("/hotspot-detect.html", HTTP_GET, handlePortal);
  server.on("/library/test/success.html", HTTP_GET, handlePortal);
  server.on("/success.txt", HTTP_GET, []() { server.send(200, "text/plain", "success"); });
  server.on("/ncsi.txt", HTTP_GET, []() { server.send(200, "text/plain", "Microsoft NCSI"); });
  server.on("/connecttest.txt", HTTP_GET, []() { server.send(200, "text/plain", "Microsoft Connect Test"); });

  server.onNotFound(handleNotFound);
}

void connectSTAIfConfigured() {
  // If no STA SSID provided, skip station connect
  if (STA_SSID == nullptr || strlen(STA_SSID) == 0) {
    Serial.println("STA disabled (empty STA_SSID). Running AP-only portal.");
    WiFi.mode(WIFI_AP);
    return;
  }

  WiFi.mode(WIFI_AP_STA);
  WiFi.begin(STA_SSID, STA_PASSWORD);

  Serial.print("Connecting STA to '");
  Serial.print(STA_SSID);
  Serial.print("'");

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < 15000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("STA connected. STA IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("STA connect timeout; continuing with AP portal.");
  }
}

void setupOpenAP() {
  WiFi.softAPConfig(apIP, apGW, apSN);

  // OPEN AP (no password)
  bool ok = WiFi.softAP(AP_SSID);

  Serial.print("SoftAP start: ");
  Serial.println(ok ? "OK" : "FAIL");
  Serial.print("AP SSID: ");
  Serial.println(AP_SSID);
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());
}

void setupDNS() {
  // Wildcard DNS makes any hostname resolve to ESP32 AP IP for captive portal
  dnsServer.start(DNS_PORT, "*", apIP);
  Serial.println("DNS wildcard server started on port 53.");
}

void setup() {
  Serial.begin(115200);
  delay(250);

  connectSTAIfConfigured();
  setupOpenAP();
  setupDNS();
  setupRoutes();

  server.begin();
  Serial.println("HTTP server started.");
  Serial.println("Portal ready.");
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();
}
