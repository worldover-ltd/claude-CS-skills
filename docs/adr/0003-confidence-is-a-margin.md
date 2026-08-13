# Confidence is a margin, not a legibility score

`confidence` is the gap between the best-fitting *document template* and the runner-up, and the runner-up's
id comes back with it. It is not how clearly the document announces itself.

The first scale scored legibility: 0.9 and up when the document named itself on its face. That measured the
wrong thing. In the only real run there is, 1,081 documents were read twice and disagreed, and the
disagreements clustered on pairs — technical data sheet against specification, dossier against composition
statement — where *both* templates fit and the document announces itself perfectly well as either. Those
documents scored high, passed the floor, and were settled by merge order. A margin score puts them under
the floor by construction, which is where the re-read and the review list can reach them.

## Consequences

- The floor now means "two templates fit" rather than "the document was hard to read", so more documents
  fall under it than before. The collector reports the count for approval rather than fanning out a re-read
  on its own.
- A document nothing fits scores low for a different reason — no best fit rather than two — and is told
  apart by carrying no template at all rather than by its score.
- No customer's taxonomy is written into the skill. The pairs that are confusable are whatever this app's
  own template list makes confusable, and the classifier discovers them per document.
