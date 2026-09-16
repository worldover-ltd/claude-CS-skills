"""A safety data sheet is not where a composition comes from, and what it is still good for.

An SDS section 3 is a hazard disclosure. Under CLP it names the substances that carry a classification
above their cut-off and nothing else, so a sheet can be complete, correct and still omit the water, the
solvent and every ingredient that happens not to be hazardous. A composition read off one is a
composition with holes in it, and the holes do not announce themselves.

So an SDS never becomes the single source. It is still the best CAS and EC register in the folder — the
regulation makes it print them — and those travel to the reader as reference, under a name that says
where they came from.

Measured on 3,771 files a classification run called SDS and 639 it called Composition: the rule here
catches 96.2% of the sheets and wrongly bans 1.9% of the compositions.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/extract-composition-from-documents/lib"
sys.path.insert(0, str(LIB))

import plan_readings  # noqa: E402
import signals  # noqa: E402

SHEET = """SAFETY DATA SHEET
according to Regulation (EC) No. 1907/2006

SECTION 1: Identification of the substance
SECTION 3: Composition/information on ingredients
| Name | CAS | % |
| --- | --- | --- |
| Sodium laureth sulfate | 9004-82-4 | 30 - 70 |
"""

STATEMENT = """UNIVERSAL Composition statement

Composition breakdown for LC581
| INCI name | CAS | % |
| --- | --- | --- |
| Aqua | 7732-18-5 | 68.0 |
| Glycerin | 56-81-5 | 32.0 |
"""

DOSSIER = """COSMETICS INFORMATION DOSSIER
TRADE Name: euxyl k 701 preservative

The safety data sheet is available on request.

COMPOSITION
| Component | CAS | % |
| --- | --- | --- |
| Phenoxyethanol | 122-99-6 | 75.0 |
"""


class WhatCountsAsASafetyDataSheet(unittest.TestCase):
    def test_a_sheet_that_titles_itself_one(self):
        self.assertTrue(signals.looks_like_sds(SHEET, "G0002 English.pdf"))

    def test_a_file_the_customer_named_for_one(self):
        self.assertTrue(signals.looks_like_sds("scanned, no text layer", "G0525 MSDS Engels.pdf"))

    def test_the_dutch_and_german_names(self):
        for name in ("G0540 VIB Nederlands.pdf", "SDB Deutsch.pdf", "Veiligheidsinformatieblad.pdf"):
            self.assertTrue(signals.looks_like_sds("", name), name)

    def test_a_composition_statement_is_not_one(self):
        self.assertFalse(signals.looks_like_sds(STATEMENT, "LC581 Composition statement.pdf"))

    def test_a_dossier_that_merely_mentions_a_sheet_is_not_one(self):
        """The phrase appears, inside a sentence saying the sheet is somewhere else."""
        self.assertFalse(signals.looks_like_sds(DOSSIER, "CID - euxyl k 701.pdf"))

    def test_the_title_has_to_be_near_the_top(self):
        buried = ("filler\n" * 900) + "SAFETY DATA SHEET\n"
        self.assertFalse(signals.looks_like_sds(buried, "Composition breakdown.pdf"))

    def test_a_sentence_carrying_the_phrase_is_not_a_title(self):
        line = "Please consult the safety data sheet of this product before handling the material.\n"
        self.assertFalse(signals.looks_like_sds(line + STATEMENT, "breakdown.pdf"))


class WhatAnSdsIsStillGoodFor(unittest.TestCase):
    """Banned as a source, kept as a register. The regulation makes it print every CAS it names."""

    def test_its_codes_are_still_read(self):
        found = plan_readings.reference_codes(SHEET)
        self.assertIn("9004-82-4", found["cas"])

    def test_a_sheet_with_no_codes_returns_empty_lists(self):
        found = plan_readings.reference_codes("SAFETY DATA SHEET\nno numbers here\n")
        self.assertEqual(found, {"cas": [], "ec": []})


if __name__ == "__main__":
    unittest.main()
