# Reading a composition

What the fan-out sends, what comes back, and the judgements the sub agent is being asked for. The agent
itself is `agents/composition-reader.md`, which carries its own tools and model — this is what the
skill's step needs to know to send it.

## The wave

One agent per material, every task in one wave. Send them **in a single message with one `Agent` call
per task** — calls in separate messages run one after another. More than twenty materials goes in waves
of twenty.

```
Agent(subagent_type: "composition-reader",
      prompt: "Read <session>/readings/R289.json and write your answer to <session>/read/R289.json.
               Follow the format in your instructions exactly.")
```

One material per agent rather than several. Batching saves calls and invites the one failure that is
invisible afterwards: an ingredient from one product landing in another product's table.

## What a composition is

A table listing what the material is made of, with a quantity against each component. Usually titled,
usually summing to about 100, usually carrying CAS numbers.

These are compositions:

- an SDS **section 3** that lists every component, including the water
- a supplier's **composition statement** or **composition breakdown** letter
- a **product data record** with a composition table
- a food **Product Information Form**'s ingredient declaration
- an **overview letter** whose product information table gives a quantity

These are not, however much they look like one:

- a **hazard-band list**. An SDS section 3 that gives `≥ 30 - < 70` and names only the classified
  components is answering a different question. On one real material it named methanol at 0.3-0.5%,
  which appeared in no other document, and omitted both the water and the butylene glycol.
- a **specification**. `Assay 47.4% min` is a limit the batch must meet, not a statement of what is in
  the drum beside it.
- a **certificate of analysis**. What one batch measured.
- a **grade definition**. A table saying what "F4" means — ethanol denatured with 0.25% TBA — describes
  the grade, not this drum. The material's own SDS named six possible denaturants and capped them
  together at 1.0%, identifying none of them.
- a **technical data sheet** with only use levels and properties.

The agent decides which of these it is holding. That is the judgement it is there for: the shortlist is
built by a script scoring words, and the words are nearly identical across all of them.

## Which one, where several qualify

The most recent — but recency is a property of the **content**, not of the stamp on the page:

- a **print date** is when somebody pressed print. One folder's sheet carries `Issue Date: 29/11/2021`
  beside `Print Date: 30/05/2023`.
- a **review with no changes** does not age a document forward. One sheet stamped 2025 reads
  `Version: 02 Mandatory Review - no changes to SDS` over content last edited in 2020; the
  manufacturer's own 2023 sheet was the newer document.
- a **superseded** marker ages it backwards.

So the agent returns the date *and its kind*, and `plan_readings.py` puts every date the file prints in
front of it with the label the document used. Ranking on the largest number on the page picks the wrong
document in both cases above.

Several suppliers under one material code is normal — a code's folder can hold four suppliers' sheets
for the same INCI. The most recent qualifying document wins regardless of which supplier it came from,
and the review page lists every folder the candidates came from so the choice is visible.

## What comes back, and what is checked

The answer's shape is in the agent's own instructions — `min` and `max` only where the document gives
figures, so a balance row carries neither and its quoted line carries the word. Four things are checked
by
`collect_compositions.py` before any of it counts, and failing any one carries the whole material to
`MATERIALS_WITH_ISSUES` with no rows:

| checked | why |
| --- | --- |
| the file named is one it was shown | an answer about a file nobody gave it is an answer about nothing |
| every row's quoted line is in that file | the only thing separating a transcription from a fabrication |
| every CAS and EC passes its check digit and is printed in the file | a model knows glycerin is 56-81-5 whether or not the page says so |
| the reported date is printed in the file | the date decides which document wins |

The quotation check runs the five tiers of `verbatim.py`, so a line the agent stitched together from a
heading and the cell beside it still passes — the words are the document's, only the line is the
agent's. An invented line passes none of them.

**The whole material is blocked, not the offending row.** A composition with one row quietly dropped
still looks like a composition, and still sums close enough to 100 that nobody asks.

## When the run picked wrong

Write a recut and replay it — see `apply_recut.py`. It narrows that material's task to the file you
name and clears the old answer, so the next wave reads the right document and the rows are checked
exactly as before. Correcting rows in the workbook instead leaves values nothing verified, and a rebuild
loses them.
