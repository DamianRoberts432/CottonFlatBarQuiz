import os
import tempfile
import unittest
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
                   WHERE p.pin = ?""",
                (pin,),
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
                   WHERE p.pin = ?
                   ORDER BY dt.milestone ASC""",
                (pin,),
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
        with client.session_transaction() as session:
            session["participant_pin"] = pin.upper()
        return client

    def dopewars_top_score(self, pin):
        conn = Quiz.db_conn()
        try:
            row = conn.execute(
                """SELECT ds.top_score
                   FROM dopewars_scores ds
                   JOIN participants p ON p.id = ds.participant_id
                   WHERE p.pin = ?""",
                (pin.upper(),),
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def test_new_pin_starts_from_first_question(self):
        first_question = self.approved_questions()[0]["text"]

        response = self.client.post("/quiz", data={"pin": "alpha1"}, follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Question 1 of", body)
        self.assertIn(first_question, body)

    def test_returning_pin_resumes_at_first_unanswered_question(self):
        questions = self.approved_questions()
        first_question = questions[0]["text"]
        second_question = questions[1]["text"]

        first_client = Quiz.app.test_client()
        first_client.post("/quiz", data={"pin": "resume1"}, follow_redirects=True)
        response = self.answer_question(first_client, 0)
        body = response.get_data(as_text=True)

        self.assertIn(second_question, body)
        self.assertNotIn(first_question, body)
        self.assertEqual(self.answered_count("RESUME1"), 1)

        returning_client = Quiz.app.test_client()
        response = returning_client.post("/quiz", data={"pin": "resume1"}, follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertIn(second_question, body)
        self.assertNotIn(first_question, body)

    def test_different_pins_keep_independent_progress(self):
        questions = self.approved_questions()
        first_question = questions[0]["text"]
        second_question = questions[1]["text"]

        first_client = Quiz.app.test_client()
        first_client.post("/quiz", data={"pin": "alpha2"}, follow_redirects=True)
        self.answer_question(first_client, 0)

        second_client = Quiz.app.test_client()
        response = second_client.post("/quiz", data={"pin": "beta2"}, follow_redirects=True)
        self.assertIn(first_question, response.get_data(as_text=True))

        returning_client = Quiz.app.test_client()
        response = returning_client.post("/quiz", data={"pin": "alpha2"}, follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertIn(second_question, body)
        self.assertNotIn(first_question, body)

    def test_completed_pin_sees_completion_instead_of_repeat_question(self):
        self.trim_questions(1)
        only_question = self.approved_questions()[0]["text"]

        first_client = Quiz.app.test_client()
        first_client.post("/quiz", data={"pin": "done1"}, follow_redirects=True)
        response = self.answer_question(first_client, 0)
        body = response.get_data(as_text=True)

        self.assertIn("Your answer was saved.", body)
        self.assertNotIn(only_question, body)

        returning_client = Quiz.app.test_client()
        response = returning_client.post("/quiz", data={"pin": "done1"}, follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertIn("already answered every available question.", body)
        self.assertNotIn(only_question, body)

    def test_tokens_are_issued_every_20_answers(self):
        self.trim_questions(60)
        client = Quiz.app.test_client()
        client.post("/quiz", data={"pin": "token20"}, follow_redirects=True)

        self.answer_questions(client, 0, 20)
        self.assertEqual(self.token_milestones("TOKEN20"), [20])

        self.answer_questions(client, 20, 20)
        self.assertEqual(self.token_milestones("TOKEN20"), [20, 40])

        self.answer_questions(client, 40, 20)
        self.assertEqual(self.token_milestones("TOKEN20"), [20, 40, 60])

    def test_reanswering_question_does_not_duplicate_tokens(self):
        self.trim_questions(20)
        client = Quiz.app.test_client()
        client.post("/quiz", data={"pin": "nodupe1"}, follow_redirects=True)

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

    def test_games_page_lists_dopewars_link(self):
        response = self.client.get("/games", follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cotton Flat Bar Quiz", body)
        self.assertIn("/games/dopewars", body)
        self.assertIn("High Scores", body)

    def test_gold_users_page_lists_participants_without_double_counting_tokens(self):
        leaderboard_client = Quiz.app.test_client()
        leaderboard_client.post("/quiz", data={"pin": "gold20"}, follow_redirects=True)
        self.answer_questions(leaderboard_client, 0, 20)

        second_client = Quiz.app.test_client()
        second_client.post("/quiz", data={"pin": "gold40"}, follow_redirects=True)
        self.answer_questions(second_client, 0, 40)

        response = self.client.get("/gold-users")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Gold Users", body)
        self.assertIn("GOLD20", body)
        self.assertIn("GOLD40", body)
        self.assertIn("<td>1</td><td>GOLD40</td><td>40</td><td>2</td><td>0</td><td>2</td><td>0/20</td>", body)
        self.assertIn("<td>2</td><td>GOLD20</td><td>20</td><td>1</td><td>0</td><td>1</td><td>0/20</td>", body)

    def test_admin_page_shows_token_counts_without_join_multiplication(self):
        client = Quiz.app.test_client()
        client.post("/quiz", data={"pin": "admin20"}, follow_redirects=True)
        self.answer_questions(client, 0, 20)

        self.make_admin()
        response = self.client.get("/admin")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("<td>ADMIN20</td><td>20</td><td>1</td><td>0</td><td>0/20</td>", body)

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
        response = self.client.get("/games/dopewars")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Enter your PIN", body)
        self.assertIn("Play Dopewars", body)

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
        self.assertIn("SCORE1", menu)
        self.assertIn("$10000", menu)


if __name__ == "__main__":
    unittest.main()
