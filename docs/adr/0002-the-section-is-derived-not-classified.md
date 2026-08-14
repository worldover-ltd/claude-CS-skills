# The section is derived, not classified

The classifier picks a *document template* and nothing else. Which *section* the document lands in is
looked up afterwards, in code, from the *item template* each copy's item is on.

Asking a model for the section was asking it to perform a join it had already been given the answer to —
"pick the section that lists your chosen template id" is a lookup, not a judgement. Two of the collector's
failure categories, `bad_section` and `unarranged`, existed only to catch a model getting that lookup
wrong. Deriving it retires both, and it is what makes ADR-0001 possible: one reading can cover copies on
several item templates, each needing a different section, so the section cannot travel with the answer.

## Amended: a step at the end may arrange what the app has not

The rule above holds and is not weakened: **the classifier is still never asked about sections.** What
changed is what happens to the documents the lookup finds no home for.

Measured on a real export, that is most of them. The app held 5 sections across 3 item templates, and 68
of 82 template rows had no section at all — including the one carrying 445 documents. So "the app owner is
told a section attachment is missing" turned out to mean handing somebody a list of 68 gaps.

A separate step now runs **after every document has a template**, over the distinct (document template,
item template) pairs the run produced — 58 of them behind 2,163 rows on that folder. It opens no file and
reads no extracted text; the whole question is answerable from rows the run has already written. It picks
an existing section where one holds the template, and names a new one where none does.

This is a different decision from classification and is kept apart from it deliberately: arranging a
customer's Documents tab is a layout choice, so what comes back is marked `is_new` on the workbook's
reference sheets and read there by the person whose app it is.

## Consequences

- Where no section on that item template holds the chosen template, the row still attaches with a null
  section and the app owner is told a section attachment is missing. That was already the rule; it is now
  the only way to reach it.
- **The section step may not move a template the app already arranges.** Where its answer disagrees with
  an existing arrangement, the app's own wins and the disagreement is reported. Rearranging a Documents
  tab in use is a bigger decision than this step is entitled to take quietly.
- The classifier is asked about sections **not at all**, not even to propose one. It is shown no section
  list — one reading spans item templates, which is the whole reason sections left the payload — so any
  name it offered would be a guess against a vocabulary it cannot see. Where no section renders the chosen
  template, the collector reports the sections that item template *does* have and somebody arranges one in
  the app. A list to pick from beats a name to evaluate.
- Where more than one section holds the template, the first by the app's own `sortOrder` wins. Any of them
  renders the document, so there is nothing for a judgement to improve.
