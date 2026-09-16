# The conversation holds no data

A run's conversation launches passes, reports what they print, and asks the questions a *step* owes the
user. It never takes a data file into itself. Where something must be read — a manifest, a spreadsheet, a
folder listing, a document — it is read by a script that prints counts and anomalies, or by a sub agent
that reports a short answer.

The reason is arithmetic rather than taste. A conversation re-reads everything it holds on every turn, so
a file taken in at turn 100 is paid for again on turns 101 through the end. Measured on the 17,117-document
run of 2026-08-31: 1,844 turns carrying 353,000 tokens on average, **$1,348 of a $1,463 run**. The sub
agents cost **$114**, of which the classifier itself was $60. Coordination cost twelve times the work it
coordinated.

Five `Read` calls were 426,538 tokens — **57% of everything the conversation ever took in**. Every one was
a file a script could have summarised in twenty lines. By contrast the 342 sub agent calls returned 279
tokens each, because a sub agent's brief already says to report rather than recite; that half of the design
was right and is unchanged.

## Consequences

- **Nothing sees the data end to end any more.** A script that produces plausible but wrong counts has one
  fewer reader before a workbook is built. Passes therefore report anomalies — batches that answered for
  nobody, documents that matched nothing — and not only totals, because a total cannot look wrong.
- **A conversation that holds no state can be thrown away**, which is what makes compacting at step
  boundaries safe. Left alone a run compacts only when nearly full — four times on the measured run, twice
  of them after context had passed half a million tokens. Compacting at the boundaries instead costs less
  than half as much.
- **It stops being worth the most capable model.** A conversation that routes and relays is not exercising
  judgement; that lives in the steps where a person answers something. A run costs about five times less
  on a mid-sized model than on the largest one, for identical answers.
- **A pass that has nothing to print has to grow something to print.** That is a cost, and it is the same
  cost as ADR-0006 — a pass reporting in the user's words — so the two are paid for once.
