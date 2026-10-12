from collections import Counter
from contextlib import closing
from datetime import datetime
from html import escape
import os
import random
import re
import sqlite3

from flask import Flask, redirect, request, session, url_for


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


def participant_for_pin(conn, pin):
    row = conn.execute("SELECT * FROM participants WHERE pin = ?", (pin,)).fetchone()
    if row:
        conn.execute("UPDATE participants SET last_seen_at = ? WHERE id = ?", (now(), row["id"]))
        return row["id"]
    cur = conn.execute("INSERT INTO participants (pin, created_at, last_seen_at) VALUES (?, ?, ?)", (pin, now(), now()))
    return cur.lastrowid


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
        SELECT p.pin, ds.top_score, ds.achieved_at
        FROM dopewars_scores ds
        JOIN participants p ON p.id = ds.participant_id
        ORDER BY ds.top_score DESC, ds.achieved_at ASC, p.pin ASC
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


@app.route("/")
def menu():
    with closing(db_conn()) as conn:
        dopewars_scores = dopewars_leaderboard(conn)
    body = [
        "<h1>🍺 Cotton Flat Bar Quiz</h1>",
        "<p class='muted'>Funny sociology, questionable opinions, and community data.</p>",
        "<a class='btn btn-ok' href='/quiz'>▶ Take Quiz</a>",
        "<a class='btn btn-sec' href='/submit-question'>✍ Submit Question</a>",
        "<a class='btn btn-sec' href='/answers'>📊 Community Answers</a>",
        "<a class='btn btn-sec' href='/gold-users'>🥇 Gold Users</a>",
        "<a class='btn btn-sec' href='/games/dopewars'>🕹 Games</a>",
        "<a class='btn btn-sec' href='/admin'>🛠 Admin</a>",
        "<div class='question left'><h2>🕹 Dopewars</h2><p>Classic text-based street trading across NYC.</p><a class='btn btn-ok' href='/games/dopewars'>Play Dopewars</a><h3>High Scores</h3>",
    ]
    if dopewars_scores:
        body.append("<table class='table'><tr><th>#</th><th>PIN</th><th>Top Score</th><th>Date</th></tr>")
        for index, row in enumerate(dopewars_scores, 1):
            body.append(
                f"<tr><td>{index}</td><td>{escape(row['pin'])}</td><td>${row['top_score']}</td><td>{escape((row['achieved_at'] or '').replace('T', ' '))}</td></tr>"
            )
        body.append("</table>")
    else:
        body.append("<p class='muted'>No Dopewars scores yet. Be the first to set one.</p>")
    body.append("</div>")
    return page("Cotton Flat Bar Quiz", "".join(body))


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
        body.append("<table class='table'><tr><th>#</th><th>PIN</th><th>Answered</th><th>Tokens ready</th><th>Tokens redeemed</th><th>Total tokens</th><th>Progress</th></tr>")
        for index, participant in enumerate(participants, 1):
            progress = participant["answered"] % TOKEN_MILESTONE
            body.append(
                f"<tr><td>{index}</td><td>{escape(participant['pin'])}</td><td>{participant['answered']}</td>"
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
    if request.method == "POST" and request.form.get("action") == "set_pin":
        pin = normalize_pin(request.form.get("pin"))
        if len(pin) < MIN_PIN_LENGTH:
            body = "<h1>Enter your PIN</h1><p class='muted'>Use your quiz PIN so your Dopewars high score can be saved to your profile.</p><div class='error'>Use at least 4 letters or numbers.</div>" + pin_form(url_for("dopewars"), "Play Dopewars", "<input type='hidden' name='action' value='set_pin'>")
            return page("Enter PIN", body)
        with closing(db_conn()) as conn:
            participant_id = participant_for_pin(conn, pin)
            conn.commit()
        session["participant_pin"] = pin
        session["participant_id"] = participant_id
        return redirect(url_for("dopewars"))

    if not session.get("participant_pin"):
        body = "<h1>Enter your PIN</h1><p class='muted'>Use your quiz PIN so your Dopewars high score can be saved to your profile.</p>" + pin_form(url_for("dopewars"), "Play Dopewars", "<input type='hidden' name='action' value='set_pin'>")
        return page("Enter PIN", body)

    participant_id = session.get("participant_id")
    if not participant_id:
        with closing(db_conn()) as conn:
            participant_id = participant_for_pin(conn, session["participant_pin"])
            conn.commit()
        session["participant_id"] = participant_id

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

    if request.method == "POST" and not session.get("participant_pin"):
        pin = normalize_pin(request.form.get("pin"))
        if len(pin) < MIN_PIN_LENGTH:
            conn.close()
            return page("Enter PIN", "<h1>Enter your PIN</h1><div class='error'>Use at least 4 letters or numbers.</div>" + pin_form())
        participant_id = participant_for_pin(conn, pin)
        conn.commit()
        conn.close()
        session["participant_pin"] = pin
        session["participant_id"] = participant_id
        return redirect(url_for("quiz"))

    if not session.get("participant_pin"):
        conn.close()
        return page("Enter PIN", "<h1>Enter your PIN</h1><p class='muted'>Use the same PIN each time so the host can track your answers and drink-token progress.</p>" + pin_form())

    participant_id = session.get("participant_id")
    if not participant_id:
        participant_id = participant_for_pin(conn, session["participant_pin"])
        conn.commit()
        session["participant_id"] = participant_id

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

    body = f"<p class='muted'>Question {index + 1} of {len(questions)} · PIN {escape(session['participant_pin'])}</p><h1>Take Quiz</h1><div class='question left'><h3>{escape(strip_internal_round_labels(question['text']))}</h3><form method='post' action='{escape(url_for('quiz', q=index))}' class='left'>"
    if question["is_open_text"]:
        body += "<input name='author' maxlength='80' placeholder='Your name (optional)'><textarea name='message' maxlength='2000' required placeholder='Type your answer here'></textarea>"
    else:
        for number, option in enumerate(options_for(question), 1):
            body += f"<label class='choice'><input type='radio' name='choice' value='{number}' required>{escape(option)}</label>"
    body += "<button class='btn btn-ok' type='submit'>Submit Answer</button></form></div><a class='btn btn-sec' href='/'>Back to Menu</a>"
    conn.close()
    return page("Take Quiz", body)


def pin_form(action="", button_label="Start Quiz", hidden_fields=""):
    action_attr = f" action='{escape(action)}'" if action else ""
    return f"<form method='post'{action_attr}>{hidden_fields}<input name='pin' maxlength='20' minlength='4' required pattern='[A-Za-z0-9]+' placeholder='Enter your PIN'><button class='btn btn-ok' type='submit'>{escape(button_label)}</button></form>"


def participant_stats(conn, sort_mode="admin"):
    order_by = {
        "admin": "answered DESC, p.pin ASC",
        "leaderboard": "total_tokens DESC, answered DESC, p.pin ASC",
    }.get(sort_mode, "answered DESC, p.pin ASC")
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
               p.pin,
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
    body = "<h1>Host Admin</h1><a class='btn btn-ok' href='/admin/add-question'>Add Question</a><h2>Participant Drink Tokens</h2>"
    if participants:
        body += "<table class='table'><tr><th>PIN</th><th>Answered</th><th>Tokens ready</th><th>Given</th><th>Progress</th><th>Action</th></tr>"
        for participant in participants:
            progress = participant["answered"] % TOKEN_MILESTONE
            body += f"<tr><td>{escape(participant['pin'])}</td><td>{participant['answered']}</td><td>{participant['unredeemed']}</td><td>{participant['redeemed']}</td><td>{progress}/{TOKEN_MILESTONE}</td><td><a class='btn btn-ok small' href='/admin/redeem-token/{participant['id']}'>Redeem</a></td></tr>"
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
    body += "<a class='btn btn-sec' href='/gold-users'>View Gold Users</a><a class='btn btn-sec' href='/admin/logout'>Log Out</a><a class='btn btn-sec' href='/'>Back to Menu</a>"
    return page("Host Admin", body)


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

if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True)
