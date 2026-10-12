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
- `/gold-users` — participant leaderboard by drink-token progress
- `/games` — games menu
- `/games/dopewars` — text-based Dopewars game
- `/games/drawing` — Drawing with Friends
- `/tv` — full-screen TV display (Dopewars high scores, or the drawing game while a round runs)
- `/admin` — host administration

## Wi-Fi hotspot (Pi, no ESP32)

The Pi's built-in Wi-Fi broadcasts the open network **Cotton Flat Bar Quiz** and the Pi is `192.168.4.1` on it. The USB Wi-Fi dongle stays connected to the bar's internet, so Raspberry Pi Connect keeps working. Set it up once, from the repo folder on the Pi:

```bash
sudo bash setup-hotspot.sh
```

The script refuses to run if the built-in Wi-Fi is the Pi's only internet connection. Unplug the ESP32 afterwards so two networks don't share the same name.

The hotspot answers every name lookup with `192.168.4.1`, and the quiz also listens on port 80 (`PORTAL_PORT=80` in `cotton-flat-quiz.service`). A phone's "is there internet?" check is redirected to `http://192.168.4.1/`, so the sign-in popup opens the main menu. Once the phone opens any quiz page, its next check gets a success reply, so the popup shows **Done** and the phone stays connected.

`esp32_portal.ino` is the old ESP32 version of this and is no longer needed.

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

### Drawing with Friends

`/games/drawing`: someone taps **Start a New Round**, players join with a name, and any joined player taps **Start Drawing**. Everyone gets the same random prompt and 2 minutes to draw on their phone (drawings auto-submit when time runs out). Each drawing is then shown on the TV for 15 seconds in join order, after which the TV goes back to Dopewars scores. The admin page has **End Current Drawing Round** for stuck rounds. Only the last 10 rounds' drawings are kept in `quiz.db`.

## TV display

Plug a TV into the Pi's HDMI and open `http://127.0.0.1:5000/tv` full screen. To start it automatically when the Pi desktop logs in:

```bash
mkdir -p ~/.config/autostart
printf '[Desktop Entry]
Type=Application
Name=Quiz TV
Exec=chromium-browser --kiosk --noerrdialogs --disable-infobars --incognito http://127.0.0.1:5000/tv
' > ~/.config/autostart/quiz-tv.desktop
```

On newer Raspberry Pi OS the browser command may be `chromium` instead of `chromium-browser`. Press `Alt+F4` to close kiosk mode.

## ESP32 secrets

Keep `wifi_secrets.h` local and do not commit credentials.
