"""The gate: a form's own name held up against the list the app can offer.

The point of the step is to be wrong-able *before* anything is classified, so every test here asserts on
what the gate says rather than on what a later step does with it.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "plugins/customer-service-skills/skills/upload-documents"
GROUPING = SKILL / "lib/grouping"

TEMPLATES = [
    {"id": "dt_sds", "name": "Safety Data Sheet (SDS)", "for_tables": ["raw_materials"]},
    {"id": "dt_coa", "name": "Certificate of Analysis (CoA)", "for_tables": ["raw_materials"]},
    {"id": "dt_spec", "name": "Product Specification", "for_tables": ["raw_materials"]},
]


class Session:
    def __init__(self, root, forms):
        self.root = Path(root)
        (self.root / "WORKFLOW.json").write_text(json.dumps({
            "documentTemplates": TEMPLATES,
            "itemTemplates": [{"name": "Raw Material", "table": "raw_materials",
                               "identifierColumn": "code", "documentSections": []}]}), encoding="utf-8")
        (self.root / "NAMED.json").write_text(json.dumps({
            "forms": [{"formId": f"f{n:02d}", "documents": documents, "title": title,
                       "description": description}
                      for n, (title, description, documents) in enumerate(forms, 1)],
            "missing": [], "trimmed": [], "unreadable": [], "answeredForSomeoneElse": []}),
            encoding="utf-8")
        (self.root / "FORMS.json").write_text(json.dumps({
            "floor": 2, "threshold": 0.55, "documents": sum(f[2] for f in forms),
            "files": sum(f[2] for f in forms), "headerLines": 8, "skipped": None,
            "forms": [{"id": f"f{n:02d}", "members": [f"sha{n}{m}" for m in range(documents)],
                       "fit": {}, "wording": []}
                      for n, (_, _, documents) in enumerate(forms, 1)]}), encoding="utf-8")

    def run(self, *arguments):
        return subprocess.run(
            [sys.executable, str(GROUPING / "check_vocabulary.py"), str(self.root), *arguments],
            capture_output=True, text=True, encoding="utf-8", errors="replace")

    def gap(self):
        return json.loads((self.root / "VOCABULARY_GAP.json").read_text(encoding="utf-8"))


class GateTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def test_a_form_the_app_has_a_name_for_is_matched(self):
        session = Session(self.directory.name, [("Safety Data Sheet", "Hazards and handling.", 12)])
        result = session.run()
        self.assertEqual(result.returncode, 0, result.stderr)
        matched = session.gap()["matched"]
        self.assertEqual(matched[0]["templateId"], "dt_sds")

    def test_a_form_the_app_has_no_name_for_is_reported_with_its_document_count(self):
        # The number is the whole point: three forms is a shrug, 1,808 documents is a decision.
        session = Session(self.directory.name, [
            ("Introduction / Change of Supplier for Raw Materials", "Supplier form.", 1211),
            ("Safety Data Sheet", "Hazards.", 12)])
        session.run()
        gap = session.gap()
        self.assertEqual([m["formId"] for m in gap["missing"]], ["f01"])
        self.assertEqual(gap["missing"][0]["documents"], 1211)
        self.assertEqual(gap["documentsWithNoTemplate"], 1211)

    def test_the_gate_says_what_it_would_cost_to_carry_on(self):
        session = Session(self.directory.name, [("Notification of Change", "A change notice.", 400)])
        result = session.run()
        self.assertIn("400", result.stdout)
        # Both roads have to be on the page, because the tail of small forms is not worth a round trip.
        self.assertIn("re-export", result.stdout.casefold())
        self.assertIn("placeholder", result.stdout.casefold())

    def test_a_near_match_is_offered_rather_than_decided(self):
        # "Certificate of Analysis" against "Certificate of Analysis (CoA)" is the app's own name with
        # its abbreviation stripped; naming it a match silently is how a wrong template gets picked.
        session = Session(self.directory.name, [("Certificate of Analysis", "Batch results.", 30)])
        session.run()
        gap = session.gap()
        self.assertEqual(gap["matched"][0]["templateId"], "dt_coa")
        self.assertLess(gap["matched"][0]["score"], 1.0)

    def test_a_form_nobody_named_is_neither_matched_nor_missing(self):
        session = Session(self.directory.name, [("", "", 5)])
        session.run()
        gap = session.gap()
        self.assertEqual(gap["matched"], [])
        self.assertEqual(gap["missing"], [])
        self.assertEqual([u["formId"] for u in gap["unnamed"]], ["f01"])


if __name__ == "__main__":
    unittest.main()
