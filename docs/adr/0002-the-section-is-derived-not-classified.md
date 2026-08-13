# The section is derived, not classified

The classifier picks a *document template* and nothing else. Which *section* the document lands in is
looked up afterwards, in code, from the *item template* each copy's item is on.

Asking a model for the section was asking it to perform a join it had already been given the answer to —
"pick the section that lists your chosen template id" is a lookup, not a judgement. Two of the collector's
failure categories, `bad_section` and `unarranged`, existed only to catch a model getting that lookup
wrong. Deriving it retires both, and it is what makes ADR-0001 possible: one reading can cover copies on
several item templates, each needing a different section, so the section cannot travel with the answer.

## Consequences

- Where no section on that item template holds the chosen template, the row still attaches with a null
  section and the app owner is told a section attachment is missing. That was already the rule; it is now
  the only way to reach it.
- The classifier is asked about sections **not at all**, not even to propose one. It is shown no section
  list — one reading spans item templates, which is the whole reason sections left the payload — so any
  name it offered would be a guess against a vocabulary it cannot see. Where no section renders the chosen
  template, the collector reports the sections that item template *does* have and somebody arranges one in
  the app. A list to pick from beats a name to evaluate.
- Where more than one section holds the template, the first by the app's own `sortOrder` wins. Any of them
  renders the document, so there is nothing for a judgement to improve.
