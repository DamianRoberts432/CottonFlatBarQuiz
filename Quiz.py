import base64
from collections import Counter
from contextlib import closing
from datetime import datetime
from html import escape
import json
import math
import os
import random
import re
import secrets
import sqlite3
import threading
import time

from flask import Flask, Response, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get(
    "COTTON_FLAT_SECRET", "cotton-flat-bar-secret-key-1346"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("COTTON_FLAT_DB_PATH", os.path.join(BASE_DIR, "quiz.db"))
SOURCE_FILE_PATH = os.path.abspath(__file__)
ADMIN_PASS = os.environ.get("COTTON_FLAT_ADMIN_PASS", "1346")
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))
PORTAL_PORT = int(os.environ.get("PORTAL_PORT", "0"))
PORTAL_HOST = os.environ.get("COTTON_FLAT_PORTAL_HOST", "192.168.4.1")

MAX_QUESTION_LENGTH = 500
MAX_OPTION_LENGTH = 200
MAX_RESPONSE_LENGTH = 2000
MIN_PIN_LENGTH = 4
MAX_PIN_LENGTH = 20
TOKEN_MILESTONE = 20

DOPEWARS_START_CASH = 2000
DOPEWARS_START_DEBT = 5500
DOPEWARS_GAME_DAYS = 30
DOPEWARS_CAPACITY = 100
DOPEWARS_LOCATIONS = ["Bronx", "Ghetto", "Central Park", "Manhattan", "Coney Island", "Brooklyn"]
DOPEWARS_PRICE_RANGES = {
    "Weed": (80, 450),
    "Acid": (600, 2600),
    "Cocaine": (1000, 6500),
    "Heroin": (2200, 11000),
    "Meth": (500, 3800),
    "Shrooms": (120, 900),
}
DOPEWARS_LOCATION_MULTIPLIER = {
    "Bronx": 1.0,
    "Ghetto": 0.9,
    "Central Park": 1.05,
    "Manhattan": 1.25,
    "Coney Island": 0.95,
    "Brooklyn": 1.1,
}
DOPEWARS_INTEREST_RATE = 0.1

DRAWING_PREP_SECONDS = 10
DRAWING_SECONDS = 90
DRAWING_VOTE_SECONDS = 45
DRAWING_RESULTS_SECONDS = 12
DRAWING_SUBMIT_GRACE_SECONDS = 5
DRAWING_LOBBY_TIMEOUT_SECONDS = 20 * 60
DRAWING_MAX_IMAGE_CHARS = 400_000
DRAWING_KEEP_ROUNDS = 10
DRAWING_IMAGE_RE = re.compile(r"data:image/(jpeg|png);base64,([A-Za-z0-9+/=]+)")
DRAWING_PROMPTS = [
    "A cowboy riding a giant chicken",
    "The bartender on their day off",
    "A cat running for mayor",
    "Your worst haircut ever",
    "A dinosaur at a job interview",
    "The last slice of pizza fighting back",
    "A tractor in a fancy restaurant",
    "Bigfoot on a first date",
    "A goat doing karaoke",
    "The world's laziest superhero",
    "A raccoon stealing a beer",
    "What your dog dreams about",
    "A pickle with a secret",
    "An armadillo starting a band",
    "A cactus that wants a hug",
    "Grandma on a motorcycle",
    "A fish who thinks it's a bird",
    "The ghost of a cheeseburger",
    "A haunted jukebox",
    "Aliens visiting a gas station",
    "A cow getting a tattoo",
    "A snowman on vacation in Texas",
    "A spider wearing eight boots",
    "The most dramatic sneeze in history",
    "A frog winning the lottery",
    "A robot learning to line dance",
    "Your phone if it could talk back",
    "A squirrel planning a heist",
    "A potato's family portrait",
    "The moon getting a sunburn",
    "A shark at the dentist",
    "Elvis buying groceries",
    "A pirate who is scared of water",
    "A horse trying to use a smartphone",
    "The world's angriest cupcake",
    "A wizard stuck in traffic",
    "A chicken crossing the road (and why)",
    "A pig with a fancy mustache",
    "A UFO abducting a pickup truck",
    "A mermaid at a car wash",
]


def strip_internal_round_labels(text):
    if text is None:
        return ""
    cleaned = re.sub(r"\s*\(\s*Round\s+\d+\s*\)\s*", " ", str(text), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


OPEN_QUESTION_TEMPLATES = [
    "What tiny social rule do people pretend is normal even though it makes absolutely no sense?",
    "What is the funniest status symbol someone can own while insisting they do not care about status?",
    "What behavior instantly tells you that someone is the main character in their own documentary?",
    "What is the most suspiciously specific thing someone can say at a party before you quietly leave?",
    "What social ritual would you delete from humanity if you had one mildly powerful afternoon?",
    "What is your best example of a group of adults collectively pretending to know what is happening?",
    "What harmless opinion turns a peaceful dinner into a tiny constitutional crisis?",
    "What is the strangest unofficial rule in your friend group, and who invented it?",
    "What object do people buy mainly so other people know they are the kind of person who buys it?",
    "What is the clearest sign that a gathering has crossed from fun into an anthropological field study?",
    "What kind of person is most likely to say ‘I hate drama’ immediately before creating drama?",
    "What is the most impressive social maneuver you have witnessed in a queue, meeting, or group chat?",
    "What ordinary convenience has made people dramatically less capable of interacting with one another?",
    "What is the funniest way people perform being busy when they are actually avoiding one task?",
    "What social behavior deserves a warning label but somehow remains legal?",
    "What is the most revealing thing a person can do when nobody is technically watching?",
    "What phrase sounds polite but is actually a tiny verbal weapon?",
    "What is the most chaotic way a friend group has ever made a simple decision?",
    "What would your personal sociology textbook call the unwritten law of your household?",
    "What is the most accurate one-sentence diagnosis of modern group chats?",
    "What harmless habit becomes deeply weird when a whole group does it together?",
    "What is the funniest example of people confusing confidence with competence?",
    "What social expectation do you obey only because you fear becoming tonight’s anecdote?",
    "What kind of public behavior makes you think, ‘This person has never faced consequences’?",
    "What is the most creative excuse someone has used to avoid a perfectly reasonable invitation?",
    "What is one thing people claim is about convenience when it is obviously about showing off?",
    "What is the funniest disagreement your friends could debate for three hours without learning anything?",
    "What is the strongest evidence that humans are just fancy herd animals with calendars?",
    "What social role do you accidentally become whenever a group starts making plans?",
    "What is the best example of a trend that is really just mass coordinated peer pressure?",
    "What is the weirdest thing people do to look relaxed while being obviously stressed?",
    "What is your favorite example of a person refusing to admit they are lost?",
    "What is the most dramatic way someone has reacted to a very small inconvenience?",
    "What social custom would aliens find hardest to explain in their report about Earth?",
    "What is the funniest lie people tell themselves about why they keep checking their phone?",
    "What behavior says ‘I am trying to seem mysterious’ but actually says ‘I forgot the conversation’?",
    "What is the most accurate unofficial job title for the responsible person in your friend group?",
    "What is one social skill people wildly overestimate in themselves?",
    "What is the best example of a crowd becoming one shared brain cell?",
    "What is your favorite tiny act of rebellion against an unnecessary social rule?",
]

OPEN_SUFFIXES = [
    "Answer as honest as you like",
]

DELETED_SEED_QUESTION_NUMBERS = []

CHOICE_QUESTIONS = [
    ("Which group-chat role has the most social power despite doing the least work?", ["The person who says ‘following’", "The reaction-button monarch", "The silent reader", "The accidental voice-echoer"]),
    ("Which item is most likely to become a Veblen good at a painfully fashionable café?", ["Plain tap water", "A tiny pastry with a French name", "A suspiciously expensive tote bag", "A normal-size coffee"]),
    ("What is the classic sign of an in-group boundary?", ["A secret handshake", "Shared slang outsiders do not understand", "Everyone wearing identical shoes", "A committee meeting"]),
    ("Which situation best demonstrates diffusion of responsibility?", ["One person cooking dinner", "A crowd watching everyone else call for help", "A friend answering a text", "Someone labeling leftover containers"]),
    ("Which is the strongest example of conspicuous consumption?", ["Buying a used paperback", "Wearing a luxury item mainly for recognition", "Packing lunch", "Repairing a bicycle"]),
    ("What is the most likely result of group polarization?", ["A group becomes more moderate", "A group drifts toward a more extreme shared view", "Nobody changes their mind", "Everyone leaves the room"]),
    ("Which setting is the clearest example of a ‘third place’?", ["A bedroom", "A workplace cubicle", "A neighborhood bar or café", "An airport security line"]),
    ("What does the IKEA effect describe?", ["Hating flat-pack furniture", "Valuing something more because you helped make it", "Buying Scandinavian snacks", "Forgetting where you parked"]),
    ("Which behavior is closest to impression management?", ["Choosing a profile photo strategically", "Forgetting your own birthday", "Eating leftovers", "Misplacing your keys"]),
    ("What does social loafing mean?", ["Relaxing at a beach", "Putting in less effort when responsibility is shared", "Avoiding small talk", "Walking slowly in a museum"]),
    ("Which example best fits a moral panic?", ["A calm town meeting", "A public frenzy claiming a harmless trend will destroy society", "A disagreement over pizza", "A quiet library"]),
    ("Which option is a classic example of a norm violation?", ["Saying thank you", "Standing silently facing the back of a crowded elevator", "Arriving early", "Returning a borrowed book"]),
    ("What does the bystander effect predict?", ["People help faster in crowds", "People may be less likely to help when others are present", "People never help strangers", "People only help family"]),
    ("Which choice best demonstrates cultural capital?", ["Knowing which fork to use at a formal dinner", "Owning a raincoat", "Counting your steps", "Bringing exact change"]),
    ("What is a reference group?", ["A random mailing list", "A group used as a standard for evaluating yourself", "A jury", "A family tree"]),
    ("Which behavior best illustrates reciprocity?", ["Ignoring a favor", "Returning a favor because someone helped you", "Changing your password", "Buying identical socks"]),
    ("What is a self-fulfilling prophecy?", ["A prediction that helps cause the outcome it predicts", "A weather forecast", "A lucky guess", "A rumor nobody believes"]),
    ("Which example best shows role conflict?", ["Having one hobby", "Being asked to be both an employee and a caregiver at the same time", "Wearing two hats", "Changing seats"]),
    ("What is the decoy effect?", ["A third option makes one of two original options look better", "A product disappears from a shelf", "A magician distracts a crowd", "A friend changes the subject"]),
    ("Which choice is most clearly an achieved status?", ["Age", "A degree earned through study", "Birth order", "Eye color"]),
]


def now():
    return datetime.now().isoformat(timespec="seconds")


def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def ensure_column(conn, table, column, definition):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def seed_question_number(seed_key):
    match = re.fullmatch(r"(?:choice|open)-(\d+)", str(seed_key or ""))
    return int(match.group(1)) if match else None


def next_available_question_number(used_numbers):
    question_number = 1
    while question_number in used_numbers:
        question_number += 1
    return question_number


def make_seed_questions():
    questions = []
    deleted_numbers = set(DELETED_SEED_QUESTION_NUMBERS)
    for index in range(200):
        question_number = index + 1
        if question_number in deleted_numbers:
            continue
        if index % 5 == 0:
            text, options = CHOICE_QUESTIONS[(index // 5) % len(CHOICE_QUESTIONS)]
            questions.append({"seed_key": f"choice-{question_number}", "question_number": question_number, "text": text, "is_open_text": 0, "options": options})
        else:
            base = OPEN_QUESTION_TEMPLATES[index % len(OPEN_QUESTION_TEMPLATES)]
            suffix = OPEN_SUFFIXES[(index // len(OPEN_QUESTION_TEMPLATES)) % len(OPEN_SUFFIXES)]
            questions.append({"seed_key": f"open-{question_number}", "question_number": question_number, "text": f"{base}{suffix}", "is_open_text": 1, "options": []})
    return questions


def record_deleted_seed_question_number(question_number):
    existing_numbers = set(DELETED_SEED_QUESTION_NUMBERS)
    if question_number in existing_numbers:
        return False
    existing_numbers.add(question_number)
    numbers = ", ".join(str(number) for number in sorted(existing_numbers))
    with open(SOURCE_FILE_PATH, "r", encoding="utf-8") as source_file:
        source = source_file.read()
    updated_source, replacements = re.subn(
        r"DELETED_SEED_QUESTION_NUMBERS = \[[^\]]*\]",
        f"DELETED_SEED_QUESTION_NUMBERS = [{numbers}]",
        source,
        count=1,
    )
    if replacements != 1:
        raise RuntimeError("Could not update deleted seed question numbers in source file")
    with open(SOURCE_FILE_PATH, "w", encoding="utf-8") as source_file:
        source_file.write(updated_source)
    DELETED_SEED_QUESTION_NUMBERS[:] = sorted(existing_numbers)
    return True


def init_db():
    conn = db_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL,
            is_open_text INTEGER NOT NULL DEFAULT 1, op1 TEXT DEFAULT '', op2 TEXT DEFAULT '',
            op3 TEXT DEFAULT '', op4 TEXT DEFAULT '', approved INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER NOT NULL,
            choice INTEGER NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS text_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER NOT NULL,
            author TEXT NOT NULL DEFAULT 'Anonymous', message TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, is_open_text INTEGER NOT NULL DEFAULT 1,
            op1 TEXT DEFAULT '', op2 TEXT DEFAULT '', op3 TEXT DEFAULT '', op4 TEXT DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT, pin TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS participant_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, participant_id INTEGER NOT NULL, question_id INTEGER NOT NULL,
            created_at TEXT NOT NULL, FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
            FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE,
            UNIQUE(participant_id, question_id)
        );
        CREATE TABLE IF NOT EXISTS drink_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT, participant_id INTEGER NOT NULL, milestone INTEGER NOT NULL,
            created_at TEXT NOT NULL, redeemed_at TEXT, FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
            UNIQUE(participant_id, milestone)
        );
        CREATE TABLE IF NOT EXISTS drawing_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT, prompt TEXT NOT NULL, status TEXT NOT NULL,
            created_at REAL NOT NULL, draw_ends_at REAL, reveal_started_at REAL, ended_at REAL
        );
        CREATE TABLE IF NOT EXISTS drawing_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, round_id INTEGER NOT NULL, player_token TEXT NOT NULL,
            nickname TEXT NOT NULL, joined_at REAL NOT NULL, image TEXT, submitted_at REAL,
            FOREIGN KEY(round_id) REFERENCES drawing_rounds(id) ON DELETE CASCADE,
            UNIQUE(round_id, player_token)
        );
        CREATE TABLE IF NOT EXISTS drawing_players (
            player_token TEXT PRIMARY KEY, participant_id INTEGER, nickname TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0, joined_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS drawing_votes (
            round_id INTEGER NOT NULL, voter_token TEXT NOT NULL, entry_id INTEGER NOT NULL, voted_at REAL NOT NULL,
            PRIMARY KEY(round_id, voter_token)
        );
        CREATE TABLE IF NOT EXISTS tv_screens (key TEXT PRIMARY KEY, title TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS tv_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS dopewars_scores (
            participant_id INTEGER PRIMARY KEY,
            top_score INTEGER NOT NULL,
            achieved_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE
        );
    """)
    ensure_column(conn, "questions", "seed_key", "TEXT")
    ensure_column(conn, "questions", "question_number", "INTEGER")
    ensure_column(conn, "drawing_rounds", "prep_ends_at", "REAL")
    ensure_column(conn, "drawing_rounds", "vote_started_at", "REAL")
    ensure_column(conn, "drawing_rounds", "results_started_at", "REAL")
    ensure_column(conn, "drawing_rounds", "winners", "TEXT")
    ensure_column(conn, "participants", "name", "TEXT")
    ensure_column(conn, "participants", "name_key", "TEXT")
    ensure_column(conn, "participants", "pin_hash", "TEXT")
    ensure_column(conn, "participants", "login_count", "INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_participants_name_key ON participants(name_key)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_seed_key ON questions(seed_key)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_question_number ON questions(question_number)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_approved_id ON questions(approved, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_votes_question_id ON votes(question_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_question_id ON text_responses(question_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_participant_answers_participant ON participant_answers(participant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_participant ON drink_tokens(participant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dopewars_scores_top_score ON dopewars_scores(top_score DESC, achieved_at ASC)")

    existing_count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    if existing_count == 0:
        for item in make_seed_questions():
            options = item["options"] + [""] * 4
            conn.execute("""INSERT INTO questions
                (text, is_open_text, op1, op2, op3, op4, approved, created_at, seed_key, question_number)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""", (
                    strip_internal_round_labels(item["text"])[:MAX_QUESTION_LENGTH], item["is_open_text"],
                    options[0][:MAX_OPTION_LENGTH], options[1][:MAX_OPTION_LENGTH],
                    options[2][:MAX_OPTION_LENGTH], options[3][:MAX_OPTION_LENGTH], now(), item["seed_key"], item["question_number"]))

    for row in conn.execute("SELECT id, text FROM questions WHERE text IS NOT NULL"):
        cleaned = strip_internal_round_labels(row["text"])
        if cleaned != row["text"]:
            conn.execute("UPDATE questions SET text = ? WHERE id = ?", (cleaned, row["id"]))
    for row in conn.execute("SELECT id, text FROM suggestions WHERE text IS NOT NULL"):
        cleaned = strip_internal_round_labels(row["text"])
        if cleaned != row["text"]:
            conn.execute("UPDATE suggestions SET text = ? WHERE id = ?", (cleaned, row["id"]))

    missing_numbers = conn.execute("SELECT COUNT(*) FROM questions WHERE question_number IS NULL").fetchone()[0]
    if missing_numbers:
        used_numbers = {
            row["question_number"]
            for row in conn.execute("SELECT question_number FROM questions WHERE question_number IS NOT NULL")
        }
        for row in conn.execute("SELECT id, seed_key FROM questions WHERE question_number IS NULL ORDER BY id ASC"):
            number = seed_question_number(row["seed_key"])
            if number is None or number in used_numbers:
                number = next_available_question_number(used_numbers)
            conn.execute("UPDATE questions SET question_number = ? WHERE id = ?", (number, row["id"]))
            used_numbers.add(number)

    conn.commit()
    conn.close()


BASE_STYLE = """
<style>
*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#0f1115;color:#f4f7ff;padding:20px;margin:0;min-height:100vh;display:flex;justify-content:center}.card{width:min(900px,100%);background:#171b22;border:1px solid #2a3140;border-radius:12px;padding:20px;box-shadow:0 10px 30px rgba(0,0,0,.25)}.left{display:flex;flex-direction:column;gap:12px}.muted{color:#a7b0c0}.error{background:#4a1b1b;border:1px solid #6d2f2f;padding:10px;border-radius:8px;color:#ffd1d1}.notice{background:#182d1e;border:1px solid #2b4e34;padding:10px;border-radius:8px;color:#d7f9d1}.btn{display:inline-block;padding:10px 18px;border-radius:8px;text-decoration:none;color:#fff;font-weight:700;cursor:pointer;border:none;margin:6px 0}.btn-ok{background:#2f7cf6}.btn-sec{background:#2a3140}.btn-warn{background:#d28a00}.btn-del{background:#b62d2d}.btn-buy{background:#c83333}.btn-sell{background:#2f7cf6}.btn-travel{background:#e0b100;color:#171b22}.btn-bank{background:#1f9d5a}.btn-debt{background:#e08400}.btn-reset{background:#c52ecf}.btn-quit{background:#10a9d6}.small{padding:6px 12px;font-size:12px}.question{background:#111821;border:1px solid #2a3140;border-radius:10px;padding:14px}.choice{display:flex;align-items:center;gap:8px;background:#161d2a;padding:10px;border-radius:8px}.resp{background:#121822;border:1px solid #2a3140;padding:10px;border-radius:8px;margin:5px 0}.bar{width:100%;height:12px;background:#1e2430;border-radius:999px;overflow:hidden;margin:8px 0}.fill{height:100%;background:#2f7cf6}.admin-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:10px}.bank-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}textarea,input,select{width:100%;padding:10px;border-radius:8px;border:1px solid #485264;background:#0d1219;color:#f4f7ff}.table{width:100%;border-collapse:collapse}th,td{padding:8px 10px;border-bottom:1px solid #2a3140;text-align:left}h1,h2,h3{margin:0 0 12px}.form{display:flex;flex-direction:column;gap:12px}input[type='radio']{width:auto}a{color:#9ac1ff}
</style>
"""


def page(title, body):
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)}</title>{BASE_STYLE}</head><body><main class='card'>"
        f"{body}</main></body></html>"
    )


# Phones joining the hotspot ask a well-known site "is there internet?". The
# hotspot's DNS sends every name to the Pi, so those checks land here: until a
# phone opens a quiz page we redirect them to the menu (the sign-in popup
# opens it), afterwards we answer "online" so the phone stays connected.
CAPTIVE_SUCCESS_REPLIES = {
    "/generate_204": (204, ""),
    "/gen_204": (204, ""),
    "/hotspot-detect.html": (200, "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"),
    "/library/test/success.html": (200, "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"),
    "/connecttest.txt": (200, "Microsoft Connect Test"),
    "/ncsi.txt": (200, "Microsoft NCSI"),
    "/success.txt": (200, "success"),
}
CAPTIVE_FREE_PATHS = {"/", "/health"}
signed_in_clients = {}


def is_quiz_host(host):
    name = (host or "").lower()
    if name.startswith("["):
        return True
    name = name.split(":")[0]
    return (
        not name
        or name in {"localhost", "raspberrypi"}
        or name.endswith(".local")
        or re.fullmatch(r"[0-9.]+", name) is not None
    )


@app.before_request
def captive_portal():
    if is_quiz_host(request.host):
        if request.path not in CAPTIVE_FREE_PATHS and not request.path.startswith("/tv"):
            signed_in_clients[request.remote_addr] = time.time()
        return None
    reply = CAPTIVE_SUCCESS_REPLIES.get(request.path)
    if reply and request.remote_addr in signed_in_clients:
        status, text = reply
        response = Response(text, status=status, mimetype="text/html" if text.startswith("<") else "text/plain")
    else:
        response = redirect(f"http://{PORTAL_HOST}/", 302)
    response.headers["Cache-Control"] = "no-cache, no-store"
    return response


def admin_required():
    return bool(session.get("is_admin"))


def require_admin():
    if not admin_required():
        return redirect(url_for("admin"))
    return None


def options_for(question):
    return [(question[f"op{i}"] or "").strip() for i in range(1, 5) if (question[f"op{i}"] or "").strip()]


def form_values(source):
    text = strip_internal_round_labels(source.get("text", "").strip())
    is_open = source.get("question_type", "open") == "open"
    options = [strip_internal_round_labels(source.get(f"op{i}", "").strip()) for i in range(1, 5)]
    return text, 1 if is_open else 0, options


def validate_question(text, is_open_text, options):
    if not text:
        return "Please enter a question."
    if not is_open_text and len([option for option in options if option]) < 2:
        return "Multiple-choice questions need at least two non-empty choices."
    return ""


def normalize_pin(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").strip().upper())[:MAX_PIN_LENGTH]


PLAYER_NAME_MAX_LENGTH = 20
PIN_HASH_METHOD = "pbkdf2:sha256:60000"
PLAYER_NAME_SQL = "COALESCE(p.name, 'Player ' || p.id)"


def normalize_player_name(value):
    return re.sub(r"\s+", " ", value or "").strip()[:PLAYER_NAME_MAX_LENGTH]


def participant_login(conn, name, pin):
    """Return (participant_id, error). Unknown names get a new profile, or claim an old PIN-only profile with that PIN."""
    key = name.casefold()
    row = conn.execute("SELECT * FROM participants WHERE name_key = ?", (key,)).fetchone()
    if row:
        if not row["pin_hash"] or not check_password_hash(row["pin_hash"], pin):
            return None, "That name is taken and the PIN doesn't match. Try the PIN again or pick another name."
        participant_id = row["id"]
    else:
        pin_hash = generate_password_hash(pin, method=PIN_HASH_METHOD)
        legacy = conn.execute("SELECT id FROM participants WHERE pin = ? AND name_key IS NULL", (pin,)).fetchone()
        if legacy:
            participant_id = legacy["id"]
        else:
            participant_id = conn.execute(
                "INSERT INTO participants (pin, created_at, last_seen_at) VALUES (?, ?, ?)", (f"name:{key}", now(), now())
            ).lastrowid
        conn.execute(
            "UPDATE participants SET name = ?, name_key = ?, pin_hash = ?, pin = ? WHERE id = ?",
            (name, key, pin_hash, f"name:{participant_id}", participant_id),
        )
    conn.execute("UPDATE participants SET last_seen_at = ?, login_count = login_count + 1 WHERE id = ?", (now(), participant_id))
    return participant_id, ""


def logged_in_participant(conn):
    participant_id = session.get("participant_id")
    if participant_id and conn.execute("SELECT 1 FROM participants WHERE id = ?", (participant_id,)).fetchone():
        return participant_id
    session.pop("participant_id", None)
    session.pop("participant_name", None)
    return None


def safe_next(value):
    value = value or "/"
    return value if value.startswith("/") and not value.startswith("//") else "/"


def login_form(next_path, error="", name=""):
    error_html = f"<div class='error'>{escape(error)}</div>" if error else ""
    return (
        "<h1>Who's playing?</h1><p class='muted'>Pick a name and a PIN (4+ letters or numbers). Use the same name and PIN next time to keep your quiz progress, drink tokens and high scores. Only your name is ever shown.</p>"
        f"{error_html}<form method='post' action='{escape(url_for('login'))}'><input type='hidden' name='next' value='{escape(next_path)}'>"
        f"<input name='name' maxlength='{PLAYER_NAME_MAX_LENGTH}' required placeholder='Your name' value='{escape(name)}'>"
        "<input name='pin' type='password' maxlength='20' minlength='4' required pattern='[A-Za-z0-9]+' placeholder='PIN'>"
        "<button class='btn btn-ok' type='submit'>Continue</button></form><a class='btn btn-sec' href='/'>Back to Menu</a>"
    )


def player_line():
    name = session.get("participant_name")
    if name:
        return f"<p>Playing as <strong>{escape(name)}</strong> · <a href='/logout'>switch player</a></p>"
    return "<p><a href='/login'>Sign in with your name and PIN</a></p>"


def next_question_number(conn):
    return (conn.execute("SELECT COALESCE(MAX(question_number), 0) FROM questions").fetchone()[0] or 0) + 1


def first_unanswered_index(questions, answered_ids):
    for index, question in enumerate(questions):
        if question["id"] not in answered_ids:
            return index
    return None


def complete_quiz_page(message):
    return page("Quiz Complete", f"<h1>Thanks!</h1><p>{escape(message)}</p><a class='btn btn-ok' href='/answers'>See Answers</a><a class='btn btn-sec' href='/'>Menu</a>")


def question_form(title, action, question=None, error=""):
    question = dict(question) if question else {}
    question_type = "open" if question.get("is_open_text", 1) else "choice"
    fields = [escape(strip_internal_round_labels(question.get(f"op{i}", "") or "")) for i in range(1, 5)]
    return page(title, f"""
        <h1>{escape(title)}</h1>{error}<form method='post' action='{escape(action)}' class='left'>
        <label>Question</label><textarea name='text' maxlength='{MAX_QUESTION_LENGTH}' required>{escape(strip_internal_round_labels(question.get('text', '') or ''))}</textarea>
        <label>Response type</label><select name='question_type'><option value='open' {'selected' if question_type == 'open' else ''}>Free-write response</option><option value='choice' {'selected' if question_type == 'choice' else ''}>Multiple choice</option></select>
        <label>Choices</label><input name='op1' maxlength='{MAX_OPTION_LENGTH}' value='{fields[0]}' placeholder='Choice 1'><input name='op2' maxlength='{MAX_OPTION_LENGTH}' value='{fields[1]}' placeholder='Choice 2'><input name='op3' maxlength='{MAX_OPTION_LENGTH}' value='{fields[2]}' placeholder='Choice 3'><input name='op4' maxlength='{MAX_OPTION_LENGTH}' value='{fields[3]}' placeholder='Choice 4'>
        <button class='btn btn-ok' type='submit'>Save</button><a class='btn btn-sec' href='/admin'>Cancel</a></form>""")


def dopewars_inventory():
    return {drug: 0 for drug in DOPEWARS_PRICE_RANGES}


def dopewars_prices(location):
    multiplier = DOPEWARS_LOCATION_MULTIPLIER.get(location, 1.0)
    prices = {}
    for drug, (low, high) in DOPEWARS_PRICE_RANGES.items():
        prices[drug] = max(1, int(random.randint(low, high) * multiplier))
    return prices


def new_dopewars_state():
    location = DOPEWARS_LOCATIONS[0]
    return {
        "day": 1,
        "cash": DOPEWARS_START_CASH,
        "debt": DOPEWARS_START_DEBT,
        "bank": 0,
        "capacity": DOPEWARS_CAPACITY,
        "location": location,
        "inventory": dopewars_inventory(),
        "prices": dopewars_prices(location),
        "message": "Welcome to NYC. Build your fortune before day 30.",
        "game_over": False,
    }


def dopewars_total_units(state):
    return sum(max(0, int(quantity)) for quantity in state["inventory"].values())


def dopewars_inventory_value(state):
    return sum(int(state["inventory"].get(drug, 0)) * int(state["prices"].get(drug, 0)) for drug in DOPEWARS_PRICE_RANGES)


def dopewars_final_score(state):
    return int(state["cash"]) + int(state["bank"]) - int(state["debt"])


def dopewars_end_summary(state, reason):
    return f"{reason} Final score: ${dopewars_final_score(state)} (cash ${state['cash']} + bank ${state['bank']} - debt ${state['debt']})."


def dopewars_save_high_score(participant_id, state):
    if not participant_id:
        return
    score = dopewars_final_score(state)
    timestamp = now()
    with closing(db_conn()) as conn:
        conn.execute(
            """
            INSERT INTO dopewars_scores (participant_id, top_score, achieved_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(participant_id) DO UPDATE SET
                top_score = excluded.top_score,
                achieved_at = excluded.achieved_at,
                updated_at = excluded.updated_at
            WHERE excluded.top_score > dopewars_scores.top_score
            """,
            (participant_id, score, timestamp, timestamp),
        )
        conn.commit()


def dopewars_finish_run(state, participant_id, reason):
    state["game_over"] = True
    state["message"] = dopewars_end_summary(state, reason)
    dopewars_save_high_score(participant_id, state)


def dopewars_leaderboard(conn, limit=10):
    return conn.execute(
        """
        SELECT ds.participant_id, COALESCE(p.name, 'Player ' || p.id) AS name, ds.top_score, ds.achieved_at
        FROM dopewars_scores ds
        JOIN participants p ON p.id = ds.participant_id
        ORDER BY ds.top_score DESC, ds.achieved_at ASC, name ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def dopewars_bankrupt(state):
    assets = int(state["cash"]) + int(state["bank"]) + dopewars_inventory_value(state)
    return assets <= int(state["debt"]) and int(state["cash"]) <= 0 and int(state["bank"]) <= 0 and dopewars_total_units(state) == 0


def parse_positive_int(value):
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, amount)


def dopewars_travel_event(state):
    roll = random.random()
    if roll < 0.12:
        held = [drug for drug, qty in state["inventory"].items() if qty > 0]
        if not held:
            return "Police searched you, but found nothing."
        drug = random.choice(held)
        seized = max(1, state["inventory"][drug] // 2)
        state["inventory"][drug] -= seized
        return f"Police stop: they seized {seized} units of {drug}."
    if roll < 0.24:
        if state["cash"] <= 0:
            return "A mugger tried, but you had no cash."
        lost = max(50, int(state["cash"] * random.uniform(0.15, 0.35)))
        lost = min(lost, state["cash"])
        state["cash"] -= lost
        return f"You were mugged and lost ${lost}."
    if roll < 0.36:
        found = random.randint(100, 900)
        state["cash"] += found
        return f"You found a hidden stash with ${found}."
    if roll < 0.48:
        drug = random.choice(list(DOPEWARS_PRICE_RANGES.keys()))
        state["prices"][drug] = max(10, state["prices"][drug] // 3)
        return f"Street deal: {drug} is insanely cheap today."
    return ""


def dopewars_render_body(state):
    summary = "<div class='notice'>" + escape(state["message"]) + "</div>" if state.get("message") else ""
    prices = "".join(f"<li>{escape(drug)}: ${state['prices'][drug]}</li>" for drug in DOPEWARS_PRICE_RANGES)
    inventory_rows = "".join(
        f"<tr><td>{escape(drug)}</td><td>{state['inventory'][drug]}</td><td>${state['prices'][drug]}</td></tr>"
        for drug in DOPEWARS_PRICE_RANGES
    )
    options = "".join(f"<option value='{escape(location)}'>{escape(location)}</option>" for location in DOPEWARS_LOCATIONS)
    actions = ""
    if not state.get("game_over"):
        actions = f"""
            <h2>Actions</h2>
            <form method='post' class='left'>
                <input type='hidden' name='action' value='buy'>
                <label>Buy</label><select name='drug'>{''.join(f"<option value='{escape(drug)}'>{escape(drug)}</option>" for drug in DOPEWARS_PRICE_RANGES)}</select>
                <input type='number' min='1' name='quantity' placeholder='Quantity'>
                <button class='btn btn-buy' type='submit'>Buy</button>
            </form>
            <form method='post' class='left'>
                <input type='hidden' name='action' value='sell'>
                <label>Sell</label><select name='drug'>{''.join(f"<option value='{escape(drug)}'>{escape(drug)}</option>" for drug in DOPEWARS_PRICE_RANGES)}</select>
                <input type='number' min='1' name='quantity' placeholder='Quantity'>
                <button class='btn btn-sell' type='submit'>Sell</button>
            </form>
            <form method='post' class='left'>
                <input type='hidden' name='action' value='travel'>
                <label>Travel</label><select name='location'>{options}</select>
                <button class='btn btn-travel' type='submit'>Travel (next day)</button>
            </form>
            <div class='question left'>
                <h3>🏦 Bank</h3>
                <div class='bank-grid'>
                    <form method='post' class='left'>
                        <input type='hidden' name='action' value='deposit'>
                        <label>Deposit</label><input type='number' min='1' name='amount' placeholder='Amount'>
                        <button class='btn btn-bank' type='submit'>Deposit</button>
                    </form>
                    <form method='post' class='left'>
                        <input type='hidden' name='action' value='withdraw'>
                        <label>Withdraw</label><input type='number' min='1' name='amount' placeholder='Amount'>
                        <button class='btn btn-bank' type='submit'>Withdraw</button>
                    </form>
                </div>
            </div>
            <form method='post' class='left'>
                <input type='hidden' name='action' value='pay_debt'>
                <label>Pay loan shark</label><input type='number' min='1' name='amount' placeholder='Amount'>
                <button class='btn btn-debt' type='submit'>Pay Loan Shark</button>
            </form>
            <form method='post' class='left'>
                <input type='hidden' name='action' value='quit'>
                <button class='btn btn-quit' type='submit'>Quit Game</button>
            </form>
        """
    return f"""
        <h1>🕹 Dopewars</h1>
        <p class='muted'>Day {state['day']} of {DOPEWARS_GAME_DAYS} · Location: {escape(state['location'])}</p>
        <p>Cash: <strong>${state['cash']}</strong> · Bank: <strong>${state['bank']}</strong> · Debt: <strong>${state['debt']}</strong> · Space: <strong>{dopewars_total_units(state)}/{state['capacity']}</strong></p>
        {summary}
        <div class='question left'>
            <h2>Market Prices</h2>
            <ul>{prices}</ul>
        </div>
        <div class='question left'>
            <h2>Inventory</h2>
            <table class='table'><tr><th>Drug</th><th>Units</th><th>Price</th></tr>{inventory_rows}</table>
        </div>
        {actions}
        <form method='post' action='/games/dopewars/reset'><button class='btn btn-reset' type='submit'>Reset Game</button></form>
        <a class='btn btn-sec' href='/'>Back to Menu</a>
    """


@app.route("/health")
def health():
    return {"ok": True, "service": "CottonFlatBarQuiz"}, 200


@app.route("/login", methods=["GET", "POST"])
def login():
    next_path = safe_next(request.values.get("next"))
    if request.method == "GET":
        return page("Who's playing?", login_form(next_path))
    name = normalize_player_name(request.form.get("name"))
    pin = normalize_pin(request.form.get("pin"))
    if not name:
        return page("Who's playing?", login_form(next_path, "Please enter a name."))
    if len(pin) < MIN_PIN_LENGTH:
        return page("Who's playing?", login_form(next_path, "Use at least 4 letters or numbers for the PIN.", name))
    with closing(db_conn()) as conn:
        participant_id, error = participant_login(conn, name, pin)
        if error:
            return page("Who's playing?", login_form(next_path, error, name))
        display_name = conn.execute("SELECT name FROM participants WHERE id = ?", (participant_id,)).fetchone()["name"]
        conn.commit()
    session.pop("dopewars_state", None)
    session["participant_id"] = participant_id
    session["participant_name"] = display_name
    return redirect(next_path)


@app.route("/logout")
def player_logout():
    for key in ("participant_id", "participant_name", "participant_pin", "dopewars_state"):
        session.pop(key, None)
    return redirect(url_for("menu"))


@app.route("/")
def menu():
    with closing(db_conn()) as conn:
        dopewars_scores = dopewars_leaderboard(conn)
    body = [
        "<h1>🍺 Cotton Flat Bar Quiz</h1>",
        "<p class='muted'>Funny sociology, questionable opinions, and community data.</p>",
        player_line(),
        "<a class='btn btn-ok' href='/quiz'>▶ Take Quiz</a>",
        "<a class='btn btn-sec' href='/submit-question'>✍ Submit Question</a>",
        "<a class='btn btn-sec' href='/answers'>📊 Community Answers</a>",
        "<a class='btn btn-sec' href='/gold-users'>🥇 Gold Users</a>",
        "<a class='btn btn-sec' href='/games/dopewars'>🕹 Games</a>",
        "<a class='btn btn-sec' href='/games/drawing'>🎨 Drawing with Friends</a>",
        "<a class='btn btn-sec' href='/admin'>🛠 Admin</a>",
        "<div class='question left'><h2>🕹 Dopewars</h2><p>Classic text-based street trading across NYC.</p><a class='btn btn-ok' href='/games/dopewars'>Play Dopewars</a><h3>High Scores</h3>",
    ]
    if dopewars_scores:
        body.append("<table class='table'><tr><th>#</th><th>Player</th><th>Top Score</th><th>Date</th></tr>")
        for index, row in enumerate(dopewars_scores, 1):
            body.append(
                f"<tr><td>{index}</td><td>{escape(row['name'])}</td><td>${row['top_score']}</td><td>{escape((row['achieved_at'] or '').replace('T', ' '))}</td></tr>"
            )
        body.append("</table>")
    else:
        body.append("<p class='muted'>No Dopewars scores yet. Be the first to set one.</p>")
    body.append("</div>")
    return page("Cotton Flat Bar Quiz", "".join(body))


TV_PAGE = """<!doctype html><html><head><meta charset='utf-8'><title>Cotton Flat Bar Quiz TV</title>
<style>
html,body{margin:0;height:100%;background:#0f1115;color:#f4f7ff;font-family:Arial,sans-serif;cursor:none;overflow:hidden}
#app{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:3vh 4vw;box-sizing:border-box;text-align:center}
h1{font-size:6vh;margin:0 0 3vh}h2{font-size:4.5vh;margin:0 0 2vh}.muted{color:#a7b0c0;font-size:3vh}
table{border-collapse:collapse;font-size:4vh;min-width:60vw}td,th{padding:1.2vh 2vw;border-bottom:1px solid #2a3140;text-align:left}
th{color:#a7b0c0;font-size:2.8vh}td.score{color:#80efad;font-weight:bold;text-align:right}tr.first td{color:#ffd54a}
.timer{font-size:22vh;font-weight:bold;color:#ffd54a;line-height:1}.art{max-height:62vh;max-width:90vw;border-radius:12px;background:#fff;margin:1vh 0}
.chips{display:flex;flex-wrap:wrap;gap:1.5vh;justify-content:center;margin:3vh 0}.chip{background:#6a3fb5;padding:1.2vh 2.5vw;border-radius:999px;font-size:3.5vh}
.grid{display:flex;flex-wrap:wrap;gap:3vh;justify-content:center;margin:2vh 0}.cell{position:relative}.cell img{height:30vh;max-width:28vw;background:#fff;border-radius:10px}.cell img.win{height:55vh;max-width:80vw}.num{position:absolute;top:-1.5vh;left:-1.5vh;background:#ffd54a;color:#111;font-weight:bold;font-size:5vh;border-radius:999px;padding:0 2vh}
</style></head><body><div id='app'><h1>🍺 Cotton Flat Bar Quiz</h1></div>
<script>
const app = document.getElementById('app');
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
const BOARD_MS = 12000;
function fmtScore(b, v){ return (b.unit=='$' ? '$' : '') + Number(v).toLocaleString(); }
function renderScores(st){
  const boards = st.boards.filter(b=>b.rows.length || b.message);
  if(!boards.length) return "<h1>Cotton Flat Bar Quiz</h1><p class='muted'>No scores yet. Join the Wi-Fi <b>Cotton Flat Bar Quiz</b> and play!</p>";
  const pick = Math.floor(Date.now()/BOARD_MS) % boards.length;
  const b = boards[pick];
  if(b.message) return `<h1>${esc(b.title)}</h1><p style='font-size:5vh;white-space:pre-wrap'>${esc(b.message)}</p><p class='muted'>${pick+1}/${boards.length}</p>`;
  let h = `<h1>${esc(b.title)}</h1><table><tr><th>#</th><th>Player</th><th style='text-align:right'>${esc(b.label)}</th></tr>`;
  b.rows.forEach((r,i)=>{h += `<tr class='${i==0?"first":""}'><td>${i+1}</td><td>${esc(r.name)}</td><td class='score'>${fmtScore(b, r.score)}</td></tr>`;});
  h += "</table>";
  if(b.note) h += `<p class='muted'>${esc(b.note)}</p>`;
  h += `<p class='muted'>Join the Wi-Fi Cotton Flat Bar Quiz to play · ${pick+1}/${boards.length}</p>`;
  return h;
}
let deadline = 0, lastHtml = '';
function fmt(sec){sec=Math.max(0,Math.ceil(sec));return Math.floor(sec/60)+':'+String(sec%60).padStart(2,'0');}
function renderDrawing(st){
  let h = "<h2>Drawing with Friends</h2>";
  if(st.phase=='prep'){
    h += `<h1>Get ready to draw: &ldquo;${esc(st.prompt)}&rdquo;</h1><div id='timer' class='timer'></div><p class='muted'>${st.players.map(esc).join(' &middot; ')}</p>`;
  }else if(st.phase=='drawing'){
    h += `<h1>Draw: &ldquo;${esc(st.prompt)}&rdquo;</h1><div id='timer' class='timer'></div><p class='muted'>${st.submitted} of ${st.players.length} drawings in</p>`;
  }else if(st.phase=='voting'){
    h += `<h1>Vote on your phone! &ldquo;${esc(st.prompt)}&rdquo;</h1><div class='grid'>`;
    h += st.drawings.map(d=>`<div class='cell'><img src='/games/drawing/image/${d.entry_id}'><span class='num'>${d.number}</span></div>`).join('');
    h += `</div><p class='muted'>${st.votes_in} of ${st.voters} votes in &middot; <span id='timer'></span></p>`;
  }else if(st.phase=='results'){
    if(st.winners.length){ h += "<div class='grid'>" + st.winners.map(w=>`<div class='cell'><img class='win' src='/games/drawing/image/${w.entry_id}'><span class='num'>${w.number}</span><h1>${esc(w.name)} wins! +1 point</h1></div>`).join('') + "</div>"; }
    else { h += "<h1>No votes this round</h1>"; }
    h += "<p class='muted'>" + st.standings.map(s=>`${esc(s.name)}: ${s.points}`).join(' &middot; ') + "</p>";
  }
  return h;
}
function render(st){
  const html = st.mode=='drawing' ? renderDrawing(st) : renderScores(st);
  if(st.mode=='drawing') deadline = Date.now() + st.seconds_left*1000;
  if(html !== lastHtml){ app.innerHTML = html; lastHtml = html; }
  tick();
}
function tick(){ const t = document.getElementById('timer'); if(t) t.textContent = fmt((deadline-Date.now())/1000); }
setInterval(tick, 250);
async function poll(){
  let wait = 3000;
  try{ const r = await fetch('/tv/state',{cache:'no-store'}); const st = await r.json(); render(st); if(st.mode=='drawing') wait = 1500; }catch(e){}
  setTimeout(poll, wait);
}
poll();
</script></body></html>"""


def mvp_leaderboard(conn, limit=10):
    return conn.execute(
        "SELECT COALESCE(name, 'Player ' || id) AS name, login_count FROM participants WHERE login_count > 0 ORDER BY login_count DESC, last_seen_at DESC LIMIT ?",
        (limit,),
    ).fetchall()


def tv_builtin_boards(conn):
    return [
        {"title": "Dopewars High Scores", "label": "Top Score", "unit": "$", "rows": [{"name": row["name"], "score": row["top_score"]} for row in dopewars_leaderboard(conn)]},
        {"title": "MVPs: Most Visits", "label": "Visits", "unit": "", "rows": [{"name": row["name"], "score": row["login_count"]} for row in mvp_leaderboard(conn)]},
        {"title": "Drawing with Friends Scores", "label": "Points", "unit": "", "rows": [{"name": row["name"], "score": row["points"]} for row in drawing_standings(conn)]},
    ]


TV_BOARD_KEYS = ("dopewars", "mvp", "drawing")


def tv_boards(conn, include_hidden=False):
    settings = {row["key"]: row for row in conn.execute("SELECT * FROM tv_screens")}
    boards = []
    for key, board in zip(TV_BOARD_KEYS, tv_builtin_boards(conn)):
        saved = settings.get(key)
        board.update({"key": key, "enabled": bool(saved["enabled"]) if saved else True})
        if saved and saved["title"]:
            board["title"] = saved["title"]
        if board["enabled"] or include_hidden:
            boards.append(board)
    for message in conn.execute("SELECT * FROM tv_messages ORDER BY id"):
        boards.append({"key": f"message{message['id']}", "id": message["id"], "title": message["title"], "message": message["body"], "rows": [], "enabled": True})
    return boards


@app.route("/tv")
def tv():
    return TV_PAGE


@app.route("/tv/state")
def tv_state():
    with closing(db_conn()) as conn:
        state = drawing_state(conn)
        if state["phase"] != "none":
            return {"mode": "drawing", **state}
        return {"mode": "scores", "boards": tv_boards(conn)}


def clock():
    return time.time()


def drawing_entries(conn, round_id):
    return conn.execute(
        "SELECT id, player_token, nickname, joined_at, submitted_at FROM drawing_entries WHERE round_id = ? ORDER BY joined_at ASC, id ASC",
        (round_id,),
    ).fetchall()


def drawing_end_round(conn, round_id, status):
    conn.execute("UPDATE drawing_rounds SET status = ?, ended_at = ? WHERE id = ?", (status, clock(), round_id))
    conn.commit()


def drawing_reload(conn, round_id):
    return conn.execute("SELECT * FROM drawing_rounds WHERE id = ?", (round_id,)).fetchone()


def drawing_award(conn, rnd, current):
    claimed = conn.execute(
        "UPDATE drawing_rounds SET results_started_at = ? WHERE id = ? AND results_started_at IS NULL", (current, rnd["id"])
    ).rowcount
    if claimed:
        tally = conn.execute("SELECT entry_id, COUNT(*) AS votes FROM drawing_votes WHERE round_id = ? GROUP BY entry_id", (rnd["id"],)).fetchall()
        top = max((row["votes"] for row in tally), default=0)
        winners = [row["entry_id"] for row in tally if top and row["votes"] == top]
        for entry_id in winners:
            conn.execute(
                "UPDATE drawing_players SET points = points + 1 WHERE player_token = (SELECT player_token FROM drawing_entries WHERE id = ?)",
                (entry_id,),
            )
        conn.execute("UPDATE drawing_rounds SET winners = ? WHERE id = ?", (json.dumps(winners), rnd["id"]))
    conn.commit()
    return drawing_reload(conn, rnd["id"])


def drawing_current_round(conn):
    """Return (round, entries, phase) for the running round, advancing it by the clock; None when idle."""
    rnd = conn.execute("SELECT * FROM drawing_rounds WHERE status IN ('lobby', 'drawing') ORDER BY id DESC LIMIT 1").fetchone()
    if not rnd:
        return None
    if rnd["status"] == "lobby" or rnd["prep_ends_at"] is None:
        drawing_end_round(conn, rnd["id"], "expired")
        return None
    current = clock()
    entries = drawing_entries(conn, rnd["id"])
    if current < rnd["prep_ends_at"]:
        return rnd, entries, "prep"
    submitted = [entry for entry in entries if entry["submitted_at"] is not None]
    if rnd["vote_started_at"] is None:
        everyone_done = bool(entries) and len(submitted) == len(entries)
        if not everyone_done and current < rnd["draw_ends_at"] + DRAWING_SUBMIT_GRACE_SECONDS:
            return rnd, entries, "drawing"
        if not submitted:
            drawing_end_round(conn, rnd["id"], "done")
            return None
        conn.execute("UPDATE drawing_rounds SET vote_started_at = ? WHERE id = ? AND vote_started_at IS NULL", (current, rnd["id"]))
        conn.commit()
        rnd = drawing_reload(conn, rnd["id"])
    if rnd["results_started_at"] is None:
        votes = conn.execute("SELECT COUNT(*) FROM drawing_votes WHERE round_id = ?", (rnd["id"],)).fetchone()[0]
        voters = conn.execute("SELECT COUNT(*) FROM drawing_players").fetchone()[0]
        if votes < voters and current < rnd["vote_started_at"] + DRAWING_VOTE_SECONDS:
            return rnd, entries, "voting"
        rnd = drawing_award(conn, rnd, current)
    if current >= rnd["results_started_at"] + DRAWING_RESULTS_SECONDS:
        drawing_end_round(conn, rnd["id"], "done")
        return None
    return rnd, entries, "results"


def drawing_standings(conn):
    rows = conn.execute("SELECT nickname, points FROM drawing_players ORDER BY points DESC, joined_at ASC")
    return [{"name": row["nickname"], "points": row["points"]} for row in rows]


def drawing_expire_table(conn):
    last = conn.execute(
        "SELECT MAX(t) FROM (SELECT MAX(joined_at) AS t FROM drawing_players UNION ALL SELECT MAX(COALESCE(ended_at, created_at)) FROM drawing_rounds)"
    ).fetchone()[0]
    if last is not None and clock() - last > DRAWING_LOBBY_TIMEOUT_SECONDS:
        conn.execute("DELETE FROM drawing_players")
        conn.commit()


def drawing_state(conn, player_token=""):
    current_round = drawing_current_round(conn)
    if not current_round:
        drawing_expire_table(conn)
    standings = drawing_standings(conn)
    joined = bool(player_token) and conn.execute("SELECT 1 FROM drawing_players WHERE player_token = ?", (player_token,)).fetchone() is not None
    state = {"phase": "none", "standings": standings, "joined": joined, "signed_in": bool(player_token), "in_round": False}
    if not current_round:
        return state
    rnd, entries, phase = current_round
    me = next((entry for entry in entries if player_token and entry["player_token"] == player_token), None)
    submitted = [entry for entry in entries if entry["submitted_at"] is not None]
    ends_at = {
        "prep": rnd["prep_ends_at"],
        "drawing": rnd["draw_ends_at"],
        "voting": (rnd["vote_started_at"] or 0) + DRAWING_VOTE_SECONDS,
        "results": (rnd["results_started_at"] or 0) + DRAWING_RESULTS_SECONDS,
    }[phase]
    state.update({
        "phase": phase,
        "round_id": rnd["id"],
        "prompt": rnd["prompt"],
        "players": [entry["nickname"] for entry in entries],
        "submitted": len(submitted),
        "in_round": me is not None,
        "my_submitted": bool(me and me["submitted_at"] is not None),
        "seconds_left": max(0, int(math.ceil(ends_at - clock()))),
    })
    if phase in ("voting", "results"):
        votes = {row["voter_token"]: row["entry_id"] for row in conn.execute("SELECT voter_token, entry_id FROM drawing_votes WHERE round_id = ?", (rnd["id"],))}
        tally = Counter(votes.values())
        numbers = {entry["id"]: number for number, entry in enumerate(submitted, 1)}
        winners = set(json.loads(rnd["winners"] or "[]"))
        state["drawings"] = [{"number": numbers[e["id"]], "entry_id": e["id"], "mine": bool(player_token) and e["player_token"] == player_token} for e in submitted]
        state["votes_in"] = len(votes)
        state["voters"] = len(standings)
        state["my_vote"] = numbers.get(votes.get(player_token))
        state["winners"] = [{"number": numbers[e["id"]], "entry_id": e["id"], "name": e["nickname"], "votes": tally[e["id"]]} for e in submitted if e["id"] in winners]
    return state


def drawing_token():
    participant_id = session.get("participant_id")
    return f"p{participant_id}" if participant_id else ""


def drawing_new_prompt(conn):
    recent = {row["prompt"] for row in conn.execute("SELECT prompt FROM drawing_rounds ORDER BY id DESC LIMIT 15")}
    choices = [prompt for prompt in DRAWING_PROMPTS if prompt not in recent] or DRAWING_PROMPTS
    return random.choice(choices)


def drawing_prune(conn):
    old_ids = [row["id"] for row in conn.execute("SELECT id FROM drawing_rounds ORDER BY id DESC LIMIT -1 OFFSET ?", (DRAWING_KEEP_ROUNDS,))]
    for round_id in old_ids:
        conn.execute("DELETE FROM drawing_votes WHERE round_id = ?", (round_id,))
        conn.execute("DELETE FROM drawing_entries WHERE round_id = ?", (round_id,))
        conn.execute("DELETE FROM drawing_rounds WHERE id = ?", (round_id,))


def drawing_standings_html(state):
    rows = state.get("standings") or []
    if not rows:
        return ""
    cells = "".join(f"<tr><td>{escape(row['name'])}</td><td>{row['points']}</td></tr>" for row in rows)
    return f"<h3>Scores</h3><table class='table'><tr><th>Player</th><th>Points</th></tr>{cells}</table>"


def drawing_button(action, label, style="btn-ok", fields=""):
    return f"<form method='post' action='{action}'>{fields}<button class='btn {style}' type='submit'>{escape(label)}</button></form>"


DRAWING_PAD = """
<p class='muted'>Time left: <strong id='timer' style='font-size:1.4em;color:#ffd54a'></strong></p>
<canvas id='pad' width='480' height='360' style='width:100%;touch-action:none;background:#fff;border-radius:8px'></canvas>
<div class='admin-row' id='colors'></div>
<div class='admin-row'><button class='btn btn-sec small' data-size='4'>Thin</button><button class='btn btn-sec small' data-size='10'>Medium</button><button class='btn btn-sec small' data-size='22'>Thick</button><button class='btn btn-sec small' id='eraser'>Eraser</button><button class='btn btn-del small' id='clear'>Clear</button></div>
<button class='btn btn-ok' id='send'>Submit Drawing</button>
<script>
const c = document.getElementById('pad'), ctx = c.getContext('2d');
ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height);
let color = '#111111', size = 10, down = false, last = null, sent = false;
['#111111','#e53935','#fb8c00','#fdd835','#43a047','#1e88e5','#8e24aa','#6d4c41','#f48fb1'].forEach(col => {
  const b = document.createElement('button'); b.className = 'btn small'; b.style.background = col; b.style.width = '38px'; b.innerHTML = '&nbsp;';
  b.onclick = () => { color = col; }; document.getElementById('colors').appendChild(b);
});
document.querySelectorAll('[data-size]').forEach(b => b.onclick = () => { size = Number(b.dataset.size); });
document.getElementById('eraser').onclick = () => { color = '#ffffff'; size = 22; };
document.getElementById('clear').onclick = () => { if (confirm('Clear your drawing?')) { ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height); } };
function pos(e) { const r = c.getBoundingClientRect(); return { x: (e.clientX - r.left) * c.width / r.width, y: (e.clientY - r.top) * c.height / r.height }; }
function dot(p) { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(p.x, p.y, size / 2, 0, Math.PI * 2); ctx.fill(); }
function line(a, b) { ctx.strokeStyle = color; ctx.lineWidth = size; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
c.addEventListener('pointerdown', e => { e.preventDefault(); down = true; last = pos(e); c.setPointerCapture(e.pointerId); dot(last); });
c.addEventListener('pointermove', e => { if (!down) return; const p = pos(e); line(last, p); last = p; });
['pointerup', 'pointercancel'].forEach(n => c.addEventListener(n, () => { down = false; }));
async function submitDrawing() {
  if (sent) return; sent = true; document.getElementById('send').disabled = true;
  try { await fetch('/games/drawing/submit', { method: 'POST', body: new URLSearchParams({ image: c.toDataURL('image/jpeg', 0.8) }) }); } catch (e) {}
  location.reload();
}
document.getElementById('send').onclick = submitDrawing;
const deadline = Date.now() + SECONDS_LEFT * 1000;
function tick() { const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000)); document.getElementById('timer').textContent = Math.floor(left / 60) + ':' + String(left % 60).padStart(2, '0'); if (left <= 0) submitDrawing(); }
tick(); setInterval(tick, 500);
</script>"""


def drawing_page_key(state):
    return f"{state['phase']}|{state.get('round_id', '')}|{state['joined']}|{state['in_round']}|{state.get('my_submitted', '')}|{state.get('my_vote', '')}|{len(state['standings'])}"


def drawing_render_body(state, error=""):
    phase = state["phase"]
    prompt = escape(state.get("prompt", ""))
    body = ["<h1>&#127912; Drawing with Friends</h1>", error]
    rules = (
        f"<p class='muted'>Everyone gets the same prompt: {DRAWING_PREP_SECONDS} seconds to get ready, {DRAWING_SECONDS} seconds to draw, "
        "then everyone votes for their favourite numbered drawing. The winner gets 1 point. Scores reset when a new player joins.</p>"
    )
    if not state["signed_in"]:
        body.append(rules + "<a class='btn btn-ok' href='/login?next=/games/drawing'>Sign in to play</a>")
    elif not state["joined"]:
        body.append(rules + drawing_button("/games/drawing/join", "Join the Game" if phase == "none" else "Join - you'll play next round"))
    if phase == "none" and state["joined"]:
        body.append(f"<p>At the table: {', '.join(escape(row['name']) for row in state['standings'])}</p>")
        body.append(drawing_button("/games/drawing/start", "Everyone's In - Start Round!"))
    elif phase == "prep":
        if state["in_round"]:
            body.append(f"<h2>Get ready to draw: &ldquo;{prompt}&rdquo;</h2><p class='muted'>Drawing starts in {state['seconds_left']} seconds...</p>")
        else:
            body.append("<p>A round is starting. Watch the TV!</p>")
    elif phase == "drawing":
        if state["in_round"] and not state["my_submitted"]:
            body.append(f"<h2>Draw: &ldquo;{prompt}&rdquo;</h2>")
            body.append(DRAWING_PAD.replace("SECONDS_LEFT", str(state["seconds_left"])))
        elif state["in_round"]:
            body.append(f"<div class='notice'>Drawing sent! Waiting for the others ({state['submitted']} of {len(state['players'])} in).</div>")
        else:
            body.append(f"<p>A round is underway: &ldquo;{prompt}&rdquo;. Watch the TV!</p>")
    elif phase == "voting":
        body.append(f"<h2>Vote for your favourite: &ldquo;{prompt}&rdquo;</h2>")
        if state["my_vote"]:
            body.append(f"<div class='notice'>You voted for #{state['my_vote']}. Tap another number to change it.</div>")
        body.append(f"<p class='muted'>{state['votes_in']} of {state['voters']} votes in &middot; about {state['seconds_left']} seconds left</p>")
        only_one = len(state["drawings"]) == 1
        for drawing in state["drawings"]:
            body.append(f"<div class='question left'><img src='/games/drawing/image/{drawing['entry_id']}' style='width:100%;border-radius:8px;background:#fff'>")
            if state["joined"] and (only_one or not drawing["mine"]):
                field = f"<input type='hidden' name='number' value='{drawing['number']}'>"
                body.append(drawing_button("/games/drawing/vote", f"Vote #{drawing['number']}", fields=field))
            else:
                body.append(f"<strong>#{drawing['number']}{' (yours)' if drawing['mine'] else ''}</strong>")
            body.append("</div>")
    elif phase == "results":
        for winner in state["winners"]:
            body.append(f"<h2>#{winner['number']} by {escape(winner['name'])} wins! +1 point</h2>")
            body.append(f"<img src='/games/drawing/image/{winner['entry_id']}' style='width:100%;border-radius:8px;background:#fff'>")
        if not state["winners"]:
            body.append("<h2>No votes this round, so no points.</h2>")
    if state["joined"] and not state["in_round"] and phase != "none":
        body.append("<div class='notice'>You're in for the next round.</div>")
    body.append(drawing_standings_html(state))
    drawing_now = phase == "drawing" and state["in_round"] and not state.get("my_submitted")
    if state["joined"] and not drawing_now:
        body.append(drawing_button("/games/drawing/leave", "Leave the Game", "btn-sec small"))
    body.append("<a class='btn btn-sec' href='/'>Back to Menu</a>")
    if not drawing_now:
        body.append(
            "<script>const KEY = " + json.dumps(drawing_page_key(state)) + ";"
            "setInterval(async () => { try { const r = await fetch('/games/drawing/state', {cache: 'no-store'}); const s = await r.json();"
            " if (s.key !== KEY) location.reload(); } catch (e) {} }, 2000);</script>"
        )
    return "".join(body)


@app.route("/games/drawing")
def drawing_game():
    with closing(db_conn()) as conn:
        state = drawing_state(conn, drawing_token())
    return page("Drawing with Friends", drawing_render_body(state))


@app.route("/games/drawing/state")
def drawing_game_state():
    with closing(db_conn()) as conn:
        state = drawing_state(conn, drawing_token())
    state["key"] = drawing_page_key(state)
    return state


@app.route("/games/drawing/join", methods=["POST"])
def drawing_join():
    with closing(db_conn()) as conn:
        participant_id = logged_in_participant(conn)
        if not participant_id:
            return redirect(url_for("login", next=url_for("drawing_game")))
        name = conn.execute("SELECT COALESCE(name, 'Player ' || id) FROM participants WHERE id = ?", (participant_id,)).fetchone()[0]
        added = conn.execute(
            "INSERT OR IGNORE INTO drawing_players (player_token, participant_id, nickname, joined_at) VALUES (?, ?, ?, ?)",
            (drawing_token(), participant_id, name, clock()),
        ).rowcount
        if added:
            conn.execute("UPDATE drawing_players SET points = 0")
        conn.commit()
    return redirect(url_for("drawing_game"))


@app.route("/games/drawing/leave", methods=["POST"])
def drawing_leave():
    with closing(db_conn()) as conn:
        conn.execute("DELETE FROM drawing_players WHERE player_token = ?", (drawing_token(),))
        conn.commit()
    return redirect(url_for("drawing_game"))


@app.route("/games/drawing/start", methods=["POST"])
def drawing_start():
    token = drawing_token()
    with closing(db_conn()) as conn:
        seated = token and conn.execute("SELECT 1 FROM drawing_players WHERE player_token = ?", (token,)).fetchone()
        if seated and not drawing_current_round(conn):
            drawing_prune(conn)
            start = clock()
            round_id = conn.execute(
                "INSERT INTO drawing_rounds (prompt, status, created_at, prep_ends_at, draw_ends_at) VALUES (?, 'drawing', ?, ?, ?)",
                (drawing_new_prompt(conn), start, start + DRAWING_PREP_SECONDS, start + DRAWING_PREP_SECONDS + DRAWING_SECONDS),
            ).lastrowid
            conn.execute(
                "INSERT INTO drawing_entries (round_id, player_token, nickname, joined_at) SELECT ?, player_token, nickname, joined_at FROM drawing_players",
                (round_id,),
            )
            conn.commit()
    return redirect(url_for("drawing_game"))


@app.route("/games/drawing/submit", methods=["POST"])
def drawing_submit():
    image = request.form.get("image", "")
    match = DRAWING_IMAGE_RE.fullmatch(image) if len(image) <= DRAWING_MAX_IMAGE_CHARS else None
    if not match:
        return {"ok": False, "error": "Invalid drawing."}, 400
    try:
        base64.b64decode(match.group(2), validate=True)
    except ValueError:
        return {"ok": False, "error": "Invalid drawing."}, 400
    with closing(db_conn()) as conn:
        current_round = drawing_current_round(conn)
        if not current_round or current_round[2] != "drawing":
            return {"ok": False, "error": "Drawing time is over."}, 409
        cur = conn.execute(
            "UPDATE drawing_entries SET image = ?, submitted_at = ? WHERE round_id = ? AND player_token = ? AND submitted_at IS NULL",
            (image, clock(), current_round[0]["id"], drawing_token()),
        )
        conn.commit()
        if cur.rowcount == 0:
            return {"ok": False, "error": "You are not in this round or already submitted."}, 409
    return {"ok": True}


@app.route("/games/drawing/vote", methods=["POST"])
def drawing_vote():
    token = drawing_token()
    number = parse_positive_int(request.form.get("number"))
    with closing(db_conn()) as conn:
        state = drawing_state(conn, token)
        drawing = next((d for d in state.get("drawings", []) if d["number"] == number), None)
        if state["phase"] == "voting" and state["joined"] and drawing and (not drawing["mine"] or len(state["drawings"]) == 1):
            conn.execute(
                "INSERT OR REPLACE INTO drawing_votes (round_id, voter_token, entry_id, voted_at) VALUES (?, ?, ?, ?)",
                (state["round_id"], token, drawing["entry_id"], clock()),
            )
            conn.commit()
    return redirect(url_for("drawing_game"))


@app.route("/games/drawing/image/<int:entry_id>")
def drawing_image(entry_id):
    with closing(db_conn()) as conn:
        row = conn.execute("SELECT image FROM drawing_entries WHERE id = ? AND image IS NOT NULL", (entry_id,)).fetchone()
    match = DRAWING_IMAGE_RE.fullmatch(row["image"]) if row else None
    if not match:
        return Response("Not found", status=404, mimetype="text/plain")
    response = Response(base64.b64decode(match.group(2)), mimetype=f"image/{match.group(1)}")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/admin/drawing/end", methods=["POST"])
def drawing_admin_end():
    denied = require_admin()
    if denied:
        return denied
    with closing(db_conn()) as conn:
        current_round = drawing_current_round(conn)
        if current_round:
            drawing_end_round(conn, current_round[0]["id"], "cancelled")
    return redirect(url_for("admin"))


@app.route("/games")
def games():
    return redirect(url_for("menu"))


@app.route("/gold-users")
def gold_users():
    with closing(db_conn()) as conn:
        participants = participant_stats(conn, sort_mode="leaderboard")

    body = [
        "<h1>🥇 Gold Users</h1>",
        "<p class='muted'>Leaderboard for players earning the most drink tokens and answering the most questions.</p>",
    ]
    if participants:
        body.append("<table class='table'><tr><th>#</th><th>Player</th><th>Answered</th><th>Tokens ready</th><th>Tokens redeemed</th><th>Total tokens</th><th>Progress</th></tr>")
        for index, participant in enumerate(participants, 1):
            progress = participant["answered"] % TOKEN_MILESTONE
            body.append(
                f"<tr><td>{index}</td><td>{escape(participant['name'])}</td><td>{participant['answered']}</td>"
                f"<td>{participant['unredeemed']}</td><td>{participant['redeemed']}</td>"
                f"<td>{participant['total_tokens']}</td><td>{progress}/{TOKEN_MILESTONE}</td></tr>"
            )
        body.append("</table>")
    else:
        body.append("<p class='muted'>No participants yet.</p>")
    body.append("<a class='btn btn-sec' href='/'>Back to Menu</a>")
    return page("Gold Users", "".join(body))


@app.route("/games/dopewars", methods=["GET", "POST"])
def dopewars():
    with closing(db_conn()) as conn:
        participant_id = logged_in_participant(conn)
    if not participant_id:
        return redirect(url_for("login", next=url_for("dopewars")))

    state = session.get("dopewars_state")
    if not isinstance(state, dict) or "cash" not in state:
        state = new_dopewars_state()

    if request.method == "POST" and not state.get("game_over"):
        action = request.form.get("action", "")
        state["message"] = ""
        if action in {"buy", "sell"}:
            drug = request.form.get("drug", "")
            quantity = parse_positive_int(request.form.get("quantity"))
            if drug not in DOPEWARS_PRICE_RANGES or quantity <= 0:
                state["message"] = "Choose a drug and quantity first."
            elif action == "buy":
                price = state["prices"][drug]
                available_space = max(0, state["capacity"] - dopewars_total_units(state))
                affordable = state["cash"] // price if price > 0 else 0
                purchased = min(quantity, available_space, affordable)
                if purchased <= 0:
                    state["message"] = "Not enough cash or coat space."
                else:
                    state["inventory"][drug] += purchased
                    spent = purchased * price
                    state["cash"] -= spent
                    state["message"] = f"Bought {purchased} units of {drug} for ${spent}."
            else:
                held = state["inventory"].get(drug, 0)
                sold = min(quantity, held)
                if sold <= 0:
                    state["message"] = f"You do not have any {drug} to sell."
                else:
                    earned = sold * state["prices"][drug]
                    state["inventory"][drug] -= sold
                    state["cash"] += earned
                    state["message"] = f"Sold {sold} units of {drug} for ${earned}."
        elif action == "travel":
            destination = request.form.get("location", "")
            if destination not in DOPEWARS_LOCATIONS:
                state["message"] = "Pick a destination."
            else:
                state["location"] = destination
                state["day"] += 1
                state["debt"] = int(state["debt"] * (1 + DOPEWARS_INTEREST_RATE))
                state["prices"] = dopewars_prices(destination)
                event = dopewars_travel_event(state)
                state["message"] = f"Traveled to {destination}. Loan shark interest increased your debt."
                if event:
                    state["message"] += " " + event
        elif action in {"deposit", "withdraw", "pay_debt"}:
            amount = parse_positive_int(request.form.get("amount"))
            if amount <= 0:
                state["message"] = "Enter an amount greater than zero."
            elif action == "deposit":
                moved = min(amount, state["cash"])
                state["cash"] -= moved
                state["bank"] += moved
                state["message"] = f"Deposited ${moved} in the bank."
            elif action == "withdraw":
                moved = min(amount, state["bank"])
                state["bank"] -= moved
                state["cash"] += moved
                state["message"] = f"Withdrew ${moved} from the bank."
            else:
                paid = min(amount, state["cash"], state["debt"])
                state["cash"] -= paid
                state["debt"] -= paid
                state["message"] = f"Paid ${paid} to the loan shark."
        elif action == "quit":
            dopewars_finish_run(state, participant_id, "You quit the run.")
        else:
            state["message"] = "Unknown action."

        if state["day"] >= DOPEWARS_GAME_DAYS and not state.get("game_over"):
            dopewars_finish_run(state, participant_id, "Day 30 reached.")
        elif dopewars_bankrupt(state) and not state.get("game_over"):
            dopewars_finish_run(state, participant_id, "You went bankrupt.")

    session["dopewars_state"] = state
    return page("Dopewars", dopewars_render_body(state))


@app.route("/games/dopewars/reset", methods=["POST"])
def dopewars_reset():
    session["dopewars_state"] = new_dopewars_state()
    return redirect(url_for("dopewars"))


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    conn = db_conn()
    questions = conn.execute("SELECT * FROM questions WHERE approved = 1 ORDER BY question_number ASC, id ASC").fetchall()
    if not questions:
        conn.close()
        return page("Take Quiz", "<h1>Take Quiz</h1><p>No approved questions yet.</p>")

    participant_id = logged_in_participant(conn)
    if not participant_id:
        conn.close()
        return redirect(url_for("login", next=url_for("quiz")))

    answered_ids = {
        row["question_id"]
        for row in conn.execute("SELECT question_id FROM participant_answers WHERE participant_id = ?", (participant_id,))
    }
    resume_index = first_unanswered_index(questions, answered_ids)
    if resume_index is None:
        conn.close()
        return complete_quiz_page("You've already answered every available question.")

    try:
        index = int(request.values.get("q", "0"))
    except (TypeError, ValueError):
        index = 0
    index = max(0, min(index, len(questions) - 1))
    if request.method == "GET" and index != resume_index:
        conn.close()
        return redirect(url_for("quiz", q=resume_index))
    if questions[index]["id"] in answered_ids:
        conn.close()
        return redirect(url_for("quiz", q=resume_index))
    question = questions[index]

    if request.method == "POST":
        valid_answer = False
        if question["is_open_text"]:
            message = request.form.get("message", "").strip()[:MAX_RESPONSE_LENGTH]
            author = request.form.get("author", "Anonymous").strip()[:80] or "Anonymous"
            if message:
                conn.execute("INSERT INTO text_responses (question_id, author, message, created_at) VALUES (?, ?, ?, ?)", (question["id"], author, message, now()))
                valid_answer = True
        else:
            try:
                choice = int(request.form.get("choice", "0"))
            except (TypeError, ValueError):
                choice = 0
            if 1 <= choice <= len(options_for(question)):
                conn.execute("INSERT INTO votes (question_id, choice, created_at) VALUES (?, ?, ?)", (question["id"], choice, now()))
                valid_answer = True
        if valid_answer and participant_id:
            conn.execute("INSERT OR IGNORE INTO participant_answers (participant_id, question_id, created_at) VALUES (?, ?, ?)", (participant_id, question["id"], now()))
            answered = conn.execute("SELECT COUNT(*) FROM participant_answers WHERE participant_id = ?", (participant_id,)).fetchone()[0]
            for milestone in range(TOKEN_MILESTONE, answered + 1, TOKEN_MILESTONE):
                conn.execute("INSERT OR IGNORE INTO drink_tokens (participant_id, milestone, created_at) VALUES (?, ?, ?)", (participant_id, milestone, now()))
        conn.commit()
        conn.close()
        if not valid_answer:
            return redirect(url_for("quiz", q=resume_index))
        next_index = first_unanswered_index(questions, answered_ids | {question["id"]})
        if next_index is None:
            return complete_quiz_page("Your answer was saved.")
        return redirect(url_for("quiz", q=next_index))

    body = f"<p class='muted'>Question {index + 1} of {len(questions)} · Playing as {escape(session.get('participant_name') or '')} (<a href='/logout'>switch</a>)</p><h1>Take Quiz</h1><div class='question left'><h3>{escape(strip_internal_round_labels(question['text']))}</h3><form method='post' action='{escape(url_for('quiz', q=index))}' class='left'>"
    if question["is_open_text"]:
        body += "<input name='author' maxlength='80' placeholder='Your name (optional)'><textarea name='message' maxlength='2000' required placeholder='Type your answer here'></textarea>"
    else:
        for number, option in enumerate(options_for(question), 1):
            body += f"<label class='choice'><input type='radio' name='choice' value='{number}' required>{escape(option)}</label>"
    body += "<button class='btn btn-ok' type='submit'>Submit Answer</button></form></div><a class='btn btn-sec' href='/'>Back to Menu</a>"
    conn.close()
    return page("Take Quiz", body)


def participant_stats(conn, sort_mode="admin"):
    order_by = {
        "admin": "answered DESC, name ASC",
        "leaderboard": "total_tokens DESC, answered DESC, name ASC",
    }.get(sort_mode, "answered DESC, name ASC")
    return conn.execute(
        f"""
        WITH answered AS (
            SELECT participant_id, COUNT(*) AS answered
            FROM participant_answers
            GROUP BY participant_id
        ),
        tokens AS (
            SELECT participant_id,
                   SUM(CASE WHEN redeemed_at IS NULL THEN 1 ELSE 0 END) AS unredeemed,
                   SUM(CASE WHEN redeemed_at IS NOT NULL THEN 1 ELSE 0 END) AS redeemed,
                   COUNT(*) AS total_tokens
            FROM drink_tokens
            GROUP BY participant_id
        )
        SELECT p.id,
               COALESCE(p.name, 'Player ' || p.id) AS name,
               p.login_count,
               COALESCE(a.answered, 0) AS answered,
               COALESCE(t.unredeemed, 0) AS unredeemed,
               COALESCE(t.redeemed, 0) AS redeemed,
               COALESCE(t.total_tokens, 0) AS total_tokens
        FROM participants p
        LEFT JOIN answered a ON a.participant_id = p.id
        LEFT JOIN tokens t ON t.participant_id = p.id
        ORDER BY {order_by}
        """
    ).fetchall()


@app.route("/answers")
def answers():
    with closing(db_conn()) as conn:
        questions = conn.execute("SELECT * FROM questions WHERE approved = 1 ORDER BY question_number ASC, id ASC").fetchall()
        body = "<h1>📊 Community Answers</h1><p class='muted'>Live results from the room.</p><a class='btn btn-sec' href='/'>Back to Menu</a>"
        for question in questions:
            qid = question["id"]
            body += f"<div class='question left'><h3>❓ {escape(strip_internal_round_labels(question['text']))}</h3>"
            if question["is_open_text"]:
                responses = conn.execute("SELECT id, author, message, created_at FROM text_responses WHERE question_id = ? ORDER BY id DESC", (qid,)).fetchall()
                if responses:
                    common = Counter([" ".join(row["message"].split()).casefold() for row in responses]).most_common(5)
                    body += "<p class='muted'>Common themes:</p><ul>" + "".join(f"<li>{escape(answer)} — {count}</li>" for answer, count in common) + "</ul><p class='muted'>Individual responses:</p>"
                    for response in responses:
                        delete = f"<form method='post' action='/admin/delete-response/{response['id']}'><button class='btn btn-del small'>Delete</button></form>" if admin_required() else ""
                        body += f"<div class='resp'><strong>{escape(response['author'])}</strong>: {escape(response['message'])}{delete}</div>"
                else:
                    body += "<p class='muted'>No answers yet.</p>"
            else:
                options = options_for(question)
                rows = conn.execute("SELECT choice, COUNT(*) AS total FROM votes WHERE question_id = ? GROUP BY choice", (qid,)).fetchall()
                counts = {row["choice"]: row["total"] for row in rows}
                total = sum(counts.values())
                for number, option in enumerate(options, 1):
                    count = counts.get(number, 0)
                    percent = round((count / total) * 100) if total else 0
                    body += f"<p>{escape(option)} — <strong>{count}</strong> ({percent}%)</p><div class='bar'><div class='fill' style='width:{percent}%'></div></div>"
            if admin_required():
                body += f"<div class='admin-row'><a class='btn btn-warn small' href='/admin/edit-question/{qid}'>Edit</a><form method='post' action='/admin/delete-question/{qid}' onsubmit=\"return confirm('Delete this question and all its answers?');\"><button class='btn btn-del small'>Delete</button></form></div>"
            body += "</div>"
    return page("Community Answers", body)


@app.route("/submit-question", methods=["GET", "POST"])
def submit_question():
    error = ""
    if request.method == "POST":
        text, is_open, options = form_values(request.form)
        error_text = validate_question(text, is_open, options)
        if error_text:
            error = f"<div class='error'>{escape(error_text)}</div>"
        else:
            with closing(db_conn()) as conn:
                conn.execute("INSERT INTO suggestions (text, is_open_text, op1, op2, op3, op4, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (text[:500], is_open, options[0][:200], options[1][:200], options[2][:200], options[3][:200], now()))
                conn.commit()
            return page("Question Submitted", "<h1>Thank you!</h1><div class='notice'>Your question is waiting for host approval.</div><a class='btn btn-sec' href='/'>Back to Menu</a>")
    return question_form("Submit Question", url_for("submit_question"), {"is_open_text": 1}, error)


def admin_tv_html(conn):
    html = ["<h2>TV Screens</h2><p class='muted'>The TV rotates these every 12 seconds. Score boards with nobody on them are skipped.</p>"]
    for board in tv_boards(conn, include_hidden=True):
        if "message" in board:
            html.append(
                f"<div class='question left'><strong>{escape(board['title'])}</strong><p>{escape(board['message'])}</p>"
                f"<form method='post' action='/admin/tv/message/{board['id']}/delete'><button class='btn btn-del small'>Remove Message Screen</button></form></div>"
            )
            continue
        checked = " checked" if board["enabled"] else ""
        html.append(
            f"<div class='question left'><form method='post' action='/admin/tv/screen/{board['key']}' class='form'>"
            f"<input name='title' maxlength='60' required value='{escape(board['title'])}'>"
            f"<label class='choice'><input type='checkbox' name='enabled' value='1'{checked}> Show on TV</label>"
            "<button class='btn btn-ok small' type='submit'>Save</button></form>"
            f"<form method='post' action='/admin/tv/clear/{board['key']}' onsubmit=\"return confirm('Clear all of these scores?');\"><button class='btn btn-del small'>Clear Scores</button></form>"
        )
        if board["key"] == "dopewars":
            for row in dopewars_leaderboard(conn):
                html.append(
                    f"<form method='post' action='/admin/dopewars-score/{row['participant_id']}/delete' class='admin-row'>"
                    f"<span>{escape(row['name'])}: ${row['top_score']}</span><button class='btn btn-del small'>Remove</button></form>"
                )
        html.append("</div>")
    html.append(
        "<div class='question left'><strong>Add a Message Screen</strong><form method='post' action='/admin/tv/message' class='form'>"
        "<input name='title' maxlength='60' required placeholder='Title, e.g. Tonight'>"
        "<textarea name='body' maxlength='300' required placeholder='Message, e.g. $3 pints until 9'></textarea>"
        "<button class='btn btn-ok small' type='submit'>Add to TV</button></form></div>"
    )
    return "".join(html)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST" and request.form.get("action") == "login":
        if request.form.get("password", "") == ADMIN_PASS:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        return page("Admin", "<h1>Host Admin</h1><div class='error'>Incorrect code.</div><a class='btn btn-sec' href='/admin'>Try again</a>")
    if not admin_required():
        return page("Admin", "<h1>Host Admin</h1><form method='post'><input type='password' name='password' required placeholder='Admin code'><input type='hidden' name='action' value='login'><button class='btn btn-ok' type='submit'>Log In</button></form>")

    with closing(db_conn()) as conn:
        suggestions = conn.execute("SELECT * FROM suggestions ORDER BY id ASC").fetchall()
        questions = conn.execute("SELECT * FROM questions ORDER BY id DESC").fetchall()
        participants = participant_stats(conn)
        tv_html = admin_tv_html(conn)
    body = "<h1>Host Admin</h1><form method='post' action='/admin/play-as-host'><button class='btn btn-ok' type='submit'>Play as Host (quiz, Dopewars, drawing)</button></form><a class='btn btn-ok' href='/admin/add-question'>Add Question</a><h2>Participant Drink Tokens</h2>"
    if participants:
        body += "<table class='table'><tr><th>Player</th><th>Answered</th><th>Tokens ready</th><th>Given</th><th>Progress</th><th>Action</th></tr>"
        for participant in participants:
            progress = participant["answered"] % TOKEN_MILESTONE
            body += f"<tr><td>{escape(participant['name'])}</td><td>{participant['answered']}</td><td>{participant['unredeemed']}</td><td>{participant['redeemed']}</td><td>{progress}/{TOKEN_MILESTONE}</td><td><a class='btn btn-ok small' href='/admin/redeem-token/{participant['id']}'>Redeem</a><form method='post' action='/admin/rename/{participant['id']}' class='admin-row'><input name='name' maxlength='{PLAYER_NAME_MAX_LENGTH}' required placeholder='New name' style='width:auto'><button class='btn btn-warn small'>Rename</button></form></td></tr>"
        body += "</table>"
    else:
        body += "<p class='muted'>No participants yet.</p>"
    body += "<h2>Pending Submissions</h2>"
    if not suggestions:
        body += "<p class='muted'>No pending submissions.</p>"
    for suggestion in suggestions:
        body += f"<div class='question left'><strong>{escape(strip_internal_round_labels(suggestion['text']))}</strong><p class='muted'>{ 'Free write' if suggestion['is_open_text'] else 'Multiple choice'}</p>"
        if not suggestion["is_open_text"]:
            body += "<br>".join(escape(option) for option in options_for(suggestion))
        body += f"<div class='admin-row'><a class='btn btn-warn small' href='/admin/edit-suggestion/{suggestion['id']}'>Edit</a><form method='post' action='/admin/approve/{suggestion['id']}'><button class='btn btn-ok small'>Approve</button></form><form method='post' action='/admin/reject/{suggestion['id']}'><button class='btn btn-del small'>Reject</button></form></div></div>"
    body += "<h2>Active Questions</h2>"
    for question in questions:
        kind = "Free write" if question["is_open_text"] else "Multiple choice"
        body += f"<div class='question left'><strong>{escape(strip_internal_round_labels(question['text']))}</strong><p class='muted'>{kind} · Question {question['question_number']} · ID {question['id']}</p><div class='admin-row'><a class='btn btn-warn small' href='/admin/edit-question/{question['id']}'>Edit</a><form method='post' action='/admin/delete-question-number/{question['question_number']}' onsubmit=\"return confirm('Delete this question and all answers?');\"><button class='btn btn-del small'>Delete</button></form></div></div>"
    body += tv_html
    body += "<h2>Drawing with Friends</h2><form method='post' action='/admin/drawing/end' onsubmit=\"return confirm('End the current drawing round?');\"><button class='btn btn-del small'>End Current Drawing Round</button></form>"
    body += "<a class='btn btn-sec' href='/tv'>TV Screen</a><a class='btn btn-sec' href='/answers'>View Community Answers</a><a class='btn btn-sec' href='/gold-users'>View Gold Users</a><a class='btn btn-sec' href='/admin/logout'>Log Out</a><a class='btn btn-sec' href='/'>Back to Menu</a>"
    return page("Host Admin", body)


@app.route("/admin/play-as-host", methods=["POST"])
def admin_play_as_host():
    denied = require_admin()
    if denied:
        return denied
    with closing(db_conn()) as conn:
        row = conn.execute("SELECT id, name FROM participants WHERE name_key = 'host'").fetchone()
        if row:
            participant_id, name = row["id"], row["name"]
        else:
            participant_id, name = conn.execute(
                "INSERT INTO participants (pin, name, name_key, pin_hash, created_at, last_seen_at) VALUES ('host', 'Host', 'host', ?, ?, ?)",
                (generate_password_hash(secrets.token_hex(16), method=PIN_HASH_METHOD), now(), now()),
            ).lastrowid, "Host"
        conn.commit()
    session.pop("dopewars_state", None)
    session["participant_id"] = participant_id
    session["participant_name"] = name
    return redirect(url_for("menu"))


@app.route("/admin/rename/<int:participant_id>", methods=["POST"])
def admin_rename(participant_id):
    denied = require_admin()
    if denied:
        return denied
    name = normalize_player_name(request.form.get("name"))
    with closing(db_conn()) as conn:
        taken = conn.execute("SELECT 1 FROM participants WHERE name_key = ? AND id != ?", (name.casefold(), participant_id)).fetchone()
        if name and not taken:
            conn.execute("UPDATE participants SET name = ?, name_key = ? WHERE id = ?", (name, name.casefold(), participant_id))
            conn.execute("UPDATE drawing_players SET nickname = ? WHERE participant_id = ?", (name, participant_id))
            conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/tv/screen/<key>", methods=["POST"])
def admin_tv_screen(key):
    denied = require_admin()
    if denied:
        return denied
    if key in TV_BOARD_KEYS:
        title = re.sub(r"\s+", " ", request.form.get("title", "")).strip()[:60]
        with closing(db_conn()) as conn:
            conn.execute(
                "INSERT INTO tv_screens (key, title, enabled) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET title = excluded.title, enabled = excluded.enabled",
                (key, title, 1 if request.form.get("enabled") else 0),
            )
            conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/tv/clear/<key>", methods=["POST"])
def admin_tv_clear(key):
    denied = require_admin()
    if denied:
        return denied
    statement = {
        "dopewars": "DELETE FROM dopewars_scores",
        "mvp": "UPDATE participants SET login_count = 0",
        "drawing": "UPDATE drawing_players SET points = 0",
    }.get(key)
    if statement:
        with closing(db_conn()) as conn:
            conn.execute(statement)
            conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/dopewars-score/<int:participant_id>/delete", methods=["POST"])
def admin_delete_dopewars_score(participant_id):
    denied = require_admin()
    if denied:
        return denied
    with closing(db_conn()) as conn:
        conn.execute("DELETE FROM dopewars_scores WHERE participant_id = ?", (participant_id,))
        conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/tv/message", methods=["POST"])
def admin_tv_message():
    denied = require_admin()
    if denied:
        return denied
    title = request.form.get("title", "").strip()[:60]
    text = request.form.get("body", "").strip()[:300]
    if title and text:
        with closing(db_conn()) as conn:
            conn.execute("INSERT INTO tv_messages (title, body) VALUES (?, ?)", (title, text))
            conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/tv/message/<int:message_id>/delete", methods=["POST"])
def admin_tv_message_delete(message_id):
    denied = require_admin()
    if denied:
        return denied
    with closing(db_conn()) as conn:
        conn.execute("DELETE FROM tv_messages WHERE id = ?", (message_id,))
        conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/redeem-token/<int:participant_id>", methods=["GET", "POST"])
def redeem_token(participant_id):
    denied = require_admin()
    if denied:
        return denied
    with closing(db_conn()) as conn:
        token = conn.execute("SELECT id FROM drink_tokens WHERE participant_id = ? AND redeemed_at IS NULL ORDER BY milestone LIMIT 1", (participant_id,)).fetchone()
        if token:
            conn.execute("UPDATE drink_tokens SET redeemed_at = ? WHERE id = ?", (now(), token["id"]))
            conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/add-question", methods=["GET", "POST"])
def add_question():
    denied = require_admin()
    if denied:
        return denied
    error = ""
    if request.method == "POST":
        text, is_open, options = form_values(request.form)
        error_text = validate_question(text, is_open, options)
        if error_text:
            error = f"<div class='error'>{escape(error_text)}</div>"
        else:
            with closing(db_conn()) as conn:
                conn.execute("INSERT INTO questions (text, is_open_text, op1, op2, op3, op4, approved, created_at, question_number) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)", (text[:500], is_open, options[0][:200], options[1][:200], options[2][:200], options[3][:200], now(), next_question_number(conn)))
                conn.commit()
            return redirect(url_for("admin"))
    return question_form("Add Question", url_for("add_question"), {"is_open_text": 1}, error)


@app.route("/admin/edit-question/<int:question_id>", methods=["GET", "POST"])
def edit_question(question_id):
    denied = require_admin()
    if denied:
        return denied
    conn = db_conn()
    question = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    if not question:
        conn.close()
        return page("Not Found", "<h1>Question not found</h1>")
    error = ""
    if request.method == "POST":
        text, is_open, options = form_values(request.form)
        error_text = validate_question(text, is_open, options)
        if error_text:
            error = f"<div class='error'>{escape(error_text)}</div>"
            question = dict(question)
            question.update({"text": text, "is_open_text": is_open, **{f"op{i}": options[i - 1] for i in range(1, 5)}})
        else:
            conn.execute("UPDATE questions SET text = ?, is_open_text = ?, op1 = ?, op2 = ?, op3 = ?, op4 = ? WHERE id = ?", (text[:500], is_open, options[0][:200], options[1][:200], options[2][:200], options[3][:200], question_id))
            conn.commit()
            conn.close()
            return redirect(url_for("admin"))
    result = question_form("Edit Question", url_for("edit_question", question_id=question_id), question, error)
    conn.close()
    return result


@app.route("/admin/edit-suggestion/<int:suggestion_id>", methods=["GET", "POST"])
def edit_suggestion(suggestion_id):
    denied = require_admin()
    if denied:
        return denied
    conn = db_conn()
    suggestion = conn.execute("SELECT * FROM suggestions WHERE id = ?", (suggestion_id,)).fetchone()
    if not suggestion:
        conn.close()
        return page("Not Found", "<h1>Suggestion not found</h1>")
    error = ""
    if request.method == "POST":
        text, is_open, options = form_values(request.form)
        error_text = validate_question(text, is_open, options)
        if error_text:
            error = f"<div class='error'>{escape(error_text)}</div>"
            suggestion = dict(suggestion)
            suggestion.update({"text": text, "is_open_text": is_open, **{f"op{i}": options[i - 1] for i in range(1, 5)}})
        else:
            conn.execute("UPDATE suggestions SET text = ?, is_open_text = ?, op1 = ?, op2 = ?, op3 = ?, op4 = ? WHERE id = ?", (text[:500], is_open, options[0][:200], options[1][:200], options[2][:200], options[3][:200], suggestion_id))
            conn.commit()
            conn.close()
            return redirect(url_for("admin"))
    result = question_form("Edit Submission", url_for("edit_suggestion", suggestion_id=suggestion_id), suggestion, error)
    conn.close()
    return result


@app.route("/admin/approve/<int:suggestion_id>", methods=["POST"])
def approve_suggestion(suggestion_id):
    denied = require_admin()
    if denied:
        return denied
    with closing(db_conn()) as conn:
        suggestion = conn.execute("SELECT * FROM suggestions WHERE id = ?", (suggestion_id,)).fetchone()
        if suggestion:
            text = strip_internal_round_labels(suggestion["text"])
            conn.execute("INSERT INTO questions (text, is_open_text, op1, op2, op3, op4, approved, created_at, question_number) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)", (text, suggestion["is_open_text"], suggestion["op1"], suggestion["op2"], suggestion["op3"], suggestion["op4"], now(), next_question_number(conn)))
            conn.execute("DELETE FROM suggestions WHERE id = ?", (suggestion_id,))
            conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/reject/<int:suggestion_id>", methods=["POST"])
def reject_suggestion(suggestion_id):
    denied = require_admin()
    if denied:
        return denied
    with closing(db_conn()) as conn:
        conn.execute("DELETE FROM suggestions WHERE id = ?", (suggestion_id,))
        conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/delete-question/<int:question_id>", methods=["POST"])
def delete_question(question_id):
    denied = require_admin()
    if denied:
        return denied
    with closing(db_conn()) as conn:
        conn.execute("DELETE FROM votes WHERE question_id = ?", (question_id,))
        conn.execute("DELETE FROM text_responses WHERE question_id = ?", (question_id,))
        conn.execute("DELETE FROM participant_answers WHERE question_id = ?", (question_id,))
        conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/delete-question-number/<int:question_number>", methods=["POST"])
def delete_question_number(question_number):
    denied = require_admin()
    if denied:
        return denied
    with closing(db_conn()) as conn:
        question = conn.execute("SELECT id, seed_key, question_number FROM questions WHERE question_number = ?", (question_number,)).fetchone()
        if question:
            if question["seed_key"] and seed_question_number(question["seed_key"]) == question["question_number"]:
                record_deleted_seed_question_number(question["question_number"])
            conn.execute("DELETE FROM votes WHERE question_id = ?", (question["id"],))
            conn.execute("DELETE FROM text_responses WHERE question_id = ?", (question["id"],))
            conn.execute("DELETE FROM participant_answers WHERE question_id = ?", (question["id"],))
            conn.execute("DELETE FROM questions WHERE id = ?", (question["id"],))
            conn.commit()
    return redirect(url_for("admin"))


@app.route("/admin/delete-response/<int:response_id>", methods=["POST"])
def delete_response(response_id):
    denied = require_admin()
    if denied:
        return denied
    with closing(db_conn()) as conn:
        conn.execute("DELETE FROM text_responses WHERE id = ?", (response_id,))
        conn.commit()
    return redirect(request.referrer or url_for("answers"))


@app.route("/admin/logout")
def logout():
    session.clear(); return redirect(url_for("menu"))


init_db()

def serve_portal_port():
    from werkzeug.serving import make_server
    try:
        make_server(FLASK_HOST, PORTAL_PORT, app, threaded=True).serve_forever()
    except OSError as error:
        print(f"Could not open the hotspot port {PORTAL_PORT}: {error}", flush=True)


if __name__ == "__main__":
    if PORTAL_PORT and PORTAL_PORT != FLASK_PORT:
        threading.Thread(target=serve_portal_port, daemon=True).start()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True)
