"""Naming a form: what goes out to the agents, and what is allowed back.

The roll call is counted against `FORMS.json`, never against what an agent said it did — on the run this
work came out of, six batches reported one fewer answer than they held and every one was complete.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GROUPING = REPO / "plugins/customer-service-skills/skills/upload-documents/lib/grouping"

FORM_TEXT = "SUPPLIER CHANGE FORM\nSupplier: {who}\nMaterial: {what}\nPrice: {price}\n"


class Session:
    def __init__(self, root, sizes):
        self.root = Path(root)
        (self.root / "extracted").mkdir(parents=True, exist_ok=True)
        documents, extracted, forms = [], [], []
        number = 0
        for index, size in enumerate(sizes, 1):
            members = []
            for _ in range(size):
                sha = f"sha{number:04d}"
                text_file = self.root / "extracted" / f"{sha}.md"
                text_file.write_text(
                    FORM_TEXT.format(who=f"Supplier {number}", what=f"Material {number}", price=number),
                    encoding="utf-8")
                path = f"C:/folder/doc_{number:03d}.pdf"
                documents.append({"path": path, "relativePath": f"doc_{number:03d}.pdf",
                                  "name": f"doc_{number:03d}.pdf", "sha": sha})
                extracted.append({"path": path, "kind": "text",
                                  "textFile": str(text_file).replace("\\", "/"),
                                  "ocrTextFile": None, "ocrChars": 0})
                members.append(sha)
                number += 1
            forms.append({"id": f"f{index:02d}", "members": members,
                          "fit": {s: 1.0 for s in members}, "wording": ["SUPPLIER", "MATERIAL"]})
        (self.root / "DOCUMENTS.json").write_text(json.dumps(documents), encoding="utf-8")
        (self.root / "EXTRACTED.json").write_text(json.dumps({"documents": extracted}), encoding="utf-8")
        (self.root / "FORMS.json").write_text(json.dumps(
            {"floor": 2, "threshold": 0.55, "documents": len(documents), "files": len(documents),
             "headerLines": 8, "forms": forms, "skipped": None}), encoding="utf-8")

    def run(self, script, *arguments):
        return subprocess.run([sys.executable, str(GROUPING / script), str(self.root), *arguments],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def read(self, name):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def answer(self, form, **fields):
        answers = self.root / "named"
        answers.mkdir(exist_ok=True)
        body = {"formId": form, "title": "A Form", "description": "What it is for."}
        body.update(fields)
        (answers / f"{form}.json").write_text(json.dumps(body), encoding="utf-8")


class NamingTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.session = Session(self.directory.name, [9, 3, 1])

    def test_each_form_gets_one_task_carrying_a_sample_of_its_own(self):
        self.assertEqual(self.session.run("plan_naming.py").returncode, 0)
        tasks = self.session.read("NAMING.json")["tasks"]
        self.assertEqual([t["formId"] for t in tasks], ["f01", "f02", "f03"])
        self.assertEqual([len(t["samples"]) for t in tasks], [5, 3, 1])

    def test_the_sample_is_structure_only(self):
        self.session.run("plan_naming.py")
        body = json.dumps(self.session.read("naming/f01.json"))
        self.assertIn("SUPPLIER", body)
        self.assertNotIn("Supplier 4", body)

    def test_no_document_templates_are_offered(self):
        # Naming a form is not choosing a type. Showing a list is what made 979 documents Questionnaires.
        self.session.run("plan_naming.py")
        body = json.dumps(self.session.read("naming/f01.json")).lower()
        for word in ("documenttemplate", "vocabulary", "certificate of analysis"):
            self.assertNotIn(word, body)

    def test_a_form_nobody_answered_for_is_named_as_missing(self):
        self.session.run("plan_naming.py")
        self.session.answer("f01")
        self.session.answer("f02")
        result = self.session.run("collect_names.py")
        self.assertIn("f03", result.stdout)
        self.assertEqual(self.session.read("NAMED.json")["missing"], ["f03"])

    def test_an_over_long_title_is_cut_and_reported(self):
        self.session.run("plan_naming.py")
        for form in ("f01", "f02", "f03"):
            self.session.answer(form, title="T" * 400, description="D" * 4000)
        self.session.run("collect_names.py")
        named = self.session.read("NAMED.json")
        self.assertTrue(all(len(f["title"]) <= 120 for f in named["forms"]))
        self.assertTrue(all(len(f["description"]) <= 600 for f in named["forms"]))
        self.assertTrue(named["trimmed"])

    def test_an_answer_for_a_form_that_does_not_exist_is_refused(self):
        self.session.run("plan_naming.py")
        for form in ("f01", "f02", "f03"):
            self.session.answer(form)
        self.session.answer("f99")
        self.session.run("collect_names.py")
        named = self.session.read("NAMED.json")
        self.assertEqual([f["formId"] for f in named["forms"]], ["f01", "f02", "f03"])


if __name__ == "__main__":
    unittest.main()
