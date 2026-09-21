import os
import tempfile
import unittest
from pathlib import Path


TEST_DB_DIR = tempfile.TemporaryDirectory()
os.environ.setdefault("COTTON_FLAT_DB_PATH", str(Path(TEST_DB_DIR.name) / "import.db"))

import Quiz


class QuizProgressTestCase(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(TEST_DB_DIR.name) / f"{self._testMethodName}.db"
        if self.db_path.exists():
            self.db_path.unlink()
        Quiz.DB_PATH = str(self.db_path)
        Quiz.app.config["TESTING"] = True
        Quiz.init_db()
        self.client = Quiz.app.test_client()

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

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

        self.assertIn("You've already answered every available question.", body)
        self.assertNotIn(only_question, body)


if __name__ == "__main__":
    unittest.main()
