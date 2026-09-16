"""The tables a composition is printed in, and what has to survive being turned into Markdown.

MarkItDown and pdfplumber find different tables: over 150 pages carrying composition signals, pdfplumber
produced one on 92 and MarkItDown on 61, agreeing on 38. So these are written beside the conversion
rather than instead of it, and these are the shapes that must come through intact — long INCI names and
two-row sheets included, because a reader that drops those drops the composition.
"""

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/extract-document-text/lib"
sys.path.insert(0, str(LIB))

import tables  # noqa: E402


class LongCellsSurvive(unittest.TestCase):
    """A column of INCI names is the normal case, not prose to be filtered out."""

    def test_a_column_of_inci_names_still_renders(self):
        rows = [
            ["INCI name", "CAS", "%"],
            ["Hydrogenated Polyisobutene (and) Ethylhexyl Palmitate", "61693-08-1", "45.0"],
            ["Tetrasodium Glutamate Diacetate", "51981-21-6", "5.0"],
        ]
        out = tables.as_markdown(rows)
        self.assertIn("Hydrogenated Polyisobutene (and) Ethylhexyl Palmitate", out)
        self.assertEqual(out.count("\n"), 3)
        self.assertTrue(tables.worth_keeping(rows))

    def test_every_cell_long_is_still_a_table(self):
        rows = [
            ["Ingredient as the supplier prints it", "Function it performs in the formulation"],
            ["Hydrogenated Polyisobutene (and) Ethylhexyl Palmitate", "Emollient and occlusive agent"],
        ]
        self.assertTrue(tables.worth_keeping(rows))


class ShortTablesSurvive(unittest.TestCase):
    """Two rows is a header and an ingredient, which is a whole composition on some sheets."""

    def test_two_rows_is_enough(self):
        rows = [["INCI name", "%"], ["Aqua", "Balance"]]
        self.assertTrue(tables.worth_keeping(rows))
        self.assertIn("| Aqua | Balance |", tables.as_markdown(rows))

    def test_one_row_is_not_a_table(self):
        self.assertFalse(tables.worth_keeping([["INCI name", "CAS", "%"]]))

    def test_a_single_column_is_not_a_table(self):
        self.assertFalse(tables.worth_keeping([["Aqua"], ["Glycerin"], ["Parfum"]]))

    def test_an_empty_table_is_not_a_table(self):
        self.assertFalse(tables.worth_keeping([]))
        self.assertFalse(tables.worth_keeping([[None, ""], ["", None]]))


class CellsAreMadeSafe(unittest.TestCase):
    def test_none_becomes_empty(self):
        out = tables.as_markdown([["INCI", "%"], [None, "5.0"]])
        self.assertIn("|  | 5.0 |", out)

    def test_a_pipe_in_a_cell_does_not_break_the_row(self):
        out = tables.as_markdown([["Name", "%"], ["Aqua | Water", "50"]])
        body = out.splitlines()[2]
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", body)[1:-1]]
        self.assertEqual(cells, [r"Aqua \| Water", "50"])

    def test_a_wrapped_cell_becomes_one_line(self):
        out = tables.as_markdown([["Name", "%"], ["Hydrogenated\nPolyisobutene", "45"]])
        self.assertIn("Hydrogenated Polyisobutene", out)
        self.assertEqual(len(out.splitlines()), 3)

    def test_ragged_rows_are_padded_to_the_widest(self):
        out = tables.as_markdown([["A", "B", "C"], ["1"], ["2", "3"]])
        for line in out.splitlines():
            self.assertEqual(line.count("|"), 4)


class ThePageSection(unittest.TestCase):
    """What gets appended to a document's Markdown, and what it says when there is nothing."""

    def test_nothing_found_writes_nothing(self):
        self.assertEqual(tables.render({}), ("", 0))
        self.assertEqual(tables.render({1: []}), ("", 0))

    def test_tables_are_headed_by_their_page(self):
        out, count = tables.render({3: [[["INCI", "%"], ["Aqua", "Balance"]]]})
        self.assertIn("## Tables on page 3", out)
        self.assertIn("| Aqua | Balance |", out)
        self.assertEqual(count, 1)

    def test_pages_come_out_in_order(self):
        out, _ = tables.render({
            7: [[["B", "%"], ["x", "1"]]],
            2: [[["A", "%"], ["y", "2"]]],
        })
        self.assertLess(out.index("page 2"), out.index("page 7"))

    def test_a_page_with_two_tables_keeps_both(self):
        out, count = tables.render({1: [
            [["A", "%"], ["x", "1"]],
            [["B", "%"], ["y", "2"]],
        ]})
        self.assertIn("| x | 1 |", out)
        self.assertIn("| y | 2 |", out)
        self.assertEqual(count, 2)

    def test_worthless_tables_are_dropped_from_the_section(self):
        out, count = tables.render({1: [[["only one row"]], [["A", "%"], ["x", "1"]]]})
        self.assertNotIn("only one row", out)
        self.assertIn("| x | 1 |", out)
        self.assertEqual(count, 1)


class CountingWhatWasWritten(unittest.TestCase):
    """A re-run recovers the count from the file it wrote last time, so the two must agree."""

    def test_the_count_matches_what_render_reported(self):
        out, count = tables.render({1: [[["A", "%"], ["x", "1"]]], 2: [[["B", "%"], ["y", "2"]]]})
        self.assertEqual(tables.count_in(out), count)

    def test_nothing_counts_as_nothing(self):
        self.assertEqual(tables.count_in(""), 0)
        self.assertEqual(tables.count_in(None), 0)

    def test_a_cell_of_dashes_is_not_miscounted_as_a_table(self):
        out, count = tables.render({1: [[["Name", "%"], ["--- not a separator", "1"]]]})
        self.assertEqual(count, 1)
        self.assertEqual(tables.count_in(out), 1)


if __name__ == "__main__":
    unittest.main()
