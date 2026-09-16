# A composition comes from one document

A raw material's composition is taken whole from a single document that states it — ingredient names,
quantities, and the codes beside them. Where no one document states it, the material has no composition
and the run says so on `MATERIALS_WITH_ISSUES`.

The alternative is obvious and wrong: take the percentages from the safety data sheet, the INCI names
from the technical data sheet, the CAS numbers from the regulatory letter, and assemble the best
composition the folder can support. It produces an answer for more materials, each row carrying a
citation, and it is what a careful person does by hand.

## What it costs, measured on the run this came from

Two materials of twenty-six were being assembled from several documents, and both were wrong in a way
that reads as right.

**R117** carried three rows. Ethanol at 95-100% and a balance line came from the product's own safety
data sheet, which states its composition in two lines. The third row — tertiary butyl alcohol at 0.25% —
came from the supplier's denaturant table, a document that defines what the *grade* "F4" means. The
product's own sheet says the denaturants "may be one or more of" six substances and caps them together
at 1.0%, identifying none of them. So the run published a figure the product's documentation does not
contain, against an ingredient its documentation does not name, and the row looked exactly like the two
beside it.

**R164** carried four rows taken from three documents, with a fourth marked primary on the reference
sheet. Its percentages were ranges — 64-72, 22-26, 2.2-2.8 — that no document states. The one sheet that
carries the whole composition gives single figures summing to 100: 70, 23, 4.5, 2.5. The ranges were
somebody's tolerance around figures they had already found.

Adopting the rule cost the TBA figure, which is real information: the drum is denatured, and 0.25% is
probably right. It is now absent from the workbook, and the reference sheet says which document has it.

## Why not allow it with a citation per row

Because the citation does not survive contact with the question people actually ask. The R117 row
carried its source in a note, and the note said, accurately, that the denaturant table "is the document
that pins which one and how much" — an argument for the stitch, written by the run that made it. Nobody
reading the workbook would have questioned it. The check that catches this is not a better citation
format, it is the absence of the seam.

It also costs the thing that makes the run checkable at all. With one document per composition, the
review page can put the table beside the page it came from and a person can compare them in one glance.
A stitched composition has no such page, and reviewing it means opening three files.

## Why not fall back to stitching where nothing else works

Because the fallback fires exactly where the evidence is weakest, and produces its most confident-looking
output there. A material whose folder holds no composition is a material whose supplier has not sent
one — a document to request. Presented as a partial composition, it becomes a thing nobody asks about
again.

## Consequences

- Materials will have no composition, and the count matters: the run reports them by name with the
  candidates it considered, so the absence is a task rather than a silence.
- The reference sheet records every candidate and why it lost, because "why this file and not that one"
  is the first question the rule provokes.
- A user who disagrees writes a **recut** naming the file the composition should come from, and the run
  re-reads it. The rows still come from a sub agent and are still checked against the document — a recut
  changes which document is authoritative, never what it says.
- Where two documents each state a full composition, the rule does not help and recency decides. That
  brings its own trap, which is why the run records the *kind* of date a document prints: a review that
  changed nothing does not make a sheet newer than the content it restates.
