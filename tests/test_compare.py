"""Setting the one-at-a-time answers against each other.

Every other check in the skill judges one answer alone. This one is the only place a contradiction
*between* answers can be seen, so the tests are about what it notices and what it correctly ignores.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/upload-documents/lib"

HEADER = "SPECIFICATIONS AND ANALYTICAL REPORT FOR"


def row(n, template, quote, evidence, form=None, via=None):
    return {"path": f"C:/f/{n}.pdf", "relativePath": f"{n}.pdf", "name": f"{n}.pdf",
            "sha": f"sha{n:04d}", "readingId": f"r{n:04d}", "table": "raw_materials",
            "identifier": f"RM-{n:03d}", "itemId": str(n), "itemName": f"Material {n}",
            "itemTemplate": "Raw Material", "documentTemplate": template,
            "documentTemplateId": f"dt_{template[:4].lower()}", "proposedTemplate": None,
            "section": None, "sectionSortOrder": None, "confidence": 0.9,
            "evidence": evidence, "quote": quote, "review": None, "viaForm": via}


class Session:
    def __init__(self, root, rows, forms=None):
        self.root = Path(root)
        self.write("CLASSIFICATIONS.json", {"results": rows})
        if forms is not None:
            self.write("FORMS.json", {"forms": [{"id": name, "members": members, "fit": {},
                                                 "wording": []} for name, members in forms.items()]})

    def write(self, name, body):
        (self.root / name).write_text(json.dumps(body), encoding="utf-8")

    def read(self, name):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def run(self):
        return subprocess.run([sys.executable, str(LIB / "compare_answers.py"), str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def test_one_quotation_filed_two_ways_is_reported(self):
        # The live case: one header line, 28 filed as a specification and 13 as a certificate.
        rows = [row(n, "Product Specification", HEADER, f"Reads as a specification {n}.")
                for n in range(6)]
        rows += [row(n, "Certificate of Analysis", HEADER, f"Reads as a certificate {n}.")
                 for n in range(6, 10)]
        session = Session(self.directory.name, rows)
        result = session.run()
        self.assertEqual(result.returncode, 0, result.stderr)
        found = session.read("CONTRADICTIONS.json")
        self.assertEqual(len(found["quoteCollisions"]), 1)
        self.assertEqual(found["quoteCollisions"][0]["answers"], 10)
        self.assertEqual(set(found["quoteCollisions"][0]["templates"]),
                         {"Product Specification", "Certificate of Analysis"})

    def test_one_quotation_filed_one_way_is_not_a_contradiction(self):
        # Copies of a form share a header line, and agreeing about it is the normal case.
        session = Session(self.directory.name, [
            row(n, "Product Specification", HEADER, f"A specification {n}.") for n in range(10)])
        session.run()
        self.assertEqual(session.read("CONTRADICTIONS.json")["quoteCollisions"], [])

    def test_an_evidence_line_reused_inside_one_form_is_left_alone(self):
        # Measured against the grouping, identical evidence tracked documents that genuinely were the
        # same form — 792 raw alarms for about 110 real ones. Only reuse across forms is worth raising.
        rows = [row(n, "Product Specification", f"line {n} of the sheet", "The same sentence.")
                for n in range(8)]
        session = Session(self.directory.name, rows,
                          forms={"f01": [f"sha{n:04d}" for n in range(8)]})
        session.run()
        self.assertEqual(session.read("CONTRADICTIONS.json")["evidenceReusedAcrossForms"], [])

    def test_an_evidence_line_reused_across_forms_is_reported(self):
        rows = [row(n, "Product Specification", f"line {n} of the sheet", "The same sentence.")
                for n in range(8)]
        session = Session(self.directory.name, rows,
                          forms={"f01": [f"sha{n:04d}" for n in range(4)],
                                 "f02": [f"sha{n:04d}" for n in range(4, 8)]})
        session.run()
        reused = session.read("CONTRADICTIONS.json")["evidenceReusedAcrossForms"]
        self.assertEqual(len(reused), 1)
        self.assertEqual(reused[0]["forms"], ["f01", "f02"])

    def test_answers_that_came_from_a_form_are_not_compared(self):
        rows = [row(n, "Supplier Change Form", HEADER, "The form's own evidence.", via="f01")
                for n in range(10)]
        rows += [row(10, "Product Specification", HEADER, "Read on its own.")]
        session = Session(self.directory.name, rows)
        session.run()
        found = session.read("CONTRADICTIONS.json")
        self.assertEqual(found["readingsCompared"], 1)
        self.assertEqual(found["quoteCollisions"], [])


if __name__ == "__main__":
    unittest.main()
