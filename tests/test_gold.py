"""The harness that says whether a change to extraction helped, and what it refuses to call evidence.

A label is a fact somebody read off the page: an ingredient, and the figure printed beside it. The score
asks only whether that pair can still be found together in whatever text the extraction produced. Two
renderings of the same fact must score the same; a rendering that has pulled the figure away from its
ingredient must not.
"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/extract-composition-from-documents/lib"
sys.path.insert(0, str(LIB))

import gold  # noqa: E402

LABEL = {
    "document": "dissolvine",
    "confirmed": True,
    "rows": [
        {"ingredient": "Tetrasodium glutamate diacetate", "value": "47.5"},
        {"ingredient": "Aqua/water", "value": "balance"},
    ],
}

GOOD = """SECTION 3 Composition
| INCI name | CAS | Concentration |
| --- | --- | --- |
| Tetrasodium glutamate diacetate | 51981-21-6 | 47.5-48.0 |
| Aqua/water | 7732-18-5 | balance |
"""


class OneSpellingOfAFact(unittest.TestCase):
    def test_case_and_punctuation_do_not_matter(self):
        self.assertEqual(gold.flatten("Aqua/Water"), gold.flatten("aqua / water"))

    def test_accents_do_not_matter(self):
        self.assertEqual(gold.flatten("Karité"), gold.flatten("Karite"))

    def test_figures_survive_flattening(self):
        self.assertIn("47.5", gold.flatten("47.5-48.0"))

    def test_nothing_flattens_to_nothing(self):
        self.assertEqual(gold.flatten(None), "")


class NearnessIsTheTest(unittest.TestCase):
    def test_a_pair_on_one_row_is_found(self):
        self.assertTrue(gold.found_together(GOOD, "Aqua/water", "balance"))

    def test_a_value_far_from_its_ingredient_is_not_found(self):
        text = "Aqua/water" + (" filler" * 200) + " balance"
        self.assertFalse(gold.found_together(text, "Aqua/water", "balance"))

    def test_an_absent_half_is_not_found(self):
        self.assertFalse(gold.found_together(GOOD, "Glycerin", "5.0"))


class AMatchIsNotPartOfALongerToken(unittest.TestCase):
    """A harness that counts 1.0 inside 21.05 reports rows recovered off text that never stated them."""

    def test_a_figure_inside_a_longer_figure_is_not_a_match(self):
        flat, origins = gold.flatten_with_map("21.05")
        self.assertEqual(gold.positions(flat, gold.flatten("1.0"), origins), [])

    def test_a_range_still_matches_its_own_start(self):
        flat, origins = gold.flatten_with_map("47.5-48.0")
        self.assertEqual(gold.positions(flat, gold.flatten("47.5"), origins), [0])

    def test_an_ingredient_inside_a_longer_word_is_not_a_match(self):
        flat, origins = gold.flatten_with_map("Sodium Alginate-Complex")
        self.assertTrue(gold.positions(flat, gold.flatten("Sodium Alginate"), origins))
        flat, origins = gold.flatten_with_map("Disodium")
        self.assertEqual(gold.positions(flat, gold.flatten("sodium"), origins), [])


class DistanceIsMeasuredWhereItMeans(unittest.TestCase):
    """Flattening collapses punctuation, and a Markdown table is mostly punctuation."""

    def test_a_pipe_padded_gap_is_still_a_gap(self):
        text = "Titanium Dioxide" + " | " * 120 + "98.6"
        self.assertGreater(len(text), 350)
        self.assertLess(len(gold.flatten(text)), 40)
        self.assertFalse(gold.found_together(text, "Titanium Dioxide", "98.6"))

    def test_the_same_pair_on_one_table_row_is_near(self):
        self.assertTrue(gold.found_together("| Titanium Dioxide | 98.6 |", "Titanium Dioxide", "98.6"))

    def test_offsets_come_back_in_the_original_text(self):
        flat, origins = gold.flatten_with_map("aa|||bb")
        self.assertEqual(origins[-1], 6)


class ScoringADocument(unittest.TestCase):
    def test_a_clean_table_recovers_every_row(self):
        result = gold.score(GOOD, LABEL)
        self.assertEqual(result["recovered"], 2)
        self.assertEqual(result["misaligned"], 0)
        self.assertEqual(result["missing"], 0)
        self.assertEqual(result["failures"], [])

    def test_a_collapsed_column_reads_as_misalignment_not_absence(self):
        collapsed = ("Tetrasodium glutamate diacetate Aqua/water" + (" x" * 300) + " 47.5 balance")
        result = gold.score(collapsed, LABEL)
        self.assertEqual(result["recovered"], 0)
        self.assertEqual(result["misaligned"], 2)
        self.assertEqual(result["missing"], 0)

    def test_text_without_the_facts_reads_as_missing(self):
        result = gold.score("SECTION 11 Toxicological information", LABEL)
        self.assertEqual(result["missing"], 2)
        self.assertEqual(result["misaligned"], 0)

    def test_every_failed_row_comes_back_for_a_person_to_look_at(self):
        result = gold.score("nothing here", LABEL)
        self.assertEqual(len(result["failures"]), 2)


class ProposingNeverDestroysAnAfternoonsWork(unittest.TestCase):
    def test_a_confirmed_label_is_left_alone(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            target = folder / "doc.json"
            target.write_text(json.dumps(LABEL), encoding="utf-8")
            record = {"path": "C:/x/doc.pdf", "tablesFound": 1, "tablesFile": str(folder / "t.md")}
            (folder / "t.md").write_text("| A | 1.0 |", encoding="utf-8")
            draft = gold.propose(record, "| A | 1.0 |")
            self.assertFalse(draft["confirmed"])
            self.assertTrue(json.loads(target.read_text(encoding="utf-8"))["confirmed"])


class LabelsNobodyHasCheckedAreKeptApart(unittest.TestCase):
    def test_confirmed_and_draft_are_returned_separately(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "a.json").write_text(json.dumps(LABEL), encoding="utf-8")
            (folder / "b.json").write_text(json.dumps({"rows": []}), encoding="utf-8")
            confirmed, draft = gold.load(folder)
        self.assertEqual([c["document"] for c in confirmed], ["dissolvine"])
        self.assertEqual([d["document"] for d in draft], ["b"])

    def test_a_label_is_named_by_its_file_when_it_does_not_name_itself(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "sds-0142.json").write_text(json.dumps({"confirmed": True, "rows": []}), encoding="utf-8")
            confirmed, _ = gold.load(folder)
        self.assertEqual(confirmed[0]["document"], "sds-0142")


class TheNumberARunIsComparedOn(unittest.TestCase):
    def test_recall_and_misalignment_are_reported_apart(self):
        summary = gold.summarise([
            {"rows": 4, "recovered": 3, "misaligned": 1, "missing": 0},
            {"rows": 4, "recovered": 2, "misaligned": 0, "missing": 2},
        ])
        self.assertEqual(summary["rows"], 8)
        self.assertAlmostEqual(summary["recall"], 5 / 8)
        self.assertAlmostEqual(summary["misalignmentRate"], 1 / 8)

    def test_no_rows_is_not_a_division_by_zero(self):
        summary = gold.summarise([])
        self.assertEqual(summary["recall"], 0.0)
        self.assertEqual(summary["documents"], 0)


if __name__ == "__main__":
    unittest.main()
