# Cotton Flat Bar Quiz

Raspberry Pi Flask quiz. The Pi broadcasts the "Cotton Flat Bar Quiz" Wi-Fi itself and phones get the menu as a sign-in popup.

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
curl http://192.168.4.1:5000/health
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
- `/admin` — host administration, split into tabs: Players & Tokens, Questions (search, 25 per page), Submissions, TV Screens & Ads, Games & Prompts
- `/advertise` — patrons upload an ad picture for the TV (shows CashApp $Drob432 and prices)

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
http://192.168.4.1:5000/games
```

The first game is a Python text-based Dopewars implementation at:

```text
http://192.168.4.1:5000/games/dopewars
```

Players trade across NYC locations with day-by-day price changes, travel events, bank/debt actions, and a final score after day 30.

### Drawing with Friends

`/games/drawing`: sign in with your name and PIN and tap **Join the Game**. Any player at the table taps **Start Round**: everyone gets the same random prompt, 10 seconds to get ready and 90 seconds to draw (drawings auto-submit). The TV and phones then show the drawings numbered, and everyone at the table votes on their phone for a favourite that isn't their own; voting closes when everyone has voted or after 45 seconds. The drawing with the most votes earns its artist 1 point (ties all score). People who join while a round is running play from the next round, and each new player resets everyone's score to 0. **Admin > Games & Prompts** has **End Current Drawing Round** for stuck rounds and the prompt list, where the host can add, edit and delete prompts. Only the last 10 rounds' drawings are kept in `quiz.db`.

## TV display

Plug a TV into the Pi's HDMI. `sudo bash setup-hotspot.sh` also sets the desktop to open `http://127.0.0.1:5000/tv` in its own maximised window at every login, so the taskbar stays usable. To open it right now:

```bash
chromium-browser --app=http://127.0.0.1:5000/tv --start-maximized &
```

On newer Raspberry Pi OS the browser command may be `chromium` instead of `chromium-browser`. To stop it opening at login: `rm ~/.config/autostart/quiz-tv.desktop`.

The TV rotates Dopewars high scores, Drawing with Friends scores and MVPs (most visits) every 12 seconds, and switches to the drawing game during a round. **Admin > TV Screens & Ads** can rename, hide or clear each board, remove single Dopewars scores, and add message screens. Ads uploaded at `/advertise` wait there until the host checks CashApp for payment and taps **Paid: Approve**. A $25 company ad then stays on the TV for 2 months, a $5 shoutout for 1 week, and each one drops off by itself when its time is up. Ad pictures (PNG, JPG, GIF or WebP, up to 3 MB) are stored in `quiz.db`, so they survive updates. **Play as Host** on the admin page lets the host take the quiz and play the games, and the player table has **Rename** for fixing names.

## ESP32 secrets

Keep `wifi_secrets.h` local and do not commit credentials.
