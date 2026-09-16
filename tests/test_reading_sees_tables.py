"""The tables an extraction read, reaching the reader and the check that holds it to account.

`signals.read_text` is the one place three passes take their text from: the shortlist that scores a
candidate, the task a sub agent is given, and the haystack every quoted value is checked against. Tables
are appended there rather than anywhere else, so a row quoted off a table is checked against the table it
was quoted from. Appending them to the task alone would fail correct rows as unverifiable.
"""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/extract-composition-from-documents/lib"
sys.path.insert(0, str(LIB))

import signals  # noqa: E402
import verbatim  # noqa: E402

CONVERSION = "SAFETY DATA SHEET\nSECTION 3 Composition\nsee table below\n"
TABLES = "## Tables on page 2\n\n| INCI name | % |\n| --- | --- |\n| Aqua/water | balance |\n"


class TablesReachTheReader(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.body = self.dir / "doc.md"
        self.body.write_text(CONVERSION, encoding="utf-8")
        self.tables = self.dir / "doc.tables.md"
        self.tables.write_text(TABLES, encoding="utf-8")

    def record(self, **over):
        base = {"fullTextFile": str(self.body), "tablesFile": str(self.tables)}
        base.update(over)
        return base

    def test_the_conversion_comes_first_and_the_tables_after(self):
        text = signals.read_text(self.record())
        self.assertLess(text.index("SECTION 3"), text.index("Aqua/water"))

    def test_the_tables_are_labelled_as_tables(self):
        self.assertIn("# Tables read from this document", signals.read_text(self.record()))

    def test_a_document_with_no_tables_is_unchanged(self):
        self.assertEqual(signals.read_text(self.record(tablesFile=None)), CONVERSION)

    def test_a_tables_path_that_is_not_there_is_ignored(self):
        self.assertEqual(signals.read_text(self.record(tablesFile=str(self.dir / "gone.md"))), CONVERSION)

    def test_an_empty_tables_file_adds_no_heading(self):
        self.tables.write_text("   \n", encoding="utf-8")
        self.assertNotIn("# Tables read", signals.read_text(self.record()))

    def test_tables_alone_are_still_given_to_a_reader(self):
        self.body.write_text("", encoding="utf-8")
        text = signals.read_text(self.record())
        self.assertIn("Aqua/water", text)
        self.assertNotIn("# Tables read from this document", text)


class AQuoteOffATableSurvivesItsCheck(unittest.TestCase):
    """The trap this placement avoids: a correct row rejected because the check looked elsewhere."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        body = self.dir / "doc.md"
        body.write_text(CONVERSION, encoding="utf-8")
        tables = self.dir / "doc.tables.md"
        tables.write_text(TABLES, encoding="utf-8")
        self.record = {"fullTextFile": str(body), "tablesFile": str(tables)}

    def test_a_value_only_the_table_states_is_in_the_haystack(self):
        haystack = signals.read_text(self.record)
        self.assertIn("Aqua/water", haystack)
        self.assertIn("balance", haystack)

    def test_the_conversion_alone_would_not_have_held_it(self):
        self.assertNotIn("Aqua/water", CONVERSION)


if __name__ == "__main__":
    unittest.main()
