import io
import os
import tempfile
import unittest
from contextlib import closing
from shutil import copyfile
from pathlib import Path
from unittest.mock import patch


TEST_DB_DIR = tempfile.TemporaryDirectory()
os.environ.setdefault("COTTON_FLAT_DB_PATH", str(Path(TEST_DB_DIR.name) / "import.db"))

import Quiz


class QuizProgressTestCase(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(TEST_DB_DIR.name) / f"{self._testMethodName}.db"
        if self.db_path.exists():
            self.db_path.unlink()
        self.source_path = Path(TEST_DB_DIR.name) / f"{self._testMethodName}.py"
        copyfile(Path(Quiz.__file__), self.source_path)
        Quiz.DB_PATH = str(self.db_path)
        Quiz.SOURCE_FILE_PATH = str(self.source_path)
        Quiz.app.config["TESTING"] = True
        Quiz.DELETED_SEED_QUESTION_NUMBERS[:] = []
        Quiz.init_db()
        self.client = Quiz.app.test_client()

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()
        if self.source_path.exists():
            self.source_path.unlink()
        Quiz.SOURCE_FILE_PATH = Quiz.__file__
        Quiz.DELETED_SEED_QUESTION_NUMBERS[:] = []

    def approved_questions(self):
        conn = Quiz.db_conn()
        try:
            return conn.execute(
                "SELECT * FROM questions WHERE approved = 1 ORDER BY question_number ASC, id ASC"
            ).fetchall()
        finally:
            conn.close()

    def trim_questions(self, total):
        conn = Quiz.db_conn()
        try:
            conn.execute("DELETE FROM questions WHERE question_number > ?", (total,))
            conn.commit()
        finally:
            conn.close()

    def answer_question(self, client, index):
        question = self.approved_questions()[index]
        data = {"message": f"Answer {index}", "author": "Tester"} if question["is_open_text"] else {"choice": "1"}
        return client.post(f"/quiz?q={index}", data=data, follow_redirects=True)

    def answered_count(self, pin):
        conn = Quiz.db_conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*)
                   FROM participant_answers pa
                   JOIN participants p ON p.id = pa.participant_id
                   WHERE p.name_key = ?""",
                (pin.casefold(),),
            ).fetchone()
            return row[0]
        finally:
            conn.close()

    def token_milestones(self, pin):
        conn = Quiz.db_conn()
        try:
            rows = conn.execute(
                """SELECT dt.milestone
                   FROM drink_tokens dt
                   JOIN participants p ON p.id = dt.participant_id
                   WHERE p.name_key = ?
                   ORDER BY dt.milestone ASC""",
                (pin.casefold(),),
            ).fetchall()
            return [row[0] for row in rows]
        finally:
            conn.close()

    def answer_questions(self, client, start, total):
        for index in range(start, start + total):
            response = self.answer_question(client, index)
            self.assertEqual(response.status_code, 200)

    def make_admin(self, client=None):
        client = client or self.client
        with client.session_transaction() as session:
            session["is_admin"] = True
        return client

    def set_dopewars_pin(self, client=None, pin="dope1"):
        client = client or self.client
        client.post("/login", data={"name": pin, "pin": pin})
        return client

    def dopewars_top_score(self, pin):
        conn = Quiz.db_conn()
        try:
            row = conn.execute(
                """SELECT ds.top_score
                   FROM dopewars_scores ds
                   JOIN participants p ON p.id = ds.participant_id
                   WHERE p.name_key = ?""",
                (pin.casefold(),),
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def test_new_pin_starts_from_first_question(self):
        first_question = self.approved_questions()[0]["text"]

        response = self.client.post("/login", data={"name": "alpha1", "pin": "alpha1", "next": "/quiz"}, follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Question 1 of", body)
        self.assertIn(first_question, body)

    def test_returning_pin_resumes_at_first_unanswered_question(self):
        questions = self.approved_questions()
        first_question = questions[0]["text"]
        second_question = questions[1]["text"]

        first_client = Quiz.app.test_client()
        first_client.post("/login", data={"name": "resume1", "pin": "resume1", "next": "/quiz"}, follow_redirects=True)
        response = self.answer_question(first_client, 0)
        body = response.get_data(as_text=True)

        self.assertIn(second_question, body)
        self.assertNotIn(first_question, body)
        self.assertEqual(self.answered_count("RESUME1"), 1)

        returning_client = Quiz.app.test_client()
        response = returning_client.post("/login", data={"name": "resume1", "pin": "resume1", "next": "/quiz"}, follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertIn(second_question, body)
        self.assertNotIn(first_question, body)

    def test_different_pins_keep_independent_progress(self):
        questions = self.approved_questions()
        first_question = questions[0]["text"]
        second_question = questions[1]["text"]

        first_client = Quiz.app.test_client()
        first_client.post("/login", data={"name": "alpha2", "pin": "alpha2", "next": "/quiz"}, follow_redirects=True)
        self.answer_question(first_client, 0)

        second_client = Quiz.app.test_client()
        response = second_client.post("/login", data={"name": "beta2", "pin": "beta2", "next": "/quiz"}, follow_redirects=True)
        self.assertIn(first_question, response.get_data(as_text=True))

        returning_client = Quiz.app.test_client()
        response = returning_client.post("/login", data={"name": "alpha2", "pin": "alpha2", "next": "/quiz"}, follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertIn(second_question, body)
        self.assertNotIn(first_question, body)

    def test_completed_pin_sees_completion_instead_of_repeat_question(self):
        self.trim_questions(1)
        only_question = self.approved_questions()[0]["text"]

        first_client = Quiz.app.test_client()
        first_client.post("/login", data={"name": "done1", "pin": "done1", "next": "/quiz"}, follow_redirects=True)
        response = self.answer_question(first_client, 0)
        body = response.get_data(as_text=True)

        self.assertIn("Your answer was saved.", body)
        self.assertNotIn(only_question, body)

        returning_client = Quiz.app.test_client()
        response = returning_client.post("/login", data={"name": "done1", "pin": "done1", "next": "/quiz"}, follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertIn("already answered every available question.", body)
        self.assertNotIn(only_question, body)

    def test_tokens_are_issued_every_20_answers(self):
        self.trim_questions(60)
        client = Quiz.app.test_client()
        client.post("/login", data={"name": "token20", "pin": "token20", "next": "/quiz"}, follow_redirects=True)

        self.answer_questions(client, 0, 20)
        self.assertEqual(self.token_milestones("TOKEN20"), [20])

        self.answer_questions(client, 20, 20)
        self.assertEqual(self.token_milestones("TOKEN20"), [20, 40])

        self.answer_questions(client, 40, 20)
        self.assertEqual(self.token_milestones("TOKEN20"), [20, 40, 60])

    def test_reanswering_question_does_not_duplicate_tokens(self):
        self.trim_questions(20)
        client = Quiz.app.test_client()
        client.post("/login", data={"name": "nodupe1", "pin": "nodupe1", "next": "/quiz"}, follow_redirects=True)

        self.answer_questions(client, 0, 20)
        self.assertEqual(self.token_milestones("NODUPE1"), [20])

        response = self.answer_question(client, 19)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.token_milestones("NODUPE1"), [20])

    def test_make_seed_questions_skips_deleted_numbers_but_keeps_source_numbers(self):
        Quiz.DELETED_SEED_QUESTION_NUMBERS[:] = [2, 5]

        questions = Quiz.make_seed_questions()

        numbers = [question["question_number"] for question in questions[:6]]
        self.assertEqual(numbers, [1, 3, 4, 6, 7, 8])
        self.assertNotIn(2, numbers)
        self.assertNotIn(5, numbers)
        self.assertEqual(len(questions), 198)

    def test_admin_can_delete_by_question_number_and_sync_source(self):
        self.make_admin()
        response = self.client.post("/admin/delete-question-number/5", follow_redirects=False)

        self.assertEqual(response.status_code, 302)

        conn = Quiz.db_conn()
        try:
            row = conn.execute("SELECT id FROM questions WHERE question_number = 5").fetchone()
        finally:
            conn.close()

        self.assertIsNone(row)
        self.assertEqual(Quiz.DELETED_SEED_QUESTION_NUMBERS, [5])
        self.assertIn("DELETED_SEED_QUESTION_NUMBERS = [5]", self.source_path.read_text(encoding="utf-8"))

    def test_admin_can_open_and_save_question_edit(self):
        self.make_admin()
        self.assertEqual(self.client.get("/admin/edit-question/1").status_code, 200)

        response = self.client.post("/admin/edit-question/1", data={
            "text": "Edited question?", "question_type": "choice",
            "op1": "Yes", "op2": "No", "op3": "", "op4": "",
        })
        self.assertEqual(response.status_code, 302)

        conn = Quiz.db_conn()
        try:
            row = conn.execute("SELECT text, is_open_text, op1, op2 FROM questions WHERE id = 1").fetchone()
        finally:
            conn.close()
        self.assertEqual(tuple(row), ("Edited question?", 0, "Yes", "No"))

    def test_admin_can_open_suggestion_edit(self):
        self.make_admin()
        conn = Quiz.db_conn()
        try:
            suggestion_id = conn.execute("INSERT INTO suggestions (text, created_at) VALUES ('Idea?', ?)", (Quiz.now(),)).lastrowid
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self.client.get(f"/admin/edit-suggestion/{suggestion_id}").status_code, 200)

    def test_tv_shows_dopewars_scores(self):
        self.set_dopewars_pin(pin="tv01")
        self.client.post("/games/dopewars", data={"action": "quit"})
        self.assertEqual(self.client.get("/tv").status_code, 200)
        state = self.client.get("/tv/state").get_json()
        self.assertEqual(state["mode"], "scores")
        self.assertEqual(state["boards"][0]["rows"][0]["name"], "tv01")
        self.assertEqual(state["boards"][1]["rows"][0], {"name": "tv01", "score": 1})

    TINY_JPEG = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ=="

    def drawing_player(self, name):
        client = Quiz.app.test_client()
        client.post("/login", data={"name": name, "pin": "1234"})
        client.post("/games/drawing/join")
        return client

    def test_drawing_round_prep_draw_vote_and_points(self):
        clock = [1000.0]
        with patch.object(Quiz, "clock", lambda: clock[0]):
            self.assertEqual(self.client.get("/games/drawing").status_code, 200)
            alice = self.drawing_player("Alice")
            bob = self.drawing_player("Bob")
            alice.post("/games/drawing/start")
            state = alice.get("/games/drawing/state").get_json()
            self.assertEqual((state["phase"], state["seconds_left"], state["in_round"]), ("prep", 10, True))
            self.assertEqual(self.client.get("/tv/state").get_json()["mode"], "drawing")
            self.assertEqual(alice.post("/games/drawing/submit", data={"image": self.TINY_JPEG}).status_code, 409)

            clock[0] += 10
            state = alice.get("/games/drawing/state").get_json()
            self.assertEqual((state["phase"], state["seconds_left"]), ("drawing", 90))
            self.assertIn("pad", alice.get("/games/drawing").get_data(as_text=True))
            carol = self.drawing_player("Carol")
            self.assertFalse(carol.get("/games/drawing/state").get_json()["in_round"])
            self.assertIn("next round", carol.get("/games/drawing").get_data(as_text=True))
            self.assertEqual(alice.post("/games/drawing/submit", data={"image": "nope"}).status_code, 400)
            self.assertEqual(alice.post("/games/drawing/submit", data={"image": self.TINY_JPEG}).status_code, 200)
            self.assertEqual(bob.post("/games/drawing/submit", data={"image": self.TINY_JPEG}).status_code, 200)

            state = self.client.get("/tv/state").get_json()
            self.assertEqual((state["phase"], [d["number"] for d in state["drawings"]]), ("voting", [1, 2]))
            image = self.client.get(f"/games/drawing/image/{state['drawings'][0]['entry_id']}")
            self.assertEqual((image.status_code, image.mimetype), (200, "image/jpeg"))
            alice.post("/games/drawing/vote", data={"number": "1"})
            self.assertIsNone(alice.get("/games/drawing/state").get_json()["my_vote"])
            alice.post("/games/drawing/vote", data={"number": "2"})
            bob.post("/games/drawing/vote", data={"number": "1"})
            carol.post("/games/drawing/vote", data={"number": "2"})

            state = self.client.get("/tv/state").get_json()
            self.assertEqual((state["phase"], [(w["name"], w["votes"]) for w in state["winners"]]), ("results", [("Bob", 2)]))
            self.assertEqual(state["standings"][0], {"name": "Bob", "points": 1})
            clock[0] += Quiz.DRAWING_RESULTS_SECONDS
            state = self.client.get("/tv/state").get_json()
            self.assertEqual(state["mode"], "scores")
            board = next(b for b in state["boards"] if b["title"].startswith("Drawing"))
            self.assertEqual(board["rows"][0], {"name": "Bob", "score": 1})

            self.drawing_player("Dave")
            board = next(b for b in self.client.get("/tv/state").get_json()["boards"] if b["title"].startswith("Drawing"))
            self.assertEqual({row["score"] for row in board["rows"]}, {0})

    def test_drawing_vote_closes_after_timer(self):
        clock = [1000.0]
        with patch.object(Quiz, "clock", lambda: clock[0]):
            alice = self.drawing_player("Alice")
            self.drawing_player("Bob")
            alice.post("/games/drawing/start")
            clock[0] += Quiz.DRAWING_PREP_SECONDS
            alice.post("/games/drawing/submit", data={"image": self.TINY_JPEG})
            clock[0] += Quiz.DRAWING_SECONDS + Quiz.DRAWING_SUBMIT_GRACE_SECONDS
            state = self.client.get("/tv/state").get_json()
            self.assertEqual((state["phase"], len(state["drawings"])), ("voting", 1))
            clock[0] += Quiz.DRAWING_VOTE_SECONDS
            state = self.client.get("/tv/state").get_json()
            self.assertEqual((state["phase"], state["winners"]), ("results", []))

    def test_drawing_needs_sign_in_and_admin_can_end_round(self):
        self.assertIn("/login", self.client.post("/games/drawing/join").headers["Location"])
        alice = self.drawing_player("Alice")
        alice.post("/games/drawing/start")
        self.assertEqual(self.client.get("/tv/state").get_json()["mode"], "drawing")
        self.make_admin()
        self.client.post("/admin/drawing/end")
        self.assertEqual(self.client.get("/tv/state").get_json()["mode"], "scores")

    def test_games_page_lists_dopewars_link(self):
        response = self.client.get("/games", follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cotton Flat Bar Quiz", body)
        self.assertIn("/games/dopewars", body)
        self.assertIn("High Scores", body)

    def test_gold_users_page_lists_participants_without_double_counting_tokens(self):
        leaderboard_client = Quiz.app.test_client()
        leaderboard_client.post("/login", data={"name": "gold20", "pin": "gold20", "next": "/quiz"}, follow_redirects=True)
        self.answer_questions(leaderboard_client, 0, 20)

        second_client = Quiz.app.test_client()
        second_client.post("/login", data={"name": "gold40", "pin": "gold40", "next": "/quiz"}, follow_redirects=True)
        self.answer_questions(second_client, 0, 40)

        response = self.client.get("/gold-users")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Gold Users", body)
        self.assertIn("gold20", body)
        self.assertIn("gold40", body)
        self.assertIn("<td>1</td><td>gold40</td><td>40</td><td>2</td><td>0</td><td>2</td><td>0/20</td>", body)
        self.assertIn("<td>2</td><td>gold20</td><td>20</td><td>1</td><td>0</td><td>1</td><td>0/20</td>", body)

    def test_admin_page_shows_token_counts_without_join_multiplication(self):
        client = Quiz.app.test_client()
        client.post("/login", data={"name": "admin20", "pin": "admin20", "next": "/quiz"}, follow_redirects=True)
        self.answer_questions(client, 0, 20)

        self.make_admin()
        response = self.client.get("/admin")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("<td>admin20</td><td>20</td><td>1</td><td>0</td><td>0/20</td>", body)

    def test_dopewars_new_game_initializes_starting_stats(self):
        self.set_dopewars_pin()
        response = self.client.get("/games/dopewars")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Back to Menu", body)
        self.assertIn("/games/dopewars/reset", body)

        with self.client.session_transaction() as session:
            state = session["dopewars_state"]

        self.assertEqual(state["cash"], 2000)
        self.assertEqual(state["debt"], 5500)
        self.assertEqual(state["day"], 1)
        self.assertEqual(state["capacity"], 100)

    def test_dopewars_buy_and_sell_updates_cash_inventory_and_capacity(self):
        self.set_dopewars_pin()
        with self.client.session_transaction() as session:
            session["dopewars_state"] = {
                "day": 1,
                "cash": 20000,
                "debt": 5500,
                "bank": 0,
                "capacity": 100,
                "location": "Bronx",
                "inventory": {drug: 0 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "prices": {drug: 100 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "message": "",
                "game_over": False,
            }

        buy_response = self.client.post("/games/dopewars", data={"action": "buy", "drug": "Weed", "quantity": "150"})
        self.assertEqual(buy_response.status_code, 200)

        with self.client.session_transaction() as session:
            state = session["dopewars_state"]
            self.assertEqual(state["inventory"]["Weed"], 100)
            self.assertEqual(state["cash"], 10000)

        sell_response = self.client.post("/games/dopewars", data={"action": "sell", "drug": "Weed", "quantity": "40"})
        self.assertEqual(sell_response.status_code, 200)

        with self.client.session_transaction() as session:
            state = session["dopewars_state"]
            self.assertEqual(state["inventory"]["Weed"], 60)
            self.assertEqual(state["cash"], 14000)

    def test_dopewars_travel_advances_day_and_interest(self):
        self.set_dopewars_pin()
        with self.client.session_transaction() as session:
            session["dopewars_state"] = {
                "day": 1,
                "cash": 2000,
                "debt": 5500,
                "bank": 0,
                "capacity": 100,
                "location": "Bronx",
                "inventory": {drug: 0 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "prices": {drug: 100 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "message": "",
                "game_over": False,
            }

        with patch("Quiz.random.random", return_value=0.99):
            response = self.client.post("/games/dopewars", data={"action": "travel", "location": "Brooklyn"})

        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            state = session["dopewars_state"]
            self.assertEqual(state["day"], 2)
            self.assertEqual(state["debt"], 6050)

    def test_dopewars_ends_on_day_30_with_final_score(self):
        self.set_dopewars_pin()
        with self.client.session_transaction() as session:
            session["dopewars_state"] = {
                "day": 29,
                "cash": 3000,
                "debt": 1000,
                "bank": 500,
                "capacity": 100,
                "location": "Bronx",
                "inventory": {drug: 0 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "prices": {drug: 100 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "message": "",
                "game_over": False,
            }

        with patch("Quiz.random.random", return_value=0.99):
            response = self.client.post("/games/dopewars", data={"action": "travel", "location": "Manhattan"})

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Final score:", body)
        self.assertIn("Day 30 reached.", body)
        with self.client.session_transaction() as session:
            self.assertTrue(session["dopewars_state"]["game_over"])

    def test_dopewars_reset_restores_initial_state(self):
        self.set_dopewars_pin()
        with self.client.session_transaction() as session:
            session["dopewars_state"] = {
                "day": 10,
                "cash": 999,
                "debt": 1,
                "bank": 5000,
                "capacity": 100,
                "location": "Manhattan",
                "inventory": {drug: 5 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "prices": {drug: 100 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "message": "changed",
                "game_over": True,
            }

        response = self.client.post("/games/dopewars/reset", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as session:
            state = session["dopewars_state"]
            self.assertEqual(state["day"], 1)
            self.assertEqual(state["cash"], 2000)
            self.assertEqual(state["debt"], 5500)
            self.assertEqual(sum(state["inventory"].values()), 0)
            self.assertFalse(state["game_over"])

    def test_dopewars_requires_pin_before_play(self):
        response = self.client.get("/games/dopewars", follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Who's playing?", body)
        self.assertIn("name='next' value='/games/dopewars'", body)

    def test_dopewars_quit_saves_best_score_and_reset_does_not_overwrite(self):
        self.set_dopewars_pin(pin="score1")
        with self.client.session_transaction() as session:
            session["dopewars_state"] = {
                "day": 5,
                "cash": 9000,
                "debt": 1000,
                "bank": 2000,
                "capacity": 100,
                "location": "Bronx",
                "inventory": {drug: 0 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "prices": {drug: 100 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "message": "",
                "game_over": False,
            }
        self.client.post("/games/dopewars", data={"action": "quit"}, follow_redirects=True)
        self.assertEqual(self.dopewars_top_score("score1"), 10000)

        self.client.post("/games/dopewars/reset", follow_redirects=True)
        with self.client.session_transaction() as session:
            session["dopewars_state"] = {
                "day": 5,
                "cash": 1200,
                "debt": 2000,
                "bank": 0,
                "capacity": 100,
                "location": "Bronx",
                "inventory": {drug: 0 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "prices": {drug: 100 for drug in Quiz.DOPEWARS_PRICE_RANGES},
                "message": "",
                "game_over": False,
            }
        self.client.post("/games/dopewars", data={"action": "quit"}, follow_redirects=True)
        self.assertEqual(self.dopewars_top_score("score1"), 10000)

        menu = self.client.get("/").get_data(as_text=True)
        self.assertIn("score1", menu)
        self.assertIn("$10000", menu)

    def test_captive_probe_redirects_until_phone_opens_a_page(self):
        Quiz.signed_in_clients.clear()
        probe = self.client.get("/generate_204", headers={"Host": "connectivitycheck.gstatic.com"})
        self.assertEqual((probe.status_code, probe.headers["Location"]), (302, "http://192.168.4.1/"))
        apple = self.client.get("/hotspot-detect.html", headers={"Host": "captive.apple.com"})
        self.assertEqual(apple.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/generate_204", headers={"Host": "connectivitycheck.gstatic.com"}).status_code, 302)

        self.client.get("/answers")
        self.assertEqual(self.client.get("/generate_204", headers={"Host": "connectivitycheck.gstatic.com"}).status_code, 204)
        self.assertIn("Success", self.client.get("/hotspot-detect.html", headers={"Host": "captive.apple.com"}).get_data(as_text=True))
        self.assertEqual(self.client.get("/anything", headers={"Host": "example.com"}).status_code, 302)
        Quiz.signed_in_clients.clear()
    def test_name_login_is_protected_by_pin_and_hides_pin(self):
        owner = Quiz.app.test_client()
        response = owner.post("/login", data={"name": "Big Dan", "pin": "4321", "next": "/"}, follow_redirects=True)
        body = response.get_data(as_text=True)
        self.assertIn("Playing as <strong>Big Dan</strong>", body)
        self.assertNotIn("4321", body)

        thief = Quiz.app.test_client()
        response = thief.post("/login", data={"name": "big dan", "pin": "9999", "next": "/quiz"})
        self.assertIn("PIN doesn&#x27;t match", response.get_data(as_text=True))
        self.assertEqual(thief.get("/quiz").status_code, 302)

        again = Quiz.app.test_client()
        again.post("/login", data={"name": "BIG DAN", "pin": "4321"})
        with closing(Quiz.db_conn()) as conn:
            rows = conn.execute("SELECT name, pin, login_count FROM participants").fetchall()
        self.assertEqual([(row["name"], row["login_count"]) for row in rows], [("Big Dan", 2)])
        self.assertNotIn("4321", rows[0]["pin"])
        self.assertEqual(self.client.get("/tv/state").get_json()["boards"][1]["rows"], [{"name": "Big Dan", "score": 2}])

    def test_old_pin_profile_is_claimed_by_first_name_login(self):
        with closing(Quiz.db_conn()) as conn:
            old_id = conn.execute("INSERT INTO participants (pin, created_at, last_seen_at) VALUES ('OLD123', 'x', 'x')").lastrowid
            conn.execute("INSERT INTO drink_tokens (participant_id, milestone, created_at) VALUES (?, 20, 'x')", (old_id,))
            conn.commit()
        self.assertIn("Player", self.client.get("/gold-users").get_data(as_text=True))
        self.client.post("/login", data={"name": "Rosa", "pin": "old123"})
        with closing(Quiz.db_conn()) as conn:
            row = conn.execute("SELECT id, name FROM participants WHERE name_key = 'rosa'").fetchone()
        self.assertEqual((row["id"], row["name"]), (old_id, "Rosa"))
        self.assertNotIn("OLD123", self.client.get("/gold-users").get_data(as_text=True))
    def test_admin_can_play_as_host(self):
        self.make_admin()
        self.client.post("/admin/play-as-host")
        self.assertEqual(self.client.get("/quiz").status_code, 200)
        self.assertEqual(self.client.get("/games/dopewars").status_code, 200)
        self.client.post("/games/drawing/join")
        self.assertEqual(self.client.get("/games/drawing/state").get_json()["standings"], [{"name": "Host", "points": 0}])
        intruder = Quiz.app.test_client()
        self.assertIn("doesn&#x27;t match", intruder.post("/login", data={"name": "Host", "pin": "1234"}).get_data(as_text=True))

    def test_admin_edits_tv_screens(self):
        self.set_dopewars_pin(pin="hustle1")
        self.client.post("/games/dopewars", data={"action": "quit"})
        admin = Quiz.app.test_client()
        self.make_admin(admin)
        self.assertIn("TV Screens", admin.get("/admin").get_data(as_text=True))
        admin.post("/admin/tv/screen/dopewars", data={"title": "Top Hustlers", "enabled": "1"})
        admin.post("/admin/tv/screen/mvp", data={"title": "MVPs"})
        admin.post("/admin/tv/message", data={"title": "Tonight", "body": "$3 pints"})
        boards = self.client.get("/tv/state").get_json()["boards"]
        self.assertEqual([b["title"] for b in boards], ["Top Hustlers", "Drawing with Friends Scores", "Tonight"])
        self.assertEqual(boards[0]["rows"][0]["name"], "hustle1")

        with closing(Quiz.db_conn()) as conn:
            participant_id = conn.execute("SELECT id FROM participants WHERE name_key = 'hustle1'").fetchone()["id"]
        admin.post(f"/admin/rename/{participant_id}", data={"name": "Polite Name"})
        self.assertEqual(self.client.get("/tv/state").get_json()["boards"][0]["rows"][0]["name"], "Polite Name")
        admin.post(f"/admin/dopewars-score/{participant_id}/delete")
        self.assertEqual(self.client.get("/tv/state").get_json()["boards"][0]["rows"], [])
        admin.post(f"/admin/tv/message/{boards[2]['id']}/delete")
        admin.post("/admin/tv/clear/mvp")
        admin.post("/admin/tv/screen/mvp", data={"title": "MVPs", "enabled": "1"})
        boards = self.client.get("/tv/state").get_json()["boards"]
        self.assertEqual(([b["title"] for b in boards], boards[1]["rows"]), (["Top Hustlers", "MVPs", "Drawing with Friends Scores"], []))

    def prompt_rows(self):
        with closing(Quiz.db_conn()) as conn:
            return {row["text"]: row["id"] for row in conn.execute("SELECT id, text FROM drawing_prompts")}

    def test_admin_manages_drawing_prompts(self):
        prompts = self.prompt_rows()
        self.assertEqual(len(prompts), len(Quiz.DRAWING_PROMPTS))
        self.assertGreaterEqual(len(prompts), 90)
        self.assertIn("A horse ordering a drink", prompts)
        self.client.post("/admin/drawing/prompts", data={"text": "Sneaky"})
        self.assertNotIn("Sneaky", self.prompt_rows())
        self.make_admin()
        self.assertIn("A horse ordering a drink", self.client.get("/admin?tab=games").get_data(as_text=True))
        self.client.post("/admin/drawing/prompts", data={"text": "  A <b>moose</b>   at prom "})
        self.assertIn("A &lt;b&gt;moose&lt;/b&gt; at prom", self.client.get("/admin?tab=games").get_data(as_text=True))
        new_id = self.prompt_rows()["A <b>moose</b> at prom"]
        self.client.post(f"/admin/drawing/prompts/{new_id}", data={"text": "A moose at prom"})
        self.client.post(f"/admin/drawing/prompts/{prompts['A horse ordering a drink']}/delete")
        rows = self.prompt_rows()
        self.assertEqual((rows.get("A moose at prom"), "A horse ordering a drink" in rows), (new_id, False))
        Quiz.init_db()
        self.assertNotIn("A horse ordering a drink", self.prompt_rows())
        with closing(Quiz.db_conn()) as conn:
            conn.execute("DELETE FROM drawing_prompts WHERE text != 'A moose at prom'")
            conn.commit()
            self.assertEqual(Quiz.drawing_new_prompt(conn), "A moose at prom")

    def test_players_suggest_prompts_for_admin(self):
        self.assertIn("/login", self.client.post("/games/drawing/suggest", data={"text": "A dog"}).headers["Location"])
        self.client.post("/login", data={"name": "Sketchy", "pin": "1234"})
        self.assertIn("Suggest a prompt", self.client.get("/games/drawing").get_data(as_text=True))
        self.client.post("/games/drawing/suggest", data={"text": "  A <i>moose</i>  bowling "})
        self.client.post("/games/drawing/suggest", data={"text": "a <i>MOOSE</i> bowling"})
        reply = self.client.post("/games/drawing/suggest", data={"text": "A goat DJ"}, follow_redirects=True)
        self.assertIn("waiting for the host", reply.get_data(as_text=True))
        self.client.post("/games/drawing/suggest", data={"text": "a horse ordering a drink"})
        with closing(Quiz.db_conn()) as conn:
            rows = {row["text"]: (row["id"], row["author"]) for row in conn.execute("SELECT * FROM drawing_prompt_suggestions")}
        self.assertEqual(sorted(rows), ["A <i>moose</i> bowling", "A goat DJ"])
        self.assertEqual(rows["A goat DJ"][1], "Sketchy")
        for n in range(3):
            self.client.post("/games/drawing/suggest", data={"text": f"Idea number {n}"})
        self.assertIn("Try again later", self.client.post("/games/drawing/suggest", data={"text": "One more"}, follow_redirects=True).get_data(as_text=True))
        self.client.post(f"/admin/drawing/suggestions/{rows['A goat DJ'][0]}/approve", data={"text": "Sneaky"})
        self.assertNotIn("Sneaky", self.prompt_rows())
        admin = self.make_admin(Quiz.app.test_client())
        page = admin.get("/admin?tab=games").get_data(as_text=True)
        self.assertIn("A &lt;i&gt;moose&lt;/i&gt; bowling", page)
        self.assertIn("from Sketchy", page)
        admin.post(f"/admin/drawing/suggestions/{rows['A <i>moose</i> bowling'][0]}/approve", data={"text": "A moose bowling"})
        admin.post(f"/admin/drawing/suggestions/{rows['A goat DJ'][0]}/delete")
        self.assertIn("A moose bowling", self.prompt_rows())
        self.assertNotIn("A goat DJ", self.prompt_rows())
        with closing(Quiz.db_conn()) as conn:
            left = [row["text"] for row in conn.execute("SELECT text FROM drawing_prompt_suggestions")]
        self.assertEqual(len(left), 3)

    def test_admin_gives_tokens_and_deletes_players(self):
        old = Quiz.app.test_client()
        old.post("/login", data={"name": "Forgetful", "pin": "1111"})
        self.client.post("/login", data={"name": "Forgetful Again", "pin": "2222"})
        with closing(Quiz.db_conn()) as conn:
            ids = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM participants")}
            conn.execute("INSERT INTO dopewars_scores (participant_id, top_score, achieved_at, updated_at) VALUES (?, 500, ?, ?)", (ids["Forgetful"], Quiz.now(), Quiz.now()))
            conn.execute("INSERT INTO drink_tokens (participant_id, milestone, created_at) VALUES (?, ?, ?)", (ids["Forgetful Again"], Quiz.TOKEN_MILESTONE, Quiz.now()))
            conn.commit()
        def ready(name):
            with closing(Quiz.db_conn()) as conn:
                return next(p["unredeemed"] for p in Quiz.participant_stats(conn) if p["name"] == name)
        self.client.post(f"/admin/players/{ids['Forgetful Again']}/tokens", data={"count": "3"})
        self.client.post(f"/admin/players/{ids['Forgetful']}/delete")
        self.assertEqual(ready("Forgetful Again"), 1)
        admin = self.make_admin(Quiz.app.test_client())
        self.assertIn("Give Tokens", admin.get("/admin?tab=players").get_data(as_text=True))
        admin.post(f"/admin/players/{ids['Forgetful Again']}/tokens", data={"count": "3"})
        admin.post(f"/admin/players/{ids['Forgetful Again']}/tokens", data={"count": "99"})
        self.assertEqual(ready("Forgetful Again"), 14)
        admin.get(f"/admin/redeem-token/{ids['Forgetful Again']}")
        self.assertEqual(ready("Forgetful Again"), 13)
        admin.post(f"/admin/players/{ids['Forgetful']}/delete")
        with closing(Quiz.db_conn()) as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM participants WHERE id = ?", (ids["Forgetful"],)).fetchone())
            self.assertIsNone(conn.execute("SELECT 1 FROM dopewars_scores WHERE participant_id = ?", (ids["Forgetful"],)).fetchone())
        self.assertNotIn("Forgetful<", admin.get("/admin?tab=players").get_data(as_text=True))
        self.assertIn("/login", old.post("/games/drawing/join").headers["Location"])

    def test_friend_and_venue_questions_are_added_once(self):
        def keyed(prefix):
            return [row for row in self.approved_questions() if (row["seed_key"] or "").startswith(prefix)]
        friends, venue = keyed("friends-"), keyed("venue-")
        self.assertEqual((len(friends), len(venue)), (50, 20))
        self.assertIn("What bands or artists would you love to see booked here?", [row["text"] for row in venue])
        for row in friends + venue:
            self.assertGreater(row["question_number"], 200)
            self.assertEqual(len(Quiz.options_for(row)), 0 if row["is_open_text"] else 4)
        Quiz.init_db()
        self.assertEqual(len(keyed("friends-")), 50)
        self.make_admin()
        self.client.post(f"/admin/delete-question-number/{friends[0]['question_number']}")
        self.client.post(f"/admin/delete-question/{venue[0]['id']}")
        Quiz.init_db()
        self.assertEqual((len(keyed("friends-")), len(keyed("venue-"))), (49, 19))

    def test_admin_tabs_split_the_page(self):
        self.assertNotIn("Quiz Questions", self.client.get("/admin?tab=questions").get_data(as_text=True))
        self.make_admin()
        home = self.client.get("/admin").get_data(as_text=True)
        self.assertIn("Players & Drink Tokens", home)
        self.assertNotIn("Edit</a>", home)
        total = len(self.approved_questions())
        first = self.client.get("/admin?tab=questions").get_data(as_text=True)
        self.assertIn(f"of {total}, newest first", first)
        self.assertEqual(first.count("/admin/edit-question/"), Quiz.ADMIN_QUESTIONS_PER_PAGE)
        last = self.client.get(f"/admin?tab=questions&p=999").get_data(as_text=True)
        self.assertIn("Previous", last)
        found = self.client.get("/admin?tab=questions&q=bands or artists").get_data(as_text=True)
        self.assertIn("Showing 1-1 of 1", found)
        for tab in ("submissions", "tv", "games", "bogus"):
            self.assertEqual(self.client.get(f"/admin?tab={tab}").status_code, 200)
        reply = self.client.post("/admin/drawing/prompts", data={"text": "Tab check"})
        self.assertTrue(reply.headers["Location"].endswith("/admin?tab=games"))

    def test_ad_upload_approval_and_expiry(self):
        png = bytes.fromhex("89504e470d0a1a0a") + b"0" * 32
        def upload(client, name, plan, data, filename="ad.png"):
            fields = {"business": name, "message": "Tacos $2", "contact": "Sam 555", "plan": plan, "image": (io.BytesIO(data), filename)}
            return client.post("/advertise", data=fields, content_type="multipart/form-data").get_data(as_text=True)
        form = self.client.get("/advertise").get_data(as_text=True)
        for text in ("$Drob432", "$25", "$5", "2 months", "1 week"):
            self.assertIn(text, form)
        self.assertIn("Only PNG", upload(self.client, "Bad", "company", b"<script>alert(1)</script>", "x.png"))
        self.assertIn("over 3 MB", upload(self.client, "Big", "company", png + b"0" * Quiz.AD_MAX_BYTES))
        clock = [1000.0]
        with patch.object(Quiz, "clock", lambda: clock[0]):
            self.assertIn("Got it", upload(self.client, "Taco Shack", "company", png))
            upload(self.client, "Happy Birthday Sam", "shoutout", png)
            with closing(Quiz.db_conn()) as conn:
                ids = {row["business"]: row["id"] for row in conn.execute("SELECT id, business FROM ads")}
            self.assertEqual(sorted(ids), ["Happy Birthday Sam", "Taco Shack"])
            def ad_titles():
                return [b["title"] for b in self.client.get("/tv/state").get_json()["boards"] if "ad" in b]
            self.assertEqual(ad_titles(), [])
            self.assertEqual(self.client.get(f"/ads/{ids['Taco Shack']}/image").status_code, 404)
            self.client.post(f"/admin/ads/{ids['Taco Shack']}/approve")
            self.assertEqual(ad_titles(), [])
            admin = Quiz.app.test_client()
            self.make_admin(admin)
            self.assertIn("Taco Shack", admin.get("/admin?tab=tv").get_data(as_text=True))
            self.assertEqual(admin.get(f"/ads/{ids['Taco Shack']}/image").status_code, 200)
            for name in ("Taco Shack", "Happy Birthday Sam"):
                admin.post(f"/admin/ads/{ids[name]}/approve")
            self.assertEqual(ad_titles(), ["Taco Shack", "Happy Birthday Sam"])
            image = self.client.get(f"/ads/{ids['Taco Shack']}/image")
            self.assertEqual((image.mimetype, image.headers["X-Content-Type-Options"]), ("image/png", "nosniff"))
            clock[0] += 8 * 86400
            self.assertEqual(ad_titles(), ["Taco Shack"])
            clock[0] += 53 * 86400
            self.assertEqual(ad_titles(), [])
            self.assertEqual(self.client.get(f"/ads/{ids['Taco Shack']}/image").status_code, 404)
            self.assertIn("Renew", admin.get("/admin?tab=tv").get_data(as_text=True))
            admin.post(f"/admin/ads/{ids['Taco Shack']}/delete")
            with closing(Quiz.db_conn()) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
