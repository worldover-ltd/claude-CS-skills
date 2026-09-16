# A reading can say what it could not carry

A *composition reading* returns, beside its rows, a list of *withheld rows*: rows it saw on the page and
could not transcribe, each with what the page prints and why. A withheld row reaches no figure on the
workbook and blocks nothing.

It relaxes no check. The four checks in `collect_compositions.py` are unchanged, and a material that
fails any of them still carries no rows at all.

## Why

Blocking the whole material rather than the offending row is deliberate, and `docs/adr/0009` is why: a
composition with one row quietly dropped still looks like a composition and still sums near enough to
100 that nobody asks.

That severity has a price, and the price is silence. A reader facing a row it cannot quite carry is
choosing between one row failing and *every* row failing, so the cheapest safe move is to leave the
doubtful row out — and an answer with rows missing is indistinguishable from a complete one. It is the
one error in this run that nothing downstream can see.

It happened. On a real fragrance material the page printed **18 rows and the answer carried 4**. The four
were correct, quoted and verified. Nobody knew until the user asked an unrelated question about CAS
numbers, an audit went looking, and a re-read brought the run from 21 rows to 35. Seven other materials
were never audited.

The cause was the same cell the ban on whole-cell checking now fixes — a CAS column naming three isomers
— but fixing that removes one reason to withhold, not the incentive. Any row a reader doubts still costs
the whole material, so long as saying nothing is free.

So saying something is made free. A withheld row cannot be wrong in the way a carried row can, because
it carries nothing; refusing one would only teach a reader to go back to silence.

## What was tried instead, and cut

Withholding depends on the reader choosing to speak. The obvious backstop for one that does not is to
count: how many rows does the page appear to hold, against how many came back? It was built, measured
against the eight verified compositions of the run above, and **flagged all eight**.

The ratio cannot be made to work. R136 carries one row off a forty-six-line page because kaolin is one
substance, and R157 one off thirty-two for the same reason — both correct, both indistinguishable by
count from a reader that gave up. Narrowing what counts as a row-shaped line does not help: a
composition sits among property tables, hazard tables, footers and phone numbers, and
`signals.read_text` appends the `pdfplumber` tables to the conversion, so the composition itself is
counted twice wherever both extractors find it.

A warning that fires on every material is worse than no warning, so there is none. What might work is
contiguity rather than proportion — a reader that quotes rows 1, 2, 3 and 17 of one table block has
visibly skipped the middle — and that is a different mechanism, not a threshold to tune.

## Consequences

- **A material can carry a composition and still owe somebody a look.** `owed.py` decides what, and the
  workbook's issues tab and the review card both read it, so the two cannot disagree about one run.
- **Withheld rows are checked and never refused.** The line a withheld row names is held against the
  document and the answer recorded, so a reader inventing rows it claims it could not carry is as
  visible as one inventing rows it did.
- **Nothing catches a reader that stays silent.** Withholding is voluntary, and the count that would
  have backed it up does not work. This buys honesty from a reader that wants to be honest and nothing
  at all from one that does not.
- **A cautious reader can withhold everything and pass.** Nothing forces a row into `rows` rather than
  `withheld`. What makes that unlikely rather than impossible is that withholding is visible and
  tedious, and a run whose materials all withhold everything looks exactly as wrong as it is.
- **A withheld row is not an *exception*.** An exception is a *file* the run could not turn into an
  *attachment*; this is a row inside a document that was read. Same shape — a reason in the words of
  the step that found it, and somebody's next action — one level down.
