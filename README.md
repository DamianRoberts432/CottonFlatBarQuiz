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

The sketch currently points its menu buttons at the Pi address `192.168.4.3:5000`. Connect the Pi to **Cotton Flat Bar Quiz**, ensure it has IP `192.168.4.3`, then start `Quiz.py`. If the Pi receives a different address, change `PI_HOST` in `esp32_portal.ino` and flash again.
