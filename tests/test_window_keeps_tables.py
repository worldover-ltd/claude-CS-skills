"""The slice a sub agent is given, and why the tables cannot be inside the text it is cut from.

`plan_readings` does not hand a reader the whole document. It cuts a window around wherever the
composition looks to be, anchored on a heading. Tables are appended at the end of the text, so a window
taken on the joined text lands nowhere near them on any document long enough to need windowing — and the
tables would still reach the shortlist that scores the candidate and the haystack its quotes are checked
against. A candidate promoted on evidence the reader is never shown is worse than one never promoted.

So the body is windowed, and the tables are joined on afterwards.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/extract-composition-from-documents/lib"
sys.path.insert(0, str(LIB))

import plan_readings  # noqa: E402
import signals  # noqa: E402

TABLES = "## Tables on page 2\n\n| INCI name | % |\n| --- | --- |\n| Aqua/water | balance |\n"
LONG_BODY = "SECTION 3 Composition\n" + ("filler line\n" * 4000)


class TheSliceCarriesTheTables(unittest.TestCase):
    def test_a_window_of_a_long_document_still_ends_with_its_tables(self):
        sliced = signals.join(plan_readings.window(LONG_BODY, 3500), TABLES)
        self.assertIn("Aqua/water", sliced)
        self.assertIn("# Tables read from this document", sliced)

    def test_windowing_the_join_kept_them_only_by_luck(self):
        """Where a heading anchors the window mid-document, the tail — and the tables — is cut away.

        `window` keeps the tail when it finds no heading worth anchoring on, which is why joining first
        appeared to work on some documents. It is not a guarantee, and a reader that sees the tables on
        one document and not the next is worse than one that never sees them.
        """
        buried = ("filler line\n" * 2000) + "SECTION 3 Composition\n47.5 %\n" + ("filler line\n" * 2000)
        joined_then_sliced = plan_readings.window(signals.join(buried, TABLES), 3500)
        self.assertNotIn("Aqua/water", joined_then_sliced)
        self.assertIn("Aqua/water", signals.join(plan_readings.window(buried, 3500), TABLES))

    def test_a_short_document_keeps_all_of_its_body(self):
        body = "SECTION 3 Composition\nshort and complete\n"
        sliced = signals.join(plan_readings.window(body, 3500), TABLES)
        self.assertIn("short and complete", sliced)
        self.assertIn("Aqua/water", sliced)

    def test_tables_do_not_push_a_body_over_the_cap(self):
        body = "SECTION 3 Composition\n" + ("x" * 3000)
        self.assertEqual(plan_readings.window(body, 3500), body)

    def test_a_document_with_no_tables_is_the_window_alone(self):
        self.assertEqual(signals.join(plan_readings.window(LONG_BODY, 3500), ""),
                         plan_readings.window(LONG_BODY, 3500))


if __name__ == "__main__":
    unittest.main()
