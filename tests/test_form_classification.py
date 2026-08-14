"""Classifying a form instead of its documents, and what falls out of that downstream.

The seam is the session directory, as everywhere else: manifests in, manifests out. What matters here is
not that an agent answers well but that one answer reaches every member of the form it was asked about,
and that a form nobody may answer that way is still read one document at a time.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "plugins/customer-service-skills/skills/upload-documents"
LIB = SKILL / "lib"
GROUPING = LIB / "grouping"

SUPPLIER = """INTRODUCTION / CHANGE OF SUPPLIER FOR RAW MATERIALS
Doc No FRM-029
Supplier: {supplier}
Raw material: {material}
Storage conditions: {storage}
Approved by: {approver}
"""

TEMPLATES = [
    {"id": "dt_sup", "name": "Supplier Change Form", "for_tables": ["raw_materials"]},
    {"id": "dt_sds", "name": "Safety Data Sheet (SDS)", "for_tables": ["raw_materials"]},
]


class Session:
    """A folder that has been hashed, extracted, grouped and named — where this step starts."""

    def __init__(self, root, members=12):
        self.root = Path(root)
        (self.root / "extracted").mkdir(parents=True, exist_ok=True)
        documents, extracted = [], []
        for n in range(members):
            sha = f"sha{n:04d}"
            body = SUPPLIER.format(supplier=f"S{n}", material=f"M{n}",
                                   storage=f"{n} degrees", approver=f"Person {n}")
            text_file = self.root / "extracted" / f"{sha}.md"
            text_file.write_text(body, encoding="utf-8")
            path = f"C:/folder/RM-{n:03d}/{sha}.pdf"
            documents.append({"path": path, "relativePath": f"RM-{n:03d}/{sha}.pdf",
                              "name": f"{sha}.pdf", "sha": sha})
            extracted.append({"path": path, "kind": "text",
                              "textFile": str(text_file).replace("\\", "/"),
                              "ocrTextFile": None, "images": [], "ocrChars": 0})
        self.shas = [d["sha"] for d in documents]

        self.write("DOCUMENTS.json", documents)
        self.write("EXTRACTED.json", {"documents": extracted})
        self.write("WORKFLOW.json", {
            "documentTemplates": TEMPLATES,
            "itemTemplates": [{"name": "Raw Material", "table": "raw_materials",
                               "identifierColumn": "code",
                               "documentSections": [{"label": "Safety",
                                                     "documentTemplates": ["dt_sds"]}]}]})
        (self.root / "ITEMS.csv").write_text(
            "table,id,identifier,name,template,archived\n" + "".join(
                f"raw_materials,{n},RM-{n:03d},Material {n},Raw Material,false\n"
                for n in range(members)), encoding="utf-8")
        self.write("BRANCHES.json", {"branches": [
            {"pathPrefix": "", "table": "raw_materials", "hintLevel": None,
             "identifier": {"type": "folderLevel", "level": 1}}]})
        self.write("FORMS.json", {
            "floor": 2, "threshold": 0.55, "documents": members, "files": members,
            "headerLines": 8, "skipped": None,
            "forms": [{"id": "f01", "members": self.shas,
                       "fit": {s: 1.0 for s in self.shas}, "wording": ["SUPPLIER"]}]})
        self.write("NAMED.json", {
            "forms": [{"formId": "f01", "documents": members,
                       "title": "Introduction / Change of Supplier for Raw Materials",
                       "description": "The supplier introduction and change form."}],
            "missing": [], "trimmed": [], "unreadable": [], "answeredForSomeoneElse": []})

    def write(self, name, body):
        (self.root / name).write_text(json.dumps(body), encoding="utf-8")

    def read(self, name):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def run(self, folder, script, *arguments):
        return subprocess.run([sys.executable, str(folder / script), str(self.root), *arguments],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def answer_the_form(self, **fields):
        """Write what a form-level agent would have written, quoting what it was actually shown."""
        task = self.read("FORM_CLASSIFICATION.json")["tasks"][0]
        payload = json.loads(Path(task["input"]).read_text(encoding="utf-8"))
        quote = next(line for line in payload["samples"][0]["structure"] if len(line) > 12)
        answer = {"formId": "f01", "received": True, "documentTemplateId": "dt_sup",
                  "runnerUpTemplateId": "dt_sds", "proposedTemplate": None,
                  "confidence": 0.93, "quote": quote,
                  "evidence": "The header names the supplier change form.", **fields}
        Path(task["output"]).write_text(json.dumps(answer), encoding="utf-8")


class FormClassificationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.session = Session(self.directory.name)

    def test_one_task_covers_every_document_on_the_form(self):
        result = self.session.run(GROUPING, "plan_form_classification.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        planned = self.session.read("FORM_CLASSIFICATION.json")
        self.assertEqual(len(planned["tasks"]), 1)
        self.assertEqual(planned["tasks"][0]["documents"], 12)

    def test_the_task_carries_the_forms_own_name_and_the_apps_list(self):
        self.session.run(GROUPING, "plan_form_classification.py")
        task = self.session.read("FORM_CLASSIFICATION.json")["tasks"][0]
        payload = json.loads(Path(task["input"]).read_text(encoding="utf-8"))
        self.assertIn("Change of Supplier", payload["title"])
        offered = {t["id"] for t in payload["vocabulary"]["documentTemplates"]["raw_materials"]}
        self.assertEqual(offered, {"dt_sup", "dt_sds"})

    def test_a_form_split_by_value_is_not_asked_here(self):
        # Its members are the same paper and the app still calls them different things, so one answer
        # cannot stand for them. They go back to being read one at a time.
        self.session.write("SPLIT_RULES.json", {
            "rules": [], "dissolved": [], "readOneAtATime": [], "renameThese": [],
            "splitByValue": [{"form": "f01", "documents": 12, "splitsInto": "blank versus filled"}]})
        self.session.run(GROUPING, "plan_form_classification.py")
        planned = self.session.read("FORM_CLASSIFICATION.json")
        self.assertEqual(planned["tasks"], [])
        self.assertEqual(planned["skipped"][0]["formId"], "f01")

    def test_what_a_split_form_splits_into_reaches_the_reading(self):
        # Recording the person's sentence and never delivering it would leave the hardest documents in
        # the folder read with no more to go on than before they said anything.
        self.session.write("SPLIT_RULES.json", {
            "rules": [], "dissolved": [], "readOneAtATime": [], "renameThese": [],
            "splitByValue": [{"form": "f01", "documents": 12,
                              "splitsInto": "Product Specification where the results column is blank"}]})
        self.session.run(GROUPING, "plan_form_classification.py")
        result = self.session.run(LIB, "plan_batches.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = self.session.read("BATCHES.json")["batches"][0]
        payload = json.loads(Path(entry["input"]).read_text(encoding="utf-8"))
        self.assertIn("results column is blank", payload["documents"][0]["splitsInto"])

    def test_an_answer_quoting_something_it_was_never_shown_is_refused(self):
        self.session.run(GROUPING, "plan_form_classification.py")
        self.session.answer_the_form(quote="CERTIFICATE OF ANALYSIS FOR BATCH 4471")
        self.session.run(GROUPING, "collect_form_templates.py")
        settled = self.session.read("FORM_TEMPLATES.json")
        self.assertEqual(settled["forms"], [])
        self.assertIn("not in the samples", settled["rejected"][0]["why"])

    def test_an_answer_naming_a_template_the_app_forbids_is_refused(self):
        self.session.run(GROUPING, "plan_form_classification.py")
        self.session.answer_the_form(documentTemplateId="dt_not_real")
        self.session.run(GROUPING, "collect_form_templates.py")
        self.assertEqual(self.session.read("FORM_TEMPLATES.json")["forms"], [])

    def test_the_answer_says_how_many_documents_it_stands_for(self):
        # Five members were read and twelve are carried. A row must be able to say so rather than
        # implying somebody looked at that file.
        self.session.run(GROUPING, "plan_form_classification.py")
        self.session.answer_the_form()
        self.session.run(GROUPING, "collect_form_templates.py")
        form = self.session.read("FORM_TEMPLATES.json")["forms"][0]
        self.assertEqual(form["standsFor"], 12)
        self.assertEqual(form["sampled"], 5)


class FanOutTest(unittest.TestCase):
    """What the rest of the run does with an answer given once for a whole form."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.session = Session(self.directory.name)
        self.session.run(GROUPING, "plan_form_classification.py")
        self.session.answer_the_form()
        self.session.run(GROUPING, "collect_form_templates.py")

    def test_documents_their_form_answered_are_never_batched(self):
        result = self.session.run(LIB, "plan_batches.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = self.session.read("BATCHES.json")
        self.assertEqual(manifest["batches"], [])
        self.assertEqual(manifest["counts"]["answeredByTheirForm"], 12)

    def test_every_member_gets_the_forms_answer_and_says_where_it_came_from(self):
        self.session.run(LIB, "plan_batches.py")
        result = self.session.run(LIB, "collect_classifications.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.session.read("CLASSIFICATIONS.json")["results"]
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(r["documentTemplate"] == "Supplier Change Form" for r in rows))
        # The provenance is the point: none of these files was read, the form they share was.
        self.assertTrue(all(r["viaForm"] == "f01" for r in rows))

    def test_a_row_says_how_many_documents_its_answer_stood_for(self):
        # ADR-0005: five members were read and twelve are carried, and the workbook must not imply
        # somebody looked at this file.
        self.session.run(LIB, "plan_batches.py")
        self.session.run(LIB, "collect_classifications.py")
        row = self.session.read("CLASSIFICATIONS.json")["results"][0]
        self.assertEqual(row["standsFor"], 12)
        self.assertEqual(row["sampled"], 5)

    def test_a_form_answer_is_not_compared_against_itself(self):
        # One answer per form by construction, so a form's members cannot contradict each other and
        # counting them as agreeing or disagreeing would be counting the same answer twelve times.
        self.session.run(LIB, "plan_batches.py")
        self.session.run(LIB, "collect_classifications.py")
        result = self.session.run(LIB, "compare_answers.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        found = self.session.read("CONTRADICTIONS.json")
        self.assertEqual(found["readingsCompared"], 0)
        self.assertEqual(found["quoteCollisions"], [])


if __name__ == "__main__":
    unittest.main()
