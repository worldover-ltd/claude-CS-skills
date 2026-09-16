"""Which folder names get put to the user first, and why a name alone never excludes anything.

Ranking by repetition finds the category somebody made on purpose under every item - `Oud` under three
hundred material folders. It is blind to the other shape: one `Archive` at the top of the tree, holding
thousands of files and sitting under exactly one parent, which sorts below every item folder and falls
off the end of the list the user is shown.

Both are worth offering. Neither is ever excluded without the user naming it: a blanket rule on names
is what silently dropped real documents last time, on a folder where 132 files genuinely ended
`.pdf.pdf`.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/upload-documents/lib"
sys.path.insert(0, str(LIB))

import plan_exclusions  # noqa: E402


def tree(*paths):
    return [{"path": "/".join(parts), "folders": list(parts[:-1]), "ext": parts[-1].rsplit(".", 1)[-1]}
            for parts in paths]


class OneArchiveAtTheTop(unittest.TestCase):
    """The shape repetition cannot see: many files, one parent."""

    def setUp(self):
        self.files = tree(*[("Archive", f"old_{n}.pdf") for n in range(40)],
                          *[("Raw Materials", f"RM-{n:04d}", "SDS.pdf") for n in range(40)])

    def test_it_is_offered(self):
        names = [row[0] for row in plan_exclusions.folder_candidates(self.files)]
        self.assertIn("archive", names)

    def test_it_is_offered_before_the_item_folders(self):
        ranked = [row[0] for row in plan_exclusions.folder_candidates(self.files)]
        self.assertLess(ranked.index("archive"), ranked.index("rm-0000"))

    def test_it_is_marked_as_a_name_worth_asking_about(self):
        rows = plan_exclusions.folder_candidates(self.files)
        flagged = {name: hinted for name, _, _, hinted in rows}
        self.assertTrue(flagged["archive"])
        self.assertFalse(flagged["rm-0000"])


class TheNamesCustomersUse(unittest.TestCase):
    def test_english_and_dutch_and_german(self):
        for name in ("Archive", "Old", "Oud", "Archief", "Alt", "Backup", "Superseded",
                     "Obsolete", "Vervallen", "Niet meer gebruiken"):
            self.assertTrue(plan_exclusions.hinted(name), name)

    def test_case_and_decoration_do_not_matter(self):
        for name in ("ARCHIVE", "_old", "01 - Archief", "Old files"):
            self.assertTrue(plan_exclusions.hinted(name), name)

    def test_a_material_folder_is_not_hinted(self):
        for name in ("RM-0142", "R289 - Dissolvine GL-47-S", "SDS", "Certificates", "2024"):
            self.assertFalse(plan_exclusions.hinted(name), name)

    def test_a_word_that_merely_contains_one_is_not_hinted(self):
        """`Gold` ends in `old`, and `Bolder` contains it."""
        for name in ("Gold standard", "Bolder labels", "Holder"):
            self.assertFalse(plan_exclusions.hinted(name), name)


class RepetitionStillCounts(unittest.TestCase):
    def test_a_category_under_every_item_still_outranks_a_one_off(self):
        files = tree(*[("Raw Materials", f"RM-{n:04d}", "Oud", "old.pdf") for n in range(30)],
                     ("Raw Materials", "RM-0000", "Certificates", "a.pdf"))
        ranked = [row[0] for row in plan_exclusions.folder_candidates(files)]
        self.assertLess(ranked.index("oud"), ranked.index("certificates"))


class NothingIsExcludedUntilItIsNamed(unittest.TestCase):
    def test_a_hinted_name_alone_catches_no_file(self):
        record = {"path": "Archive/x.pdf", "folders": ["Archive"], "ext": "pdf"}
        self.assertIsNone(plan_exclusions.excluded_by(record, set(), set()))

    def test_naming_it_catches_the_file(self):
        record = {"path": "Archive/x.pdf", "folders": ["Archive"], "ext": "pdf"}
        self.assertIn("Archive", plan_exclusions.excluded_by(record, {"archive"}, set()))


if __name__ == "__main__":
    unittest.main()
