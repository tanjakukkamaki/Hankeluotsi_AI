from pathlib import Path
from unittest import TestCase

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class AppShellTests(TestCase):
    def test_shell_renders_title_and_funding_disclaimer(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual([element.value for element in app.title], ["HankeLuotsi AI"])
        self.assertTrue(
            any("Not a funding eligibility assessment" in element.value for element in app.markdown)
        )
