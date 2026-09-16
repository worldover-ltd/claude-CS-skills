# A safety data sheet is not a composition

No *composition reading* is taken from a safety data sheet. `score_composition.py` refuses one as a
*candidate* before any agent sees it, a *recut* onto one is refused in those words, and a *material*
whose folder holds nothing else is reported as having no composition.

Its section 3 answers a different question. Under CLP a sheet lists the substances classified above
their cut-off and is complete when it has done so, which means a correct, current, well-made sheet can
omit the water, the solvent and every other ingredient that carries no classification. Read as a
composition it yields one with holes in it, and the holes do not announce themselves: the rows that are
there are real, the CAS numbers check out, and the total is close enough to 100 that nobody asks.

`READING_A_COMPOSITION.md` used to leave this to the agent, permitting *"an SDS section 3 that lists
every component, including the water"* and refusing the hazard-band form. That judgement turns out to
be the one thing the shortlist cannot help with, because the scoring is built to find sheets:
`\bsection\s*3\b` and `information on ingredients` in `signals.HEADING` are the sheet's own headings,
word for word, so a sheet scores higher than anything else in the folder.

And there are more of them than of anything else. On the folder this was measured against, 4,342 files
are sheets against 680 composition statements, and **2,010 of 2,962 materials have a sheet and no
statement**. Left in, the shortlist fills with sheets, every material gets an answer, and the run looks
like it worked.

## What a sheet is still used for

Its CAS and EC numbers. The regulation makes a sheet print an identifier against every substance it
names, so it is the best register in the folder even where its percentages cannot be trusted. Those
reach the reader as `safetyDataSheets` on the task — file name and codes, no text — so a number it
recognises can never arrive looking like a row it may transcribe.

## How a sheet is recognised

Two signals, no model. What the customer named the file (`SDS`, `MSDS`, `VIB`, `SDB`, `FDS`,
`Veiligheidsinformatieblad`), or the sheet's own title standing on a line of its own near the top
rather than quoted inside a sentence — a dossier saying *"the safety data sheet is available on
request"* is not one.

Measured against 3,771 files a classification run called `SDS` and 639 it called `Composition`: **96.2%
of the sheets caught, 1.9% of the compositions wrongly banned.** The file name alone catches 59% and
wrongly bans none; the title takes it the rest of the way.

## Consequences

- **Coverage falls a long way.** Materials with any possible source go from about 92% to about 24% on
  that folder. This is the same bargain `docs/adr/0009` struck for the *single source* and it is paid in
  the same coin: the run says "no composition" far more often, and what it does say is worth reading.
- **2,010 materials are owed a reason, not a shrug.** A folder holding only sheets is a different fact
  from a folder holding nothing composition-shaped — the supplier has been asked for a sheet and never
  for a composition, so there is somebody to ask. Those reach the issues in those words, and the sheets
  are listed on the workbook's reference tab with why they were never in the running.
- **Twelve real compositions in 639 are refused.** Dossiers that print the phrase as a heading over
  their own hazard summary. That asymmetry is deliberate: a composition wrongly refused is a material
  the user is told about by name, and a composition wrongly taken from a sheet is a wrong answer nobody
  ever questions.
- **The rule is a regex, so it is wrong in new ways on a new customer.** It was tuned on one Dutch
  customer's folder, against labels a classification run produced rather than against ground truth. A
  supplier who titles their statement *"Product Safety Data"* is banned; one whose sheet carries no
  title and an unhelpful file name is not.
- **The agent's instructions no longer carry the judgement.** `READING_A_COMPOSITION.md` used to list
  the two SDS forms and ask the agent to tell them apart. It now says a sheet never arrives, which is
  true, and one less thing for a reader to get right.
