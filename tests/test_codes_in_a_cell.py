"""A CAS column that holds more than one number, and a number the conversion broke.

Both come off real documents and both used to fail the same way. `cas_ok` was asked of the whole cell,
so `5989-27-5 or 7705-14-8` failed its check digit - and a failed code blocks the entire material, not
the row. On one fragrance sheet that cost fourteen of eighteen rows and four re-reads.

The numbers are not a transcription error. A fragrance names the isomers it may contain and an INCI
covers several registry entries, so the document really does print three numbers against one name. What
the check has to ask is whether *every* number in the cell is well formed, not whether the cell is one.

Separately, a conversion splits a number across a space - `98-55- 5` - so `find` never sees it and the
reader is given a reference list with a hole in it.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/extract-composition-from-documents/lib"
sys.path.insert(0, str(LIB))

import codes  # noqa: E402


class OneCellManyNumbers(unittest.TestCase):
    """Straight off R110, R131, R107 and R158 of a real run."""

    def test_a_single_code_still_passes(self):
        self.assertTrue(codes.cell_ok("5989-27-5"))

    def test_two_separated_by_a_word(self):
        self.assertTrue(codes.cell_ok("5989-27-5 or 7705-14-8"))

    def test_three_separated_by_semicolons(self):
        self.assertTrue(codes.cell_ok("8000-41-7; 98-55-5; 138-87-4"))

    def test_separated_by_a_slash(self):
        self.assertTrue(codes.cell_ok("64742-60-5/92045-76-6"))

    def test_separated_by_spaces_alone(self):
        self.assertTrue(codes.cell_ok("138-86-3 5989-27-5 5989-54-8"))

    def test_a_mistyped_digit_anywhere_still_fails(self):
        """The whole point of the check digit, and loosening the cell must not lose it."""
        self.assertFalse(codes.cell_ok("5989-27-5 or 7705-14-9"))
        self.assertFalse(codes.cell_ok("8000-41-7; 98-55-4; 138-87-4"))

    def test_a_cell_with_no_code_in_it_fails(self):
        for cell in ("", "   ", "Exempt", "see section 3", "9 10 11"):
            self.assertFalse(codes.cell_ok(cell), cell)

    def test_words_around_the_numbers_are_ignored(self):
        self.assertTrue(codes.cell_ok("CAS-No.: 6440-58-0"))

    def test_the_numbers_come_back_in_order(self):
        self.assertEqual(codes.from_cell("138-86-3 5989-27-5 5989-54-8"),
                         ["138-86-3", "5989-27-5", "5989-54-8"])

    def test_an_ec_cell_works_the_same_way(self):
        self.assertTrue(codes.cell_ok("231-791-2; 269-919-4", kind="ec"))
        self.assertFalse(codes.cell_ok("231-791-2; 269-919-5", kind="ec"))


class ACodeOfTheOtherKindIsStillChecked(unittest.TestCase):
    """The two shapes cannot both match one run, which is why the column's own kind is not enough.

    A CAS cell reading `5989-27-5 / EC 231-791-2` puts two numbers on the workbook. Asking only about
    CAS numbers answers for the first and lets the second through unverified.
    """

    def test_both_kinds_come_back_from_one_cell(self):
        found = codes.everything_in("5989-27-5 / EC 231-791-2")
        self.assertEqual(sorted(found), [("cas", "5989-27-5"), ("ec", "231-791-2")])

    def test_a_bad_ec_number_in_a_cas_cell_fails_the_cell(self):
        self.assertFalse(codes.cell_ok("5989-27-5 / EC 231-791-3"))

    def test_a_good_ec_number_in_a_cas_cell_passes(self):
        self.assertTrue(codes.cell_ok("5989-27-5 / EC 231-791-2"))

    def test_a_cas_cell_still_needs_a_cas_number(self):
        """An EC number alone in the CAS column is the wrong number, not a well-formed cell."""
        self.assertFalse(codes.cell_ok("231-791-2"))


class ANumberTheConversionBroke(unittest.TestCase):
    """`8000-41-7; 98-55- 5; 138-87-4` is what MarkItDown wrote for one real row."""

    BROKEN = "| Terpineol | 8000-41-7; 98-55- 5; 138-87-4 | 2.5 % |"

    def test_find_sees_it(self):
        self.assertIn("98-55-5", codes.find(self.BROKEN, "cas"))

    def test_find_still_sees_the_unbroken_ones(self):
        found = codes.find(self.BROKEN, "cas")
        self.assertIn("8000-41-7", found)
        self.assertIn("138-87-4", found)

    def test_it_comes_back_closed_up(self):
        """Whatever the page did to it, the run works in one spelling."""
        self.assertNotIn("98-55- 5", codes.find(self.BROKEN, "cas"))

    def test_a_cell_carrying_the_broken_form_passes(self):
        self.assertTrue(codes.cell_ok("8000-41-7; 98-55- 5; 138-87-4"))

    def test_a_split_across_lines_is_not_joined(self):
        """Two table rows are not one number, however the cells fell."""
        self.assertEqual(codes.find("batch 98-55-\n5 kg", "cas"), [])

    def test_the_check_digit_is_still_applied_after_closing_it_up(self):
        self.assertEqual(codes.find("98-55- 4", "cas"), [])


if __name__ == "__main__":
    unittest.main()
