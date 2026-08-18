# Nobody confirms the forms

A run groups the documents by *form*, names each form, holds the names against the app's list, and
classifies them. It no longer puts the forms in front of a person. The step that published a page of
samples and took one judgement per document is gone.

The reason is the page: confirming a grouping was the one thing this skill published an artifact to do,
and that is not what the run should be spending a publish on. Nothing else about the grouping changed.

## What this costs, in the words of the ADRs it contradicts

ADR-0004 said the confirmation "is not optional", because "there is no ground truth in a real run — nobody
knows which documents share a form until somebody looks — so the review is the only calibration the
thresholds ever get." That is still true, and now nothing calibrates them. The floor of 2.5% and the
threshold of 0.55 are what one folder measured, carried to every folder after it. `--sweep` reports what
other settings would do, but it reports *shape* — how many forms, how large the biggest — never accuracy,
because accuracy needs somebody to look.

ADR-0005 called the review load-bearing three times over: the only calibration, the only control on
whether a form's name led its own classification, and the only place a *split by value* could be declared.
All three go with it. Concretely, on the folder both real runs used, 98.4% of documents landed in a form
whose members all turned out to be one type — the remaining 1.6% is now unchallenged, and the one form
holding 45 Product Specifications beside 23 Certificates of Analysis would be answered once, as whichever
of the two the agent picked.

## What still catches something

- **The vocabulary gate** (Step 8) is untouched, and it is the check that mattered most on real data: three
  forms carrying 1,808 of 1,887 documents that the app had no template for, every one of which had
  previously been filed under the nearest name.
- **`compare_answers.py`** still sets the per-document answers against each other.
- **The workbook artifact** (Step 12) still goes to the user before anything is built, carrying the
  templates actually used with a count each and the lowest-confidence rows. It is now the only place a
  person sees what the grouping did.

## Consequences

- **`SPLIT_RULES.json` is still read by every step that read it before.** A form can be dissolved, split on
  wording, or marked *split by value* by writing that file by hand. A run never writes one.
- **The grouping settings are now defaults rather than findings.** Any change to them is a change made
  blind, so leave them where the measurement put them unless a new measurement moves them.
- **The review machinery is kept whole, not deleted.** `references/REVIEWING_BY_EYE.md`, `lib/review/` and
  `assets/review/` still describe and build a page that takes one judgement per document over any pile.
  The next thing this skill needs eyes on starts from them rather than from nothing.
