"""What an extraction says about itself, and what a second run is allowed to skip.

Two claims meet here. A run must not redo work it already has on disk — OCR did that on every run,
overwriting its own output and ignoring `--force`. And a run reusing somebody else's extraction must be
able to say whose it was, because a manifest from an older skill is an older skill's answers.
"""

import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/extract-document-text/lib"
sys.path.insert(0, str(LIB))

import extract_documents as ed  # noqa: E402


def options(**over):
    base = {
        "scans": "first", "max_chars": 0, "ocr": False, "max_pages": 40,
        "scale": 2.0, "enhance": False, "tables": True, "table_pages": 40, "force": False,
    }
    base.update(over)
    return types.SimpleNamespace(**base)


class OcrIsNotRedone(unittest.TestCase):
    """`read_by_ocr` re-read every record on every run and overwrote its own file, ignoring --force."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.out = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.source = self.out / "scan.png"
        self.source.write_bytes(b"not really a png")
        self.record = ed.record_for(self.source, "scan.png", kind="image")

    def ocr_file(self):
        return self.out / f"{ed.slug_for(Path(self.record['path']))}.ocr.md"

    def written(self, pages, body="PAGE ONE TEXT"):
        self.ocr_file().write_text("\n".join([f"<!-- pages: {pages} -->", body]), encoding="utf-8")

    def test_an_existing_reading_is_reused_and_never_reopened(self):
        self.written(1)
        ed.ocr_record(self.record, self.out, options())
        self.assertEqual(self.record["ocrChars"], len("PAGE ONE TEXT"))
        self.assertTrue(self.record["ocrTextFile"].endswith(".ocr.md"))
        self.assertIn("reused", self.record["note"])

    def test_reuse_does_not_overwrite_what_is_there(self):
        self.written(1)
        before = self.ocr_file().read_text(encoding="utf-8")
        ed.ocr_record(self.record, self.out, options())
        self.assertEqual(self.ocr_file().read_text(encoding="utf-8"), before)

    def test_a_reading_made_from_fewer_pages_is_not_reused(self):
        """--scans first then --scans all renders more pages; the old reading answers for one of them."""
        self.record["images"] = [str(self.out / "page_001.png"), str(self.out / "page_002.png")]
        self.written(1)
        ed.ocr_record(self.record, self.out, options())
        self.assertNotIn("reused", self.record["note"] or "")

    def test_a_reading_made_from_the_same_pages_is_reused(self):
        self.record["images"] = [str(self.out / "page_001.png")]
        self.written(1)
        ed.ocr_record(self.record, self.out, options())
        self.assertIn("reused", self.record["note"])

    def test_force_does_not_reuse(self):
        self.written(1)
        ed.ocr_record(self.record, self.out, options(force=True))
        self.assertNotIn("reused", self.record["note"] or "")
        self.assertEqual(self.record["ocrChars"], 0)

    def test_reuse_leaves_kind_and_textfile_alone(self):
        self.written(1)
        ed.ocr_record(self.record, self.out, options())
        self.assertEqual(self.record["kind"], "image")
        self.assertIsNone(self.record["textFile"])


class TheManifestSaysWhatMadeIt(unittest.TestCase):
    def test_the_version_is_the_plugins_own(self):
        manifest = REPO / "plugins/customer-service-skills/.claude-plugin/plugin.json"
        expected = json.loads(manifest.read_text(encoding="utf-8"))["version"]
        self.assertEqual(ed.skill_version(), expected)

    def test_the_flags_that_change_what_is_written_are_recorded(self):
        stamp = ed.produced_by(options(scans="none", tables=False, max_chars=4000))
        self.assertEqual(stamp["flags"]["scans"], "none")
        self.assertEqual(stamp["flags"]["tables"], False)
        self.assertEqual(stamp["flags"]["maxChars"], 4000)
        self.assertIsNone(stamp["flags"]["ocr"])

    def test_ocr_is_named_by_its_package_when_it_ran(self):
        self.assertEqual(ed.produced_by(options(ocr=True))["flags"]["ocr"], ed.OCR_PACKAGE)


class ReuseKnowsWhoseExtractionItIs(unittest.TestCase):
    """`reuse_extraction.py` read one field of a manifest — the cap — and compared nothing."""

    def setUp(self):
        sys.path.insert(0, str(REPO / "plugins/customer-service-skills/skills/extract-composition-from-documents/lib"))
        import reuse_extraction  # noqa: E402

        self.reuse = reuse_extraction

    def test_a_manifest_from_another_version_is_named_as_such(self):
        said = self.reuse.provenance({"producedBy": {"skillVersion": "0.11.0", "flags": {}}}, "0.12.0")
        self.assertIn("0.11.0", said)
        self.assertIn("0.12.0", said)

    def test_the_same_version_says_nothing(self):
        self.assertEqual(self.reuse.provenance({"producedBy": {"skillVersion": "0.12.0", "flags": {}}}, "0.12.0"), "")

    def test_a_manifest_with_no_stamp_is_named_as_older_than_the_stamp(self):
        said = self.reuse.provenance({"root": "C:/x"}, "0.12.0")
        self.assertIn("before", said.lower())

    def test_flags_that_change_coverage_are_named(self):
        said = self.reuse.provenance(
            {"producedBy": {"skillVersion": "0.12.0", "flags": {"scans": "none", "ocr": None}}},
            "0.12.0",
            want={"scans": "all"},
        )
        self.assertIn("scans", said)


if __name__ == "__main__":
    unittest.main()
