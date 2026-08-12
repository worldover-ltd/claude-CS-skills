# Classifying the documents

How Step 6 turns a folder of extracted documents into one document template, one section, a confidence and
a line of evidence per document. `plan_batches.py` has already written the batch input files; this page is
what to do with them.

## The shape of the fan-out

**Twenty documents per batch, up to twenty batches at once.** One sub agent per batch, so a folder of 400
documents is one wave. Send the whole wave **in a single message with one `Agent` call per batch** — calls
in separate messages run one after another. More than twenty batches goes in waves of twenty.

**Each sub agent is given one file path, not twenty.** Its batch input file already holds the vocabulary,
the documents, and what to read for each — so the prompt stays the same length whatever the batch holds,
and the agent reads the list rather than being told it. A prompt carrying twenty paths spends its context
on a list it has to keep straight; a prompt carrying one path spends it on the documents.

**Run them on `claude-haiku-4-5`.** Picking a document's type from a closed list is high-volume and
mechanical — the cheapest, fastest model is the right one, at $1/$5 per million tokens against $3/$15 for
Sonnet 5. Two things follow from the choice: its context window is 200K, the only current model under 1M,
so a batch of long documents is the one thing that can overflow it (drop `--batch-size` if it does), and if
the categories come back poor, the fix is `claude-sonnet-5` on the same prompt before anything else.

## The batch input file

Written by `plan_batches.py`, one per batch, at `.workflow/active/${sessionId}/batches/batch_003.json`:

```json
{
  "batch": 3,
  "vocabulary": {
    "documentTemplates": ["Safety Data Sheet (SDS)", "Certificate of Analysis (CoA)"],
    "sections": {
      "Raw Material": [
        { "label": "Safety", "documentTemplates": ["Safety Data Sheet (SDS)"] },
        { "label": "Quality", "documentTemplates": ["Certificate of Analysis (CoA)"] }
      ]
    }
  },
  "documents": [
    {
      "path": "C:/…/Raw Materials/RM-0142/SDS_2026.pdf",
      "entity": "Raw Material",
      "folderHint": "Safety",
      "readFrom": ["C:/…/extracted/a1b2c3d4_SDS_2026.md"]
    }
  ]
}
```

`readFrom` is the extracted Markdown, the rendered pages of a scan, or the image itself — whatever
`EXTRACTED.json` pointed at for that file. `folderHint` is a folder name that looked like a kind of
document, or `null`; it is a hint and the contents outrank it.

## The prompt

Substitute the batch's input path and its output path. Nothing else changes between batches.

```
Read the JSON file at <batch input path>. It holds a `vocabulary` and a list of `documents`.

For each document in that list:

1. Read the file(s) at its `readFrom` paths. That is the document's contents — extracted Markdown, or
   rendered page images for a scan.
2. Decide which of `vocabulary.documentTemplates` the document is. The list is closed: pick a name from it
   exactly as spelled, or `null` if none of them fits what you read.
3. Decide which section it belongs in, from `vocabulary.sections[<the document's entity>]`. Use the
   section that lists your chosen template; where none does, or you chose no template, pick the section
   whose other templates it sits closest to, or `null` if none is relevant.
4. Score your confidence from 0 to 1: 0.9 and up when the document names itself on its face (a title, a
   header, a form number); 0.7 to 0.9 when its contents make it clear without saying so; below 0.5 when you
   are inferring from something thin. Score what you actually found — a low score is useful and a wrong
   high score is not.
5. Write one line of evidence: the specific thing you read that decided it, quoting the document where you
   can. "Header reads SAFETY DATA SHEET and section 3 lists hazard classifications" is evidence;
   "appears to be an SDS" is not.

`folderHint` is the folder the document sat in, where that folder looked like a kind of document. Treat it
as a hint only — the contents outrank it. Where they disagree, follow the contents and say so in evidence.

Then write your results to <batch output path> as JSON:

{"results": [{"path": "…", "documentTemplate": "…", "section": "…", "confidence": 0.94, "evidence": "…"}]}

`path` MUST be copied verbatim from the input file — it is what your results are joined on. Return one
entry for EVERY document in the input, including the ones you could not place: those get
`"documentTemplate": null` with evidence saying what you did read. Reply with the count you wrote and
nothing else.
```

The output path is `.workflow/active/${sessionId}/classified/batch_003.json`, matching the input's number.

## The roll call

`collect_classifications.py` is the authority on who answered, and it counts against `BATCHES.json` rather
than against your memory of what you sent. A batch whose output file is missing or short goes out again —
same prompt, same input file — for at most **two further rounds**. Anything still missing after that is
reported as unread and joins the exception pile, named rather than left looking classified.

This is the whole reason the fan-out is trustworthy, so it is a count you actually make: run the collector
after every round and read its roll call before moving on.

## What comes back needing a person

Three kinds, and the collector lists each:

- **No template** — the contents did not match anything in the closed list. Often a document type the app
  does not have yet, which is worth telling the user, since somebody has to create it before the migration
  runs.
- **Below the confidence floor** (0.7 by default; `--floor` moves it) — classified, but on thin evidence.
  These are the rows to spot-check, not to discard.
- **Nothing readable** — `plan_batches.py` never batched them, because `EXTRACTED.json` had no contents for
  them. The user describes them or re-saves them.

Take each to the user with its file name, its folder, and the evidence line. That trio is usually enough
for them to answer in one pass.
