"""Arranging the Documents tab, after every document already has a template.

The step reads no document and no extracted text, so these fixtures are rows and an export — which is
the whole claim being tested: the question is answerable from what the run has already written.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/upload-documents/lib"

TEMPLATES = [
    {"id": "dt_sds", "name": "Safety Data Sheet (SDS)", "for_tables": ["raw_materials"]},
    {"id": "dt_sup", "name": "Supplier Change Form", "for_tables": ["raw_materials"]},
]


def row(template_id, name, item_template, n):
    return {"path": f"C:/f/{n}.pdf", "relativePath": f"{n}.pdf", "name": f"{n}.pdf",
            "sha": f"sha{n:04d}", "readingId": f"r{n:04d}", "table": "raw_materials",
            "identifier": f"RM-{n:03d}", "itemId": str(n), "itemName": f"Material {n}",
            "itemTemplate": item_template, "documentTemplate": name,
            "documentTemplateId": template_id, "proposedTemplate": None,
            "section": None, "sectionSortOrder": None, "confidence": 0.9,
            "evidence": "e", "quote": "q", "review": None, "viaForm": None}


class Session:
    def __init__(self, root, rows):
        self.root = Path(root)
        self.write("CLASSIFICATIONS.json", {"results": rows})
        self.write("WORKFLOW.json", {
            "documentTemplates": TEMPLATES,
            "itemTemplates": [
                {"name": "Active Material", "table": "raw_materials", "identifierColumn": "code",
                 "documentSections": [{"label": "Safety", "documentTemplates": ["dt_sds"]}]},
                {"name": "Standard", "table": "raw_materials", "identifierColumn": "code",
                 "documentSections": []}]})
        (self.root / "ITEMS.csv").write_text(
            "table,id,identifier,name,template,archived\n"
            "raw_materials,1,RM-001,One,Active Material,false\n"
            "raw_materials,2,RM-002,Two,Standard,false\n", encoding="utf-8")

    def write(self, name, body):
        (self.root / name).write_text(json.dumps(body), encoding="utf-8")

    def read(self, name):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def run(self, script):
        return subprocess.run([sys.executable, str(LIB / script), str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def answer(self, pairs):
        plan = self.read("SECTION_PLAN.json")
        Path(plan["output"]).write_text(json.dumps({"pairs": pairs}), encoding="utf-8")


class SectionPlanTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.session = Session(self.directory.name, [
            row("dt_sds", "Safety Data Sheet (SDS)", "Active Material", n) for n in range(6)
        ] + [row("dt_sup", "Supplier Change Form", "Standard", n) for n in range(6, 20)])

    def test_the_question_is_asked_per_pair_not_per_document(self):
        result = self.session.run("plan_sections.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = self.session.read("SECTION_PLAN.json")
        self.assertEqual(plan["pairs"], 2)
        self.assertEqual(plan["documents"], 20)

    def test_a_pair_the_app_already_arranges_says_so(self):
        self.session.run("plan_sections.py")
        task = json.loads((Path(self.directory.name) / "sections/task.json").read_text(encoding="utf-8"))
        by_template = {p["documentTemplateId"]: p for p in task["pairs"]}
        self.assertEqual(by_template["dt_sds"]["alreadyIn"], "Safety")
        self.assertIsNone(by_template["dt_sup"]["alreadyIn"])


class SectionAnswerTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.session = Session(self.directory.name, [
            row("dt_sds", "Safety Data Sheet (SDS)", "Active Material", n) for n in range(6)
        ] + [row("dt_sup", "Supplier Change Form", "Standard", n) for n in range(6, 20)])
        self.session.run("plan_sections.py")

    def test_a_section_the_app_lacks_is_marked_new(self):
        self.session.answer([
            {"documentTemplateId": "dt_sds", "itemTemplate": "Active Material", "section": "Safety"},
            {"documentTemplateId": "dt_sup", "itemTemplate": "Standard",
             "section": "Supplier Paperwork", "why": "Neither safety nor quality."}])
        result = self.session.run("collect_sections.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        by_template = {p["documentTemplateId"]: p for p in self.session.read("SECTIONS.json")["pairs"]}
        self.assertFalse(by_template["dt_sds"]["isNew"])
        self.assertTrue(by_template["dt_sup"]["isNew"])
        self.assertEqual(by_template["dt_sup"]["section"], "Supplier Paperwork")

    def test_a_section_id_is_derived_stably_and_per_item_template(self):
        # The export carries no section id, so this is the one id in the run that is not the app's.
        # Two Documents tabs with a "Safety" section are two sections, not one shared.
        self.session.answer([
            {"documentTemplateId": "dt_sds", "itemTemplate": "Active Material", "section": "Safety"},
            {"documentTemplateId": "dt_sup", "itemTemplate": "Standard", "section": "Safety"}])
        self.session.run("collect_sections.py")
        first = {p["documentTemplateId"]: p["sectionId"]
                 for p in self.session.read("SECTIONS.json")["pairs"]}
        self.assertNotEqual(first["dt_sds"], first["dt_sup"])
        self.session.run("collect_sections.py")
        second = {p["documentTemplateId"]: p["sectionId"]
                  for p in self.session.read("SECTIONS.json")["pairs"]}
        self.assertEqual(first, second)

    def test_the_apps_own_arrangement_is_not_overwritten(self):
        # Moving a template somebody already placed is a change to a Documents tab in use, and this
        # step is not entitled to make it quietly.
        self.session.answer([
            {"documentTemplateId": "dt_sds", "itemTemplate": "Active Material", "section": "Quality"},
            {"documentTemplateId": "dt_sup", "itemTemplate": "Standard", "section": "General"}])
        self.session.run("collect_sections.py")
        settled = self.session.read("SECTIONS.json")
        by_template = {p["documentTemplateId"]: p for p in settled["pairs"]}
        self.assertEqual(by_template["dt_sds"]["section"], "Safety")
        self.assertTrue(settled["kept"])

    def test_the_key_keeps_the_punctuation_the_apps_own_keys_keep(self):
        # A real export spells it `declarations_&_certificates`. Folding the `&` away derives an id the
        # app's own would not match, and the two reference sheets stop joining.
        self.session.answer([
            {"documentTemplateId": "dt_sds", "itemTemplate": "Active Material", "section": "Safety"},
            {"documentTemplateId": "dt_sup", "itemTemplate": "Standard",
             "section": "Declarations & Certificates"}])
        self.session.run("collect_sections.py")
        by_template = {p["documentTemplateId"]: p for p in self.session.read("SECTIONS.json")["pairs"]}
        self.assertEqual(by_template["dt_sup"]["sectionKey"], "declarations_&_certificates")

    def test_a_pair_nobody_answered_is_named_rather_than_defaulted(self):
        self.session.answer([
            {"documentTemplateId": "dt_sds", "itemTemplate": "Active Material", "section": "Safety"}])
        self.session.run("collect_sections.py")
        settled = self.session.read("SECTIONS.json")
        self.assertEqual(len(settled["pairs"]), 1)
        self.assertIn("Supplier Change Form", settled["missing"][0])


if __name__ == "__main__":
    unittest.main()
