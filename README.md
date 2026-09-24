# Cotton Flat Bar Quiz

Raspberry Pi Flask quiz with an ESP32 captive-portal menu.

## Raspberry Pi setup

The Flask app listens on port `5000` and is started by systemd from:

```text
/home/d/CottonFlatBarQuiz/Quiz.py
```

Quiz data, including per-PIN answer progress, is stored locally in:

```text
/home/d/CottonFlatBarQuiz/quiz.db
```

You can override the database location at runtime with the `COTTON_FLAT_DB_PATH` environment variable. If the database file does not exist yet, the app creates it automatically.

Install the dependency:

```bash
python3 -m pip install flask
```

Run manually for testing:

```bash
cd /home/d/CottonFlatBarQuiz
python3 Quiz.py
```

Check the service health endpoint:

```bash
curl http://127.0.0.1:5000/health
```

Expected response:

```json
{"ok":true,"service":"CottonFlatBarQuiz"}
```

## Start and manage the services

After installing or changing the service files:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cotton-flat-quiz-update.service
sudo systemctl enable cotton-flat-quiz.service
sudo systemctl restart cotton-flat-quiz.service
```

`restart` stops the currently running Flask process and starts a fresh one. The main service depends on the update service, so the update step runs before the quiz service when systemd starts the dependency chain.

Useful diagnostics:

```bash
systemctl status cotton-flat-quiz.service --no-pager
journalctl -u cotton-flat-quiz.service -n 100 --no-pager
journalctl -fu cotton-flat-quiz.service
curl http://192.168.4.4:5000/health
```

To force a code update immediately:

```bash
sudo systemctl restart cotton-flat-quiz-update.service
sudo systemctl restart cotton-flat-quiz.service
```

## Routes

- `/` — Flask menu
- `/health` — machine-readable health check
- `/quiz` — take the quiz
- `/answers` — community answers
- `/submit-question` — submit a question
- `/games` — games menu
- `/games/dopewars` — text-based Dopewars game
- `/admin` — host administration

## ESP32 portal

Flash `esp32_portal.ino` to the ESP32. It creates the open Wi-Fi network **Cotton Flat Bar Quiz** and hosts the portal menu at:

```text
http://192.168.4.1
```

The ESP32 menu sends quiz requests to the Raspberry Pi at:

```text
http://192.168.4.4:5000
```

The Pi must use `192.168.4.4` on the ESP32 access-point network. If that address changes, update `PI_IP` in `esp32_portal.ino`, reflash the ESP32, and restart the Flask service on the Pi.

The ESP32 checks `/health` before displaying the menu. An offline indicator means the Pi service is not reachable; it does not necessarily indicate an ESP32 failure.

## Games

The Flask app includes a games menu at:

```text
http://192.168.4.4:5000/games
```

The first game is a Python text-based Dopewars implementation at:

```text
http://192.168.4.4:5000/games/dopewars
```

Players trade across NYC locations with day-by-day price changes, travel events, bank/debt actions, and a final score after day 30.

## ESP32 secrets

Keep `wifi_secrets.h` local and do not commit credentials.
