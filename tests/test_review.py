"""The review round trip: what goes onto the page, and what the person's answer turns into.

The page itself is not tested here — a browser would be a new seam, and the contract that matters is the
one either side of it: a manifest going in, a pasted verdict coming back.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "plugins/customer-service-skills/skills/upload-documents"
REVIEW = SKILL / "lib/review"
GROUPING = SKILL / "lib/grouping"

PLAIN = "SUPPLIER CHANGE FORM\nSupplier: {who}\nMaterial: {what}\n"
WITH_REMOVAL = "SUPPLIER CHANGE FORM\nREMOVAL OF PACKAGING\nSupplier: {who}\nMaterial: {what}\n"
# The same stationery with its results typed in: one form, and the app calls the two halves different
# things. Nothing in the printed words separates them, which is the whole point of a value split.
RESULTS = "\nRESULT 4.72 6.13 0.08 99.4 12.6 3.11 78.2 0.55 21.9 44.0\n"


class Session:
    """A session that has been grouped and named, which is what the review step starts from."""

    def __init__(self, root, members):
        self.root = Path(root)
        (self.root / "extracted").mkdir(parents=True, exist_ok=True)
        documents, extracted = [], []
        for number, (sha, body) in enumerate(members):
            text_file = self.root / "extracted" / f"{sha}.md"
            text_file.write_text(body, encoding="utf-8")
            path = f"C:/folder/{sha}.pdf"
            documents.append({"path": path, "relativePath": f"{sha}.pdf",
                              "name": f"{sha}.pdf", "sha": sha})
            extracted.append({"path": path, "kind": "text",
                              "textFile": str(text_file).replace("\\", "/"),
                              "ocrTextFile": None, "images": [], "ocrChars": 0})
        shas = [sha for sha, _ in members]
        (self.root / "DOCUMENTS.json").write_text(json.dumps(documents), encoding="utf-8")
        (self.root / "EXTRACTED.json").write_text(json.dumps({"documents": extracted}), encoding="utf-8")
        (self.root / "FORMS.json").write_text(json.dumps({
            "floor": 2, "threshold": 0.55, "documents": len(shas), "files": len(shas),
            "headerLines": 8, "skipped": None,
            "forms": [{"id": "f01", "members": shas, "fit": {s: 1.0 for s in shas},
                       "wording": ["SUPPLIER", "FORM"]}]}), encoding="utf-8")
        (self.root / "NAMED.json").write_text(json.dumps({
            "forms": [{"formId": "f01", "documents": len(shas), "title": "Supplier Change Form",
                       "description": "Collects supplier details."}],
            "missing": [], "trimmed": [], "unreadable": [], "answeredForSomeoneElse": []}),
            encoding="utf-8")

    def run(self, folder, script, *arguments):
        return subprocess.run([sys.executable, str(folder / script), str(self.root), *arguments],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def read(self, name):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def paste(self, body):
        note = self.root / "paste.txt"
        note.write_text(body, encoding="utf-8")
        return str(note)


def verdict(marked, grouping="ok", naming="ok", shown=6, splits_into=None):
    answer = {"formId": "f01", "grouping": grouping, "naming": naming,
              "randomShown": shown, "randomMarked": len(marked), "marked": marked}
    if splits_into:
        answer["splitsInto"] = splits_into
    return ("Some prose the person can read.\n\n```form-review\n"
            + json.dumps({"forms": [answer]}) + "\n```\n")


class ReviewPageTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.session = Session(self.directory.name, [
            (f"sha{n:03d}", PLAIN.format(who=f"S{n}", what=f"M{n}") + (RESULTS if n % 2 else ""))
            for n in range(12)])

    def test_the_manifest_separates_a_random_block_from_the_chosen_ones(self):
        # Only the random block may be counted; the other two are chosen to look wrong. Sizes are given
        # here because no member is shown twice, so a form of twelve runs out under the defaults.
        self.assertEqual(self.session.run(
            REVIEW, "build_review.py", "--random", "4", "--suspect", "2", "--filled", "2").returncode, 0)
        form = self.session.read("REVIEW.json")["forms"][0]
        blocks = {sample["block"] for sample in form["samples"]}
        self.assertEqual(blocks, {"random", "suspect", "filled"})
        self.assertEqual(form["randomShown"],
                         sum(1 for s in form["samples"] if s["block"] == "random"))

    def test_what_the_sample_leaves_out_is_stated(self):
        # A sample bounds what anybody sees, and silence about that reads as "everything was checked".
        self.session.run(REVIEW, "build_review.py", "--random", "3", "--suspect", "2", "--filled", "2")
        form = self.session.read("REVIEW.json")["forms"][0]
        self.assertEqual(form["randomShown"], 3)
        self.assertEqual(form["suspectShown"], 2)
        self.assertEqual(form["filledShown"], 2)
        self.assertEqual(form["notShown"], form["documents"] - 7)

    def test_the_filled_block_puts_the_two_extremes_side_by_side(self):
        # `fit` cannot see a value split — the words a filled-in sheet adds sit below the mask floor —
        # so this block is chosen by how much was typed in instead, and shows both ends.
        self.session.run(REVIEW, "build_review.py", "--random", "2", "--suspect", "0", "--filled", "2")
        form = self.session.read("REVIEW.json")["forms"][0]
        filled = [s for s in form["samples"] if s["block"] == "filled"]
        self.assertEqual(len(filled), 2)
        self.assertLess(min(s["filled"] for s in filled), max(s["filled"] for s in filled))

    def test_the_form_carries_its_name_to_the_page(self):
        self.session.run(REVIEW, "build_review.py")
        form = self.session.read("REVIEW.json")["forms"][0]
        self.assertEqual(form["title"], "Supplier Change Form")
        self.assertEqual(form["documents"], 12)

    def test_the_page_is_one_self_contained_file(self):
        self.session.run(REVIEW, "build_review.py")
        result = self.session.run(REVIEW, "render_review.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        page = (Path(self.directory.name) / "review.html").read_text(encoding="utf-8")
        self.assertNotIn("__DATA__", page)
        self.assertIn('id="payload"', page)
        for hook in ('id="forms"', 'id="submit"', "form-review"):
            self.assertIn(hook, page)
        # A JSON block inside a script tag ends at the first `<` that starts a closing tag, whatever the
        # quoting around it, so a file name holding one would truncate the page's data silently.
        embedded = page.split('type="application/json">', 1)[1].split("</script>", 1)[0]
        self.assertNotIn("<", embedded)
        self.assertEqual(json.loads(embedded.replace("\\u003c", "<"))["shown"],
                         self.session.read("REVIEW.json")["shown"])


class VerdictTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.session = Session(self.directory.name, [
            (f"sha{n:03d}", (WITH_REMOVAL if n % 2 else PLAIN).format(who=f"S{n}", what=f"M{n}"))
            for n in range(12)])
        self.session.run(REVIEW, "build_review.py")

    def test_a_pasted_verdict_becomes_data(self):
        note = self.session.paste(verdict(["sha001.pdf"]))
        result = self.session.run(REVIEW, "read_verdict.py", note)
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = self.session.read("REVIEW_RESULT.json")["forms"][0]
        self.assertEqual(parsed["marked"], ["sha001.pdf"])
        self.assertEqual(parsed["grouping"], "ok")

    def test_a_paste_with_no_machine_readable_block_is_refused(self):
        note = self.session.paste("I looked at them and they seemed fine.")
        result = self.session.run(REVIEW, "read_verdict.py", note)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("form-review", result.stdout + result.stderr)

    def test_a_verdict_naming_a_form_that_was_not_reviewed_is_refused(self):
        note = self.session.paste(verdict([]).replace("f01", "f77"))
        result = self.session.run(REVIEW, "read_verdict.py", note)
        self.assertNotEqual(result.returncode, 0)


class RepairTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        # Half the form's members carry wording the other half lack, so the marks are separable.
        self.session = Session(self.directory.name, [
            (f"sha{n:03d}", (WITH_REMOVAL if n % 2 else PLAIN).format(who=f"S{n}", what=f"M{n}"))
            for n in range(12)])
        self.session.run(REVIEW, "build_review.py")

    def mark(self, names, **fields):
        note = self.session.paste(verdict(names, **fields))
        self.session.run(REVIEW, "read_verdict.py", note)

    def test_marks_that_separate_become_a_rule_rather_than_a_code_change(self):
        odd = [f"sha{n:03d}.pdf" for n in range(1, 12, 2)]
        self.mark(odd, grouping="mixed", shown=12)
        result = self.session.run(GROUPING, "apply_marks.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        rules = self.session.read("SPLIT_RULES.json")["rules"]
        self.assertEqual(rules[0]["form"], "f01")
        self.assertIn("REMOVAL", rules[0]["wording"])

    def test_marks_that_separate_nothing_dissolve_the_form(self):
        # Nothing in the wording tells these apart, so no rule can be honest about why they differ.
        # Dissolving returns them to being read one at a time, which is where the loop must end.
        self.mark([f"sha{n:03d}.pdf" for n in (0, 2, 5, 7)], grouping="mixed", shown=12)
        self.session.run(GROUPING, "apply_marks.py")
        outcome = self.session.read("SPLIT_RULES.json")
        self.assertEqual(outcome["rules"], [])
        self.assertIn("f01", outcome["dissolved"])
        self.assertEqual(len(outcome["readOneAtATime"]), 12)

    def test_a_form_split_by_value_holds_and_is_read_one_document_at_a_time(self):
        # Not a grouping mistake: the members are the same stationery, and what the app calls them
        # differs by what was typed in. So no rule, no dissolve, and the form survives intact.
        self.mark([], grouping="split", shown=12,
                  splits_into="Product Specification where the results column is blank, "
                              "Certificate of Analysis where it is filled")
        result = self.session.run(GROUPING, "apply_marks.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        outcome = self.session.read("SPLIT_RULES.json")
        self.assertEqual(outcome["rules"], [])
        self.assertEqual(outcome["dissolved"], [])
        self.assertEqual(outcome["readOneAtATime"], [])
        self.assertEqual(outcome["splitByValue"][0]["form"], "f01")
        self.assertEqual(outcome["splitByValue"][0]["documents"], 12)
        self.assertIn("results column", outcome["splitByValue"][0]["splitsInto"])

    def test_a_form_with_few_marks_is_left_alone(self):
        self.mark(["sha001.pdf"], grouping="ok", shown=12)
        self.session.run(GROUPING, "apply_marks.py")
        outcome = self.session.read("SPLIT_RULES.json")
        self.assertEqual(outcome["rules"], [])
        self.assertEqual(outcome["dissolved"], [])
        # The one marked document still has to leave the form it does not belong to.
        self.assertEqual(outcome["readOneAtATime"], ["sha001"])


if __name__ == "__main__":
    unittest.main()
