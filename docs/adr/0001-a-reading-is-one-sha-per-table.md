# A reading is one sha per table

A folder of documents holds a great many copies: on the first real customer's folder, 8,082 files shared
content across 2,173 distinct hashes. Classifying per file spends about a quarter of the reading budget on
byte-identical content, and — because two readings of one document can differ — writes workbook rows that
carry the same `file_sha` and different `document_template`, which the upload screen has no way to
reconcile. So the unit sent to a classifier is one *reading*: one sha per *item kind*, fanned back out to
every file that shares it.

The key is `(sha, table)` rather than sha alone because the closed list a document is picked from is the
one the app permits on that table. The same PDF filed under a raw material and under a product is picked
from two different lists and is genuinely two readings.

## Consequences

- `folderHint` is per file, and a reading covers several. Every distinct hint in the group is passed, since
  copies filed under differently-named folders disagreeing about what a document is counts as evidence.
- A document's *section* can no longer come back with the answer: sections belong to the *item template*,
  and one reading can cover copies on several. See ADR-0002.
- The classifier no longer echoes a path back, so the answer joins on the reading id rather than on a file
  name a model has an incentive to tidy. This retires a real failure: 18 answers in the first run came back
  with the name normalised and silently failed to match.
