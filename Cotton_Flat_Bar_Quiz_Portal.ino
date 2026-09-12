#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

const char* AP_SSID = "CottonFlatBar Quiz";
const char* PI_URL  = "http://192.168.4.2:5000/";
const byte DNS_PORT = 53;

DNSServer dnsServer;
WebServer server(80);

IPAddress apIP(192, 168, 4, 1);
IPAddress apGW(192, 168, 4, 1);
IPAddress apSN(255, 255, 255, 0);

bool isCaptiveProbe(const String& u) {
  return (u == "/generate_204" ||
          u == "/gen_204" ||
          u == "/hotspot-detect.html" ||
          u == "/library/test/success.html" ||
          u == "/success.txt" ||
          u == "/ncsi.txt" ||
          u == "/connecttest.txt");
}

void noCache() {
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Expires", "0");
}

void sendLaunchPage() {
  noCache();
  String html = "<!doctype html><html><head><meta charset='utf-8'/>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
                "<title>Cotton Flat Bar Quiz</title>"
                "<style>"
                "body{font-family:Arial,sans-serif;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f1115;color:#f4f7ff;padding:16px;}"
                ".card{width:min(92vw,460px);background:#171b24;border:1px solid #2a3242;border-radius:14px;padding:22px;box-shadow:0 8px 30px rgba(0,0,0,.25);text-align:center;}"
                "h1{margin:0 0 10px;font-size:1.2rem;}p{line-height:1.45;opacity:.95;}"
                ".btn{display:block;width:100%;margin-top:14px;padding:12px;border-radius:10px;text-decoration:none;font-weight:700;background:#2f7cf6;color:white;font-size:16px;}"
                ".muted{margin-top:12px;font-size:.85rem;opacity:.65;word-break:break-all;}"
                "</style></head><body><div class='card'>"
                "<h1>Connected to Cotton Flat Bar Quiz</h1>"
                "<p>Tap below to open the full quiz menu.</p>"
                "<a class='btn' href='" + String(PI_URL) + "'>Open Quiz Menu</a>"
                "<p class='muted'>Manual link: " + String(PI_URL) + "</p>"
                "</div>"
                "<script>setTimeout(function(){window.location.href='" + String(PI_URL) + "';},700);</script>"
                "</body></html>";
  server.send(200, "text/html", html);
}

void setup() {
  Serial.begin(115200);

  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(apIP, apGW, apSN);
  WiFi.softAP(AP_SSID); // open network
  dnsServer.start(DNS_PORT, "*", apIP);

  server.on("/", HTTP_GET, sendLaunchPage);

  server.on("/diag", HTTP_GET, []() {
    String out;
    out += "AP SSID: " + String(AP_SSID) + "\n";
    out += "AP IP: " + WiFi.softAPIP().toString() + "\n";
    out += "PI_URL: " + String(PI_URL) + "\n";
    server.send(200, "text/plain", out);
  });

  server.onNotFound([]() {
    if (isCaptiveProbe(server.uri())) {
      noCache();
      server.sendHeader("Location", "http://192.168.4.1/", true);
      server.send(302, "text/plain", "Redirecting...");
      return;
    }
    sendLaunchPage();
  });

  server.begin();
}

void loop() {
  dnsServer.processNextRequest();
  server.handleClient();
}
