# Documents are grouped by form before they are named

A script groups the folder's documents by the wording printed on them, an agent names each *form* once,
and a person confirms the forms — all before any document is matched against the app's document templates.

Two runs over one customer folder disagreed about 82% of its documents, and the two causes were the same
shape. Every check the pipeline had was **per reading**: nothing ever compared one document to another. So
sixty-eight documents printed on one form came back as forty-four Product Specifications, twenty-two
Certificates of Analysis and two Technical Data Sheets — spread over twenty-five batches whose answers
were each internally consistent, meaning the type was a property of the agent rather than of the document.
And 1,113 answers carried a form number in their own evidence — a name for the document in the customer's
vocabulary that the app's list did not hold. Every one was filed under a list template anyway, 1,016 of
them as `Questionnaire`. (Both figures were re-derived from the run artefacts on 2026-08-14. This ADR
first said "1,113 documents named a form the list did not contain… 979 of them as `Questionnaire`": 1,113
counts form numbers rather than out-of-list type names, which is 343, and the Questionnaire count was
under by 37.)

Neither is fixable one document at a time. A form is the unit that makes them visible: two copies of one
form cannot receive different answers if the form is what gets answered, and a form of 1,211 documents
that fits nothing in the app is one obvious question instead of 1,211 quiet wrong picks.

## What a form is compared on

The signature is the set of words a document shares with the folder — everything typed into it appears on
too few documents to survive, so what is left is the stationery. Two documents are one form when they
share enough of it.

An unordered set, deliberately, and this was measured rather than assumed. OCR reads a skewed scan in a
different order each time, so anything carrying order compares the scanner rather than the form. On 1,887
real documents, taking the 5th percentile of same-form pairs against the 95th percentile of different-form
pairs:

| what is compared | same form | different form | headroom |
| --- | ---: | ---: | ---: |
| the words, as a set | 46% | 18% | **+28** |
| the masked lines, as a set | 27% | 13% | +15 |
| runs of three masked tokens | 12% | 7% | +5 |
| runs of three, header left verbatim | 9% | 6% | +3 |

## What an agent is shown

Not the signature — a naming agent reads the **structure view**: the document's own text, in order, with
everything the form does not repeat blanked out. Two things separate it from the signature, and both were
found by trying the obvious thing first.

The words kept are counted **inside the form**, not across the folder. A folder that is mostly one form
calibrates a folder-wide floor to that form and blanks every other one: at 2.5% of 1,887 documents, the
title of a 68-document form was cut and a supplier's name survived. Counted inside its own form, the title
is kept on 36 of 68 members and the supplier drops out at 4.

The header block is never blanked. It holds the title, which is the most useful line for naming and the
most likely to be rare.

## Consequences

- **Grouping happens before naming, and naming before classification.** Not a preference — the structure
  view cannot be built until the form exists to count inside.
- **~~It costs slightly more, not less.~~** *Superseded by ADR-0005.* This said the classification step
  still reads every document, so one real folder went from 122 agent calls to about 136. Measurement since
  says the opposite: a form is classified once and its answer carried to its members, which took the same
  folder to 84 readings. The case this bullet was protecting — documents that share stationery exactly and
  differ only in what was typed in — is real, and ADR-0005 handles it as a declared exception rather than
  by paying for it everywhere.
- **A wrong form is a systemic error**, so the person's confirmation is not optional. There is no ground
  truth in a real run — nobody knows which documents share a form until somebody looks — so the review is
  the only calibration the thresholds ever get.
- **The failure rate is counted from a fair sample only.** The page also shows the least convincing
  members, because that is where a mistake hides, but counting those would make a good form look bad and
  a better sampling algorithm look worse.
- **Feedback is data, never code.** A person's marks become wording rules in `SPLIT_RULES.json` that the
  unchanged script reads. An agent editing the grouping script per customer is what the run this came out
  of actually did, and it removed every guard the pipeline had.
- **A form names one document template**, unless a person marks it *split by value* — same stationery,
  different documents, because the difference was typed in. Such a form is not repaired and does not
  dissolve; its documents are read one at a time. See ADR-0005.
- **Where no wording separates the marks, the form dissolves** and its documents are read one at a time,
  which is how this skill behaved before grouping existed. That is the loop's exit and it always
  terminates. It is also right more often than it sounds: on this folder the one genuinely contested form
  had no separating wording, because the disagreement was about what to call it.
- **Below about forty documents the step is skipped and says so.** "A word most documents share" means
  nothing in a small folder, and inventing forms out of noise is worse than reading forty documents.
