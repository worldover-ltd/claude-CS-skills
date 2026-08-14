"""The grouping step, at the seam every other library script uses: a session directory in, JSON out.

Fixtures are written as two invented forms with different values typed into each copy, because that is
the thing the step has to see through — a form is what its copies share once the answers are rubbed out.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GROUPING = REPO / "plugins/customer-service-skills/skills/upload-documents/lib/grouping"
sys.path.insert(0, str(GROUPING))

import mask_text  # noqa: E402

SUPPLIER_FORM = """INTRODUCTION / CHANGE OF SUPPLIER FOR RAW MATERIALS
Doc No FRM-029
Supplier: {supplier}
Raw material: {material}
Code: {code}
Storage conditions: {storage}
Pack size: {pack}
Price per kilo: {price}
Attach COA and MSDS
Approved by: {approver}
"""

ANALYSIS_FORM = """SPECIFICATIONS AND ANALYTICAL REPORT
Doc. No. {code}
FOR PRIME PRODUCT
{material}
Revision {revision}
TEST METHOD UOM SPECIFICATION RESULT
APPEARANCE Visual {appearance}
COLOUR Visual {colour}
MICROBIOLOGY Risk Classification {risk}
"""

SUPPLIERS = ["BASF", "Croda", "Symrise", "Evonik", "Clariant", "Lubrizol"]
MATERIALS = ["Cetiol B", "Glycerin", "Honey", "Avenolat", "Carbopol", "Actiwhite",
             "Lexguard O", "PEG 300", "Vegetol Tea", "Antaron V", "SymSave H", "Crodamol"]


def a_supplier_document(n):
    return SUPPLIER_FORM.format(
        supplier=SUPPLIERS[n % len(SUPPLIERS)], material=MATERIALS[n % len(MATERIALS)],
        code=f"R{100000 + n}", storage=f"{n % 30} degrees", pack=f"{n * 5}kg",
        price=f"{n}.50", approver=f"Person {n}")


def an_analysis_document(n):
    return ANALYSIS_FORM.format(
        code=f"R{200000 + n}", material=MATERIALS[n % len(MATERIALS)], revision=f"{n % 4}",
        appearance=f"Liquid {n}", colour=f"Shade {n}", risk=f"Category {n % 5}")


class Session:
    """A session directory holding what the extraction step leaves behind, and nothing else."""

    def __init__(self, root, texts, copies=()):
        self.root = Path(root)
        (self.root / "extracted").mkdir(parents=True, exist_ok=True)
        documents, extracted = [], []
        for number, body in enumerate(texts):
            name = f"doc_{number:03d}"
            text_file = self.root / "extracted" / f"{name}.md"
            text_file.write_text(body, encoding="utf-8")
            path = f"C:/folder/{name}.pdf"
            documents.append({"path": path, "relativePath": f"{name}.pdf",
                              "name": f"{name}.pdf", "sha": f"sha{number:04d}"})
            extracted.append({"path": path, "kind": "text",
                              "textFile": str(text_file).replace("\\", "/"),
                              "ocrTextFile": None, "ocrChars": 0})
        # A copy is a second file carrying content the run has already seen, and must not be read twice.
        for number, source in enumerate(copies):
            path = f"C:/folder/copy_{number:03d}.pdf"
            documents.append({"path": path, "relativePath": f"copy_{number:03d}.pdf",
                              "name": f"copy_{number:03d}.pdf", "sha": f"sha{source:04d}"})
            extracted.append({"path": path, "kind": "text",
                              "textFile": extracted[source]["textFile"],
                              "ocrTextFile": None, "ocrChars": 0})
        (self.root / "DOCUMENTS.json").write_text(json.dumps(documents), encoding="utf-8")
        (self.root / "EXTRACTED.json").write_text(json.dumps({"documents": extracted}), encoding="utf-8")

    def group(self, *arguments):
        # These fixtures are deliberately small; the real guard against a folder too small to group has
        # its own test and passes its own limit.
        if "--min-corpus" not in arguments:
            arguments = ("--min-corpus", "10", *arguments)
        result = subprocess.run(
            [sys.executable, str(GROUPING / "group_documents.py"), str(self.root), *arguments],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        return result

    def forms(self):
        return json.loads((self.root / "FORMS.json").read_text(encoding="utf-8"))


class MaskingTest(unittest.TestCase):
    def setUp(self):
        self.texts = [a_supplier_document(n) for n in range(12)]
        self.frequency = mask_text.frequency(self.texts)

    def test_a_word_on_every_copy_is_part_of_the_form(self):
        self.assertEqual(self.frequency["SUPPLIER"], 12)
        self.assertEqual(self.frequency["INTRODUCTION"], 12)

    def test_a_word_typed_into_one_copy_is_not(self):
        self.assertLessEqual(self.frequency["AVENOLAT"], 1)

    def test_a_run_together_title_counts_as_its_parts(self):
        # OCR joins a title into one token on some copies and not others, so a title that is plainly
        # part of the form reads as two rare tokens unless the joined one is taken apart. What it is
        # taken apart *by* is the rest of the folder: words some other document spaced out properly.
        mixed = ["SPECIFICATIONSANDANALYTICALREPORT\nbody"] * 3 + \
                ["SPECIFICATIONS AND ANALYTICAL REPORT\nbody"] * 2
        joined = mask_text.frequency(mixed)
        self.assertEqual(joined["SPECIFICATIONS"], 5)
        self.assertEqual(joined["ANALYTICAL"], 5)
        self.assertEqual(joined["REPORT"], 5)

    def test_a_title_nothing_in_the_folder_ever_spaced_stays_joined(self):
        # The honest limit of the above: with no spaced copy anywhere there is nothing to split against,
        # and the token survives whole. It still counts, so the form is not lost — see the header rule.
        only_joined = mask_text.frequency(["SPECIFICATIONSANDANALYTICALREPORT\nbody"] * 5)
        self.assertEqual(only_joined["SPECIFICATIONSANDANALYTICALREPORT"], 5)
        self.assertEqual(only_joined["ANALYTICAL"], 0)

    def test_the_structure_view_keeps_the_form_and_blanks_the_answers(self):
        keep = {word for word, count in self.frequency.items() if count >= 6}
        view = "\n".join(mask_text.structure_view(self.texts[0], keep, header_lines=0))
        self.assertIn("SUPPLIER", view)
        self.assertIn("STORAGE", view)
        self.assertNotIn("BASF", view)
        self.assertNotIn("CETIOL", view)

    def test_the_header_is_never_blanked(self):
        # The title is what a naming agent needs most, and on a form used by few documents every word of
        # it sits under the floor.
        view = mask_text.structure_view("RARE UNIQUE TITLE\nSUPPLIER: someone", set(), header_lines=1)
        self.assertEqual(view[0], "RARE UNIQUE TITLE")


class GroupingTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def session(self, **kwargs):
        texts = [a_supplier_document(n) for n in range(12)] + \
                [an_analysis_document(n) for n in range(8)]
        return Session(self.directory.name, texts, **kwargs)

    def test_two_forms_come_back_as_two_forms(self):
        session = self.session()
        result = session.group()
        self.assertEqual(result.returncode, 0, result.stderr)
        sizes = sorted(len(form["members"]) for form in session.forms()["forms"])
        self.assertEqual(sizes, [8, 12])

    def test_copies_are_one_document(self):
        # ADR-0001: the unit is content, not a path. Six copies must not become six members.
        session = self.session(copies=[0, 1, 2, 3, 4, 5])
        session.group()
        forms = session.forms()
        self.assertEqual(sum(len(f["members"]) for f in forms["forms"]), 20)
        self.assertEqual(forms["documents"], 20)
        self.assertEqual(forms["files"], 26)

    def test_the_numbers_that_produced_a_form_are_recorded(self):
        session = self.session()
        session.group()
        forms = session.forms()
        for key in ("floor", "threshold", "documents"):
            self.assertIn(key, forms)
        for form in forms["forms"]:
            self.assertEqual(sorted(form["fit"]), sorted(form["members"]))

    def test_a_folder_too_small_to_group_is_skipped_and_says_so(self):
        session = Session(self.directory.name, [a_supplier_document(n) for n in range(4)])
        result = session.group("--min-corpus", "10")
        self.assertEqual(result.returncode, 0, result.stderr)
        forms = session.forms()
        self.assertEqual(forms["forms"], [])
        self.assertIn("too small", forms["skipped"])
        self.assertIn("too small", result.stdout)

    def test_a_split_rule_separates_one_form_into_two(self):
        # The repair path: the person's marks became a rule, and the rule is data the unchanged script
        # reads. Half the supplier documents get a word the other half lack.
        texts = [a_supplier_document(n) + ("\nREMOVAL OF PACKAGING COMPONENTS\n" * 6 if n % 2 else "")
                 for n in range(12)]
        session = Session(self.directory.name, texts)
        session.group()
        before = len(session.forms()["forms"])
        (Path(self.directory.name) / "SPLIT_RULES.json").write_text(
            json.dumps({"rules": [{"form": "f01", "wording": ["REMOVAL"]}]}), encoding="utf-8")
        session.group()
        self.assertGreater(len(session.forms()["forms"]), before)

    def test_a_threshold_rule_splits_a_form_more_strictly(self):
        # Some forms are not wrong about what their members say, only about how much they had to share.
        # A number is still something a person can be shown, unlike a change to the clustering code.
        session = self.session()
        session.group()
        before = len(session.forms()["forms"])
        (Path(self.directory.name) / "SPLIT_RULES.json").write_text(
            json.dumps({"rules": [{"form": "f01", "threshold": 0.95}]}), encoding="utf-8")
        session.group()
        after = session.forms()["forms"]
        self.assertGreater(len(after), before)
        self.assertTrue(any("threshold" in " ".join(f.get("splitBy") or []) for f in after))

    def test_the_sweep_reports_without_writing_forms(self):
        session = self.session()
        session.group()
        before = session.forms()
        result = session.group("--sweep")
        self.assertIn("floor", result.stdout)
        self.assertEqual(session.forms(), before)


if __name__ == "__main__":
    unittest.main()
