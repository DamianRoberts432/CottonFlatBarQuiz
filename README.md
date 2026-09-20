# Cotton Flat Bar Quiz

## Run the Raspberry Pi quiz

Copy `Quiz.py` to the Raspberry Pi and run:

```bash
python3 -m pip install flask
python3 Quiz.py
```

The quiz listens on port 5000. Its main pages are `/quiz`, `/answers`, `/submit-question`, and `/admin`. The default admin code is `1346`.

## ESP32 portal

Flash `esp32_portal.ino`. It creates the open Wi-Fi network **Cotton Flat Bar Quiz** and hosts the menu at `http://192.168.4.1`.

Classic ESP32 hardware is 2.4 GHz-only for Wi-Fi STA mode. Use upstream credentials for a 2.4 GHz SSID; a 5 GHz-only network will not connect.
Treat Wi-Fi credentials currently in `esp32_portal.ino` as compromised, rotate them, and set local values before flashing.

The sketch now targets the Pi at `192.168.4.4:5000` and assumes the Pi is configured with a fixed IP on the ESP32 access-point network. The Pi should be set to a static address in the `192.168.4.0/24` range, ideally `192.168.4.4`, and the ESP32 code should match it exactly.

If you change the Pi IP, update `PI_HOST` in `esp32_portal.ino` and restart the ESP32.
