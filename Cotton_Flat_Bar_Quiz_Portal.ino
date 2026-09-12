#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

const char* AP_SSID = "CottonFlatBar Quiz"; 
const char* PI_URL  = "http://192.168.4"; // Explicit target address
const byte DNS_PORT = 53;

DNSServer dnsServer;
WebServer server(80);
IPAddress apIP(192, 168, 4, 1);
IPAddress apGW(192, 168, 4, 1);
IPAddress apSN(255, 255, 255, 0);

String portalPage() {
    // Fixed string replacement mapping rules to prevent text cutoff bugs
    String html = "<!doctype html><html><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width,initial-scale=1'/><title>Hub</title>";
    html += "<style>body{font-family:sans-serif;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f1115;color:#f4f7ff;}";
    html += ".card{width:min(92vw,460px);background:#171b24;border:1px solid #2a3242;border-radius:14px;padding:22px;box-shadow:0 8px 30px rgba(0,0,0,.25);text-align:center;}";
    html += "h1{margin:0 0 10px;font-size:1.3rem;}p{line-height:1.45;opacity:.95;}.btn{display:block;margin-top:20px;padding:12px;border-radius:10px;text-decoration:none;font-weight:700;background:#2f7cf6;color:white;font-size:17px;}";
    html += ".btn:hover{background:#1666d3;}.muted{margin-top:15px;font-size:.85rem;opacity:.5;word-break:break-all;}</style></head>";
    html += "<body><div class='card'><h1>Cotton Flat Bar Quiz</h1><p>Connected to the network hub. Tap below to launch your assignment card.</p>";
    html += "<a class='btn' href='TARGET_URL'>Continue to Quiz</a><p class='muted'>Manual link: TARGET_URL</p></div></body></html>";
    html += "</div></body></html>";
    
    html.replace("TARGET_URL", PI_URL); 
    return html;
}

bool isCaptiveProbe(const String& u) {
    return (u=="/generate_204"||u=="/gen_204"||u=="/hotspot-detect.html"||u=="/library/test/success.html"||u=="/success.txt"||u=="/ncsi.txt");
}

void setup() {
    Serial.begin(115200);
    WiFi.mode(WIFI_AP);
    WiFi.softAPConfig(apIP, apGW, apSN);
    WiFi.softAP(AP_SSID);
    dnsServer.start(DNS_PORT, "*", apIP);
    
    server.on("/", HTTP_GET, [](){ server.send(200, "text/html", portalPage()); });
    server.onNotFound([](){
        if(isCaptiveProbe(server.uri())) {
            server.sendHeader("Location", "http://192.168.4", true);
            server.send(302, "text/plain", ""); return;
        }
        server.send(200, "text/html", portalPage());
    });
    server.begin();
}

void loop() {
    dnsServer.processNextRequest();
    server.handleClient();
}
