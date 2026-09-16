"""Where the window goes when the document titles nothing.

A composition is not always under a heading the scoring recognises. OCR mangles one, a supplier prints
the table under their own logo, a scanned statement has no text at all above its columns. On 678 long
documents carrying composition words, 130 named no heading that scored.

The old fallback took the head and the tail, which is the one cut guaranteed to miss a table in the
middle of a document - the exact failure the window exists to avoid. The numbers are still there when
the words are not, so the fallback follows them.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/extract-composition-from-documents/lib"
sys.path.insert(0, str(LIB))

import plan_readings  # noqa: E402

TABLE = (
    "| Aqua | 7732-18-5 | 68.0 % |\n"
    "| Glycerin | 56-81-5 | 20.0 % |\n"
    "| Sodium chloride | 7647-14-5 | 11.5 % |\n"
    "| Citric acid | 77-92-9 | 0.5 % |\n"
)
PROSE = "This product is supplied in drums and stored away from sunlight.\n"


class ATableWithNoHeadingOverIt(unittest.TestCase):
    def setUp(self):
        self.buried = (PROSE * 120) + TABLE + (PROSE * 120)
        self.assertGreater(len(self.buried), 3500)

    def test_the_window_reaches_a_table_in_the_middle(self):
        sliced = plan_readings.window(self.buried, 3500)
        self.assertIn("7732-18-5", sliced)
        self.assertIn("Glycerin", sliced)

    def test_the_head_and_tail_slice_is_not_used_when_numbers_are_found(self):
        self.assertNotIn("[...]", plan_readings.window(self.buried, 3500))

    def test_a_document_with_no_numbers_at_all_still_gets_head_and_tail(self):
        """Nothing to follow, so the old behaviour stands rather than an arbitrary slice."""
        sliced = plan_readings.window(PROSE * 300, 3500)
        self.assertIn("[...]", sliced)

    def test_a_heading_still_wins_over_density(self):
        """A real heading is better evidence than a dense patch, and is tried first."""
        text = (PROSE * 60) + "Composition breakdown\n" + TABLE + (PROSE * 60) + ("99-99-9 12.0 % " * 400)
        sliced = plan_readings.window(text, 3500)
        self.assertIn("Composition breakdown", sliced)


class TheDensestPatch(unittest.TestCase):
    def test_it_is_the_offset_of_the_richest_run(self):
        text = (PROSE * 200) + TABLE
        start = plan_readings.densest(text, 3500)
        self.assertIsNotNone(start)
        self.assertIn("7732-18-5", text[start:start + 3500])

    def test_text_with_nothing_to_find_returns_nothing(self):
        self.assertIsNone(plan_readings.densest(PROSE * 300, 3500))


if __name__ == "__main__":
    unittest.main()
