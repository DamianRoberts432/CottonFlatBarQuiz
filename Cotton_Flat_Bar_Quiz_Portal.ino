#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

// ===== USER CONFIG =====
const char* AP_SSID     = "CottonFlatBar";
const char* AP_PASSWORD = "cottonflatbar";   // min 8 chars

// Upstream network (optional but recommended for option 2)
const char* STA_SSID     = "YOUR_PI_WIFI_SSID";
const char* STA_PASSWORD = "YOUR_PI_WIFI_PASSWORD";

// Where your Pi web service lives:
const char* PI_URL = "http://192.168.4.2/";  // change if needed

// Captive portal DNS
const byte DNS_PORT = 53;
DNSServer dnsServer;
WebServer server(80);

// SoftAP IP settings
IPAddress apIP(192, 168, 4, 1);
IPAddress apGW(192, 168, 4, 1);
IPAddress apSN(255, 255, 255, 0);

// ===== HTML =====
String portalPage() {
  String html = R"HTML(
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>CottonFlatBar Portal</title>
  <style>
    body{font-family:Arial,sans-serif;margin:0;background:#111;color:#fff;display:flex;min-height:100vh;align-items:center;justify-content:center}
    .card{max-width:420px;width:92%;background:#1b1b1b;border:1px solid #333;border-radius:14px;padding:22px}
    h1{font-size:1.2rem;margin:0 0 12px}
    p{opacity:.9;line-height:1.4}
    a.btn{display:inline-block;margin-top:14px;padding:10px 14px;border-radius:10px;text-decoration:none;background:#2f7cf6;color:#fff;font-weight:600}
    .small{margin-top:12px;font-size:.9rem;opacity:.75}
  </style>
</head>
<body>
  <div class="card">
    <h1>Connected to CottonFlatBar</h1>
    <p>Tap continue to open the Raspberry Pi service.</p>
    <a class="btn" href="%PI_URL%">Continue</a>
    <div class="small">If this window closes, open a browser and visit: %PI_URL%</div>
  </div>
</body>
</html>
)HTML";
  html.replace("%PI_URL%", PI_URL);
  return html;
}

bool isCaptiveProbePath(const String& uri) {
  // Common captive portal checks by OS/vendors
  return uri == "/generate_204" || uri == "/gen_204" ||          // Android
         uri == "/hotspot-detect.html" || uri == "/library/test/success.html" || // Apple
         uri == "/success.txt" ||                                 // Some systems
         uri == "/ncsi.txt" || uri == "/connecttest.txt" || uri == "/redirect";   // Windows/Misc
}

void handlePortal() {
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.send(200, "text/html", portalPage());
}

void handleRedirectToPortal() {
  server.sendHeader("Location", "http://192.168.4.1/", true);
  server.send(302, "text/plain", "Redirecting to portal...");
}

void handleNotFound() {
  // For captive behavior, unknown hosts/paths should land at portal
  if (isCaptiveProbePath(server.uri())) {
    // For probe endpoints, return expected-ish response or redirect
    if (server.uri() == "/generate_204" || server.uri() == "/gen_204") {
      // returning 302 encourages captive portal popup
      handleRedirectToPortal();
      return;
    }
    handlePortal();
    return;
  }

  // Minimal interception: show portal instead of hard 404
  handlePortal();
}

void setupRoutes() {
  // Root portal
  server.on("/", HTTP_GET, handlePortal);

  // Explicit continue endpoint if you prefer:
  server.on("/continue", HTTP_GET, []() {
    server.sendHeader("Location", PI_URL, true);
    server.send(302, "text/plain", "Opening Pi...");
  });

  // Captive probe endpoints
  server.on("/generate_204", HTTP_GET, handleRedirectToPortal);
  server.on("/gen_204", HTTP_GET, handleRedirectToPortal);
  server.on("/hotspot-detect.html", HTTP_GET, handlePortal);
  server.on("/library/test/success.html", HTTP_GET, handlePortal);
  server.on("/success.txt", HTTP_GET, [](){ server.send(200, "text/plain", "success"); });
  server.on("/ncsi.txt", HTTP_GET, [](){ server.send(200, "text/plain", "Microsoft NCSI"); });
  server.on("/connecttest.txt", HTTP_GET, [](){ server.send(200, "text/plain", "Microsoft Connect Test"); });

  server.onNotFound(handleNotFound);
}

void connectSTA() {
  WiFi.mode(WIFI_AP_STA);
  WiFi.begin(STA_SSID, STA_PASSWORD);

  Serial.print("Connecting STA");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("STA connected. IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("STA not connected (continuing AP portal mode).");
  }
}

void setupAP() {
  WiFi.softAPConfig(apIP, apGW, apSN);
  bool ok = WiFi.softAP(AP_SSID, AP_PASSWORD);
  Serial.print("SoftAP start: ");
  Serial.println(ok ? "OK" : "FAIL");
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());
}

void setupDNS() {
  // Wildcard DNS: every domain resolves to ESP32 AP IP for captive behavior
  dnsServer.start(DNS_PORT, "*", apIP);
  Serial.println("DNS server started.");
}

void setup() {
  Serial.begin(115200);
  delay(300);

  connectSTA();
  setupAP();
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
