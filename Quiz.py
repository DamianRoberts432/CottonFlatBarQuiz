from flask import Flask, request, session, redirect, url_for
from datetime import datetime
from html import escape
import os
import sqlite3

app = Flask(__name__)
# Set COTTON_FLAT_SECRET to a long random value before using this beyond tonight.
app.secret_key = os.environ.get("COTTON_FLAT_SECRET", "cotton-flat-bar-secret-key-1346")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "quiz.db")
ADMIN_PASS = os.environ.get("COTTON_FLAT_ADMIN_PASS", "1346")
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))


def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            is_open_text INTEGER NOT NULL DEFAULT 1,
            op1 TEXT DEFAULT '',
            op2 TEXT DEFAULT '',
            op3 TEXT DEFAULT '',
            op4 TEXT DEFAULT '',
            approved INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            choice INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(question_id) REFERENCES questions(id)
        );

        CREATE TABLE IF NOT EXISTS text_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            author TEXT NOT NULL DEFAULT 'Anonymous',
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(question_id) REFERENCES questions(id)
        );

        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            is_open_text INTEGER NOT NULL DEFAULT 1,
            op1 TEXT DEFAULT '',
            op2 TEXT DEFAULT '',
            op3 TEXT DEFAULT '',
            op4 TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


BASE_STYLE = """
<style>
*{box-sizing:border-box} body{font-family:Arial,sans-serif;background:#0f1115;color:#f4f7ff;padding:20px;text-align:center;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center} .card{background:#171b24;border:1px solid #2a3242;max-width:620px;width:100%;padding:25px;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.25);box-sizing:border-box} a.btn,button.btn{display:block;width:100%;margin:12px 0;padding:14px;border:0;border-radius:8px;background:#2f7cf6;color:white;text-decoration:none;cursor:pointer;font-size:16px;font-weight:bold} a.btn:hover,button.btn:hover{filter:brightness(.9)} .btn-sec{background:#495057!important}.btn-ok{background:#28a745!important}.btn-warn{background:#f0a500!important}.btn-del{background:#dc3545!important}.left{text-align:left} input,select,textarea{width:100%;padding:12px;margin:8px 0;border:1px solid #2a3242;background:#0f1115;color:white;border-radius:8px;box-sizing:border-box;font-size:15px} textarea{min-height:100px;resize:vertical}.notice{padding:12px;border-radius:8px;background:#1e3a2b;border:1px solid #2f6c4a;margin:12px 0}.error{padding:12px;border-radius:8px;background:#3d1f1f;border:1px solid #b75656;margin:12px 0}.question,.resp{padding:14px;border-left:4px solid #2f7cf6;background:#1e2433;margin:12px 0;border-radius:0 8px 8px 0;word-break:break-word}.muted{color:#aeb8c8;font-size:13px}.row{display:flex;gap:12px}.small{font-size:14px;padding:10px 12px}.choice{display:block;padding:10px 0;text-align:left}
</style>
"""


def page(title, body):
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)}</title>{BASE_STYLE}</head>"
        f"<body><main class='card'>{body}</main></body></html>"
    )


def now():
    return datetime.now().isoformat(timespec="seconds")


def admin_required():
    return bool(session.get("is_admin"))


def require_admin():
    if not admin_required():
        return redirect(url_for("admin"))
    return None


def options_for(question):
    return [question[f"op{i}"] for i in range(1, 5) if question[f"op{i}"].strip()]


@app.route("/health")
def health():
    return {"ok": True, "service": "CottonFlatBarQuiz"}, 200


@app.route("/")
def menu():
    body = """
    <h1>🍺 Cotton Flat Bar Quiz</h1>
    <p class='muted'>Choose an option below.</p>
    <a class='btn btn-ok' href='/quiz'>▶ Take Quiz</a>
    <a class='btn' href='/answers'>📋 See Answers</a>
    <a class='btn btn-warn' href='/submit-question'>💡 Submit Question</a>
    <hr><a class='btn btn-sec small' href='/admin'>Host Admin</a>
    """
    return page("Cotton Flat Bar Quiz", body)


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    conn = db_conn()
    questions = conn.execute(
        "SELECT * FROM questions WHERE approved = 1 ORDER BY id ASC"
    ).fetchall()

    if not questions:
        conn.close()
        return page("Take Quiz", "<h1>Take Quiz</h1><p>No approved questions yet. Please check back shortly.</p><a class='btn btn-sec' href='/'>Back to Menu</a>")

    try:
        index = int(request.values.get("q", "0"))
    except ValueError:
        index = 0
    index = max(0, min(index, len(questions) - 1))

    if request.method == "POST":
        question = questions[index]
        if question["is_open_text"]:
            message = request.form.get("message", "").strip()
            author = request.form.get("author", "Anonymous").strip() or "Anonymous"
            if message:
                conn.execute(
                    "INSERT INTO text_responses (question_id, author, message, created_at) VALUES (?, ?, ?, ?)",
                    (question["id"], author[:80], message[:2000], now()),
                )
                conn.commit()
        else:
            try:
                choice = int(request.form.get("choice", "0"))
            except ValueError:
                choice = 0
            if 1 <= choice <= len(options_for(question)):
                conn.execute(
                    "INSERT INTO votes (question_id, choice, created_at) VALUES (?, ?, ?)",
                    (question["id"], choice, now()),
                )
                conn.commit()
        conn.close()
        next_index = index + 1
        if next_index >= len(questions):
            return page("Quiz Complete", "<h1>Thanks for taking the quiz!</h1><p>Your answer has been saved.</p><a class='btn btn-ok' href='/answers'>See Answers</a><a class='btn btn-sec' href='/'>Back to Menu</a>")
        return redirect(url_for("quiz", q=next_index))

    question = questions[index]
    progress = f"Question {index + 1} of {len(questions)}"
    body = f"<p class='muted'>{progress}</p><h1>Take Quiz</h1><div class='question left'>{escape(question['text'])}</div><form method='post'>"
    if question["is_open_text"]:
        body += "<input name='author' maxlength='80' placeholder='Your name (optional)'>"
        body += "<textarea name='message' maxlength='2000' required placeholder='Type your answer here'></textarea>"
    else:
        for number, option in enumerate(options_for(question), 1):
            body += f"<label class='choice'><input type='radio' name='choice' value='{number}' required> {escape(option)}</label>"
    body += "<button class='btn btn-ok' type='submit'>Submit Answer</button></form><a class='btn btn-sec' href='/'>Back to Menu</a>"
    conn.close()
    return page("Take Quiz", body)


@app.route("/answers")
def answers():
    conn = db_conn()
    questions = conn.execute("SELECT * FROM questions WHERE approved = 1 ORDER BY id ASC").fetchall()
    body = "<h1>Answers</h1><p class='muted'>Responses are anonymous unless someone entered a name.</p>"
    if not questions:
        body += "<p>No approved questions yet.</p>"
    for question in questions:
        body += f"<div class='question left'><strong>{escape(question['text'])}</strong>"
        if question["is_open_text"]:
            responses = conn.execute("SELECT author, message, created_at FROM text_responses WHERE question_id = ? ORDER BY id DESC", (question["id"],)).fetchall()
            if responses:
                for response in responses:
                    body += f"<div class='resp'><strong>{escape(response['author'])}</strong><br>{escape(response['message'])}<br><span class='muted'>{escape(response['created_at'])}</span></div>"
            else:
                body += "<p class='muted'>No answers yet.</p>"
        else:
            counts = {row['choice']: row['total'] for row in conn.execute("SELECT choice, COUNT(*) AS total FROM votes WHERE question_id = ? GROUP BY choice", (question["id"],)).fetchall()}
            for number, option in enumerate(options_for(question), 1):
                body += f"<p>{escape(option)}: <strong>{counts.get(number, 0)}</strong></p>"
        body += "</div>"
    conn.close()
    body += "<a class='btn btn-sec' href='/'>Back to Menu</a>"
    return page("Answers", body)


@app.route("/submit-question", methods=["GET", "POST"])
def submit_question():
    message = ""
    if request.method == "POST":
        text = request.form.get("text", "").strip()
        question_type = request.form.get("question_type", "open")
        options = [request.form.get(f"op{i}", "").strip() for i in range(1, 5)]
        is_open_text = 1 if question_type == "open" else 0
        if not text:
            message = "<div class='error'>Please enter a question.</div>"
        elif not is_open_text and len([option for option in options if option]) < 2:
            message = "<div class='error'>Multiple-choice questions need at least two options.</div>"
        else:
            conn = db_conn()
            conn.execute("INSERT INTO suggestions (text, is_open_text, op1, op2, op3, op4, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (text[:500], is_open_text, options[0][:200], options[1][:200], options[2][:200], options[3][:200], now()))
            conn.commit()
            conn.close()
            return page("Question Submitted", "<h1>Thank you!</h1><div class='notice'>Your question was submitted for host approval.</div><a class='btn btn-sec' href='/'>Back to Menu</a>")

    body = f"""
    <h1>Submit Question</h1>
    <p class='muted'>Questions are reviewed by the host before appearing in the quiz.</p>
    {message}
    <form method='post' class='left'>
      <textarea name='text' maxlength='500' required placeholder='Your question'></textarea>
      <label>Question type</label>
      <select name='question_type'>
        <option value='open'>Open-text response</option>
        <option value='choice'>Multiple choice</option>
      </select>
      <input name='op1' maxlength='200' placeholder='Choice 1 (only needed for multiple choice)'>
      <input name='op2' maxlength='200' placeholder='Choice 2'>
      <input name='op3' maxlength='200' placeholder='Choice 3 (optional)'>
      <input name='op4' maxlength='200' placeholder='Choice 4 (optional)'>
      <button class='btn btn-warn' type='submit'>Submit for Approval</button>
    </form>
    <a class='btn btn-sec' href='/'>Back to Menu</a>
    """
    return page("Submit Question", body)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST" and request.form.get("action") == "login":
        if request.form.get("password", "") == ADMIN_PASS:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        return page("Admin", "<h1>Host Admin</h1><div class='error'>Incorrect code.</div><a class='btn btn-sec' href='/admin'>Try Again</a>")

    if not admin_required():
        return page("Admin", """
        <h1>Host Admin</h1><p class='muted'>Enter the host approval code.</p>
        <form method='post'><input type='password' name='password' inputmode='numeric' required autofocus placeholder='Admin code'>
        <input type='hidden' name='action' value='login'><button class='btn' type='submit'>Enter Admin</button></form>
        <a class='btn btn-sec' href='/'>Back to Menu</a>
        """)

    conn = db_conn()
    suggestions = conn.execute("SELECT * FROM suggestions ORDER BY id ASC").fetchall()
    questions = conn.execute("SELECT * FROM questions ORDER BY id DESC").fetchall()
    body = "<h1>Host Admin</h1><a class='btn btn-ok' href='/admin/add-question'>Add Question</a><h2>Pending Submissions</h2>"
    if not suggestions:
        body += "<p class='muted'>No pending submissions.</p>"
    for suggestion in suggestions:
        kind = "Open text" if suggestion["is_open_text"] else "Multiple choice"
        body += f"<div class='question left'><strong>{escape(suggestion['text'])}</strong><br><span class='muted'>{kind}</span>"
        if not suggestion["is_open_text"]:
            body += "<br>" + "<br>".join(escape(option) for option in options_for(suggestion))
        body += f"<form method='post' action='/admin/approve/{suggestion['id']}'><button class='btn btn-ok' type='submit'>Approve</button></form><form method='post' action='/admin/reject/{suggestion['id']}'><button class='btn btn-del small' type='submit'>Reject</button></form></div>"
    body += "<hr><h2>Active Questions</h2>"
    for question in questions:
        body += f"<div class='question left'><strong>{escape(question['text'])}</strong><form method='post' action='/admin/delete-question/{question['id']}'><button class='btn btn-del small' type='submit'>Delete</button></form></div>"
    body += "<a class='btn btn-sec' href='/admin/logout'>Log Out</a><a class='btn btn-sec' href='/'>Back to Menu</a>"
    conn.close()
    return page("Host Admin", body)


@app.route("/admin/add-question", methods=["GET", "POST"])
def add_question():
    denied = require_admin()
    if denied:
        return denied
    if request.method == "POST":
        text = request.form.get("text", "").strip()
        question_type = request.form.get("question_type", "open")
        options = [request.form.get(f"op{i}", "").strip() for i in range(1, 5)]
        is_open_text = 1 if question_type == "open" else 0
        if text and (is_open_text or len([option for option in options if option]) >= 2):
            conn = db_conn()
            conn.execute("INSERT INTO questions (text, is_open_text, op1, op2, op3, op4, approved, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)", (text[:500], is_open_text, options[0][:200], options[1][:200], options[2][:200], options[3][:200], now()))
            conn.commit()
            conn.close()
            return redirect(url_for("admin"))
        error = "<div class='error'>Enter a question, and at least two choices for multiple choice.</div>"
    else:
        error = ""
    return page("Add Question", f"""<h1>Add Question</h1>{error}<form method='post' class='left'><textarea name='text' required maxlength='500' placeholder='Question'></textarea><select name='question_type'><option value='open'>Open text</option><option value='choice'>Multiple choice</option></select><input name='op1' maxlength='200' placeholder='Choice 1'><input name='op2' maxlength='200' placeholder='Choice 2'><input name='op3' maxlength='200' placeholder='Choice 3'><input name='op4' maxlength='200' placeholder='Choice 4'><button class='btn btn-ok' type='submit'>Add Question</button></form><a class='btn btn-sec' href='/admin'>Back to Admin</a>""")


@app.route("/admin/approve/<int:suggestion_id>", methods=["POST"])
def approve_suggestion(suggestion_id):
    denied = require_admin()
    if denied:
        return denied
    conn = db_conn()
    suggestion = conn.execute("SELECT * FROM suggestions WHERE id = ?", (suggestion_id,)).fetchone()
    if suggestion:
        conn.execute("INSERT INTO questions (text, is_open_text, op1, op2, op3, op4, approved, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)", (suggestion["text"], suggestion["is_open_text"], suggestion["op1"], suggestion["op2"], suggestion["op3"], suggestion["op4"], now()))
        conn.execute("DELETE FROM suggestions WHERE id = ?", (suggestion_id,))
        conn.commit()
    conn.close()
    return redirect(url_for("admin"))


@app.route("/admin/reject/<int:suggestion_id>", methods=["POST"])
def reject_suggestion(suggestion_id):
    denied = require_admin()
    if denied:
        return denied
    conn = db_conn()
    conn.execute("DELETE FROM suggestions WHERE id = ?", (suggestion_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


@app.route("/admin/delete-question/<int:question_id>", methods=["POST"])
def delete_question(question_id):
    denied = require_admin()
    if denied:
        return denied
    conn = db_conn()
    conn.execute("DELETE FROM votes WHERE question_id = ?", (question_id,))
    conn.execute("DELETE FROM text_responses WHERE question_id = ?", (question_id,))
    conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("menu"))


if __name__ == "__main__":
    init_db()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True)
