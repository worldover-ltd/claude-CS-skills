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
  "fallbackTemplates": "C:/…/skills/upload-documents/references/DOCUMENT_TYPES.txt",
  "vocabulary": {
    "documentTemplates": {
      "raw_materials": [
        { "id": "dt_sds", "name": "Safety Data Sheet (SDS)" },
        { "id": "dt_coa", "name": "Certificate of Analysis (CoA)" }
      ]
    },
    "sections": {
      "Raw Material": [
        { "label": "Safety", "documentTemplates": ["dt_sds"] },
        { "label": "Quality", "documentTemplates": ["dt_coa"] }
      ],
      "Solvent": [{ "label": "Safety", "documentTemplates": ["dt_sds"] }]
    }
  },
  "documents": [
    {
      "path": "C:/…/Raw Materials/RM-0142/SDS_2026.pdf",
      "table": "raw_materials",
      "itemTemplate": "Raw Material",
      "folderHint": "Safety",
      "readFrom": ["C:/…/extracted/a1b2c3d4_SDS_2026.md"]
    }
  ]
}
```

Two keys carry the whole shape, and **both hold only what this batch's own documents can use**.

`documentTemplates` is keyed by **table**, so the closed list a document is picked from is the one the app
allows on *its* table — a `Spec Sheet` the app only permits on products is never offered for a raw
material.

`sections` is keyed by ***item_template***, because a section belongs to the blueprint an item is built
from, and two *item_template*s on one table carry different sections. Only the *item_template*s some
document in the batch actually sits on appear — a table's other blueprints are not the classifier's to
choose from, and every label it is shown is one it could legitimately pick.

**The two lists are scoped differently on purpose.** `for_tables` says which templates the app *permits*
on a table; a section's `documentTemplates` says which it *renders* on one blueprint, and the second is
often narrower. A `Technical Data Sheet` can be allowed on `raw_materials` and sit in no section of the
`Solvent` blueprint at all. The template list stays the table's, because a document either is a Technical
Data Sheet or it is not, and that reading is worth keeping — but the collector then checks the pairing
and reports the ones the app has nowhere to put.

`fallbackTemplates` is a **path, not a list**: around 285 document types across cosmetics, chemicals and
compliance, some 4,000 tokens if read whole. Passing the path keeps that out of every batch's context and
puts it in reach of the batches that actually meet a document the app has no word for.

`readFrom` is the extracted Markdown, the rendered pages of a scan, or the image itself — whatever
`EXTRACTED.json` pointed at for that file. `folderHint` is a folder name that looked like a kind of
document, or `null`; it is a hint and the contents outrank it.

## The prompt

Substitute the batch's input path and its output path. Nothing else changes between batches.

```
Read the JSON file at <batch input path>. It holds a `vocabulary` and a list of `documents`.

For each document in that list:

Every document gets either a **pick** — something the app already has — or a **proposal**. Picking is
always the better answer: a pick attaches on its own, a proposal is work for a person before this document
can land. Propose only what you could not pick.

For each document in that list:

1. Read the file(s) at its `readFrom` paths. That is the document's contents — extracted Markdown, or
   rendered page images for a scan.
2. **Pick the document template** from `vocabulary.documentTemplates[<the document's table>]` — the full
   list of what this kind of item can carry. Return the `id` of the closest fit as `documentTemplateId`,
   copied exactly. Use the list for that document's own table.
3. **Only where nothing in that list is what the document is**, open the file at `fallbackTemplates` and
   find the name that does fit. Return it as `proposedTemplate` with `documentTemplateId` set to `null`.
   That file is a few hundred lines, so open it for the documents that need it rather than up front. Where
   even it holds nothing, write the name yourself in the same field. Where you cannot tell what the
   document is at all, leave both `null` and say what you read in evidence.
4. **Pick the section** from `vocabulary.sections[<the document's itemTemplate>]` — the one that lists
   your chosen template id. Where none lists it but another section is clearly where this document
   belongs, pick that one. Where none fits, return `"section": null`, and add `proposedSection` with a
   label naming the group it should sit in if one is worth creating. A `null` section is a good answer:
   the document still attaches.
5. Score your confidence from 0 to 1: 0.9 and up when the document names itself on its face (a title, a
   header, a form number); 0.7 to 0.9 when its contents make it clear without saying so; below 0.5 when you
   are inferring from something thin. Score what you actually found — a low score is useful and a wrong
   high score is not.
6. Write one line of evidence: the specific thing you read that decided it, quoting the document where you
   can. "Header reads SAFETY DATA SHEET and section 3 lists hazard classifications" is evidence;
   "appears to be an SDS" is not.

`folderHint` is the folder the document sat in, where that folder looked like a kind of document. Treat it
as a hint only — the contents outrank it. Where they disagree, follow the contents and say so in evidence.

Then write your results to <batch output path> as JSON:

{"results": [{"path": "…", "documentTemplateId": "…", "proposedTemplate": null, "section": "…",
              "proposedSection": null, "confidence": 0.94, "evidence": "…"}]}

`path` MUST be copied verbatim from the input file — it is what your results are joined on. Return one
entry for EVERY document in the input, including the ones you could not place. Reply with the count you
wrote and nothing else.
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

- **A proposed template** — the classifier read the document, and the app has no word for it. The
  collector groups these **by proposed name with a count**, because the user's action is creating each
  template once, not settling each document. A name from `DOCUMENT_TYPES.txt` and a name the classifier
  wrote itself arrive the same way; the app has neither.
- **A proposed section** — same shape, grouped by *item_template* and label. Cheaper to act on than a
  template, and often the answer is to leave it: a document with a null section still attaches.
- **No template at all** — not even a proposal, so the classifier could not tell what it read. This is the
  one that needs the user to open the document.
- **A template the app cannot take** — an id that does not exist, or one the app does not allow on that
  document's table. The collector rejects both rather than carrying them into the workbook, since the
  migration would refuse them anyway.
- **A template with no section to render it** — allowed on the table, but arranged into no section of the
  *item_template* this item is on. The reading is kept, since the document really is that type; what is
  missing is a section attachment somebody adds in the app, and until they do the document attaches with
  no home on the item's page.
- **Below the confidence floor** (0.7 by default; `--floor` moves it) — classified, but on thin evidence.
  These are the rows to spot-check, not to discard.
- **Nothing readable** — `plan_batches.py` never batched them, because `EXTRACTED.json` had no contents for
  them. The user describes them or re-saves them.

Take each to the user with its file name, its folder, and the evidence line. That trio is usually enough
for them to answer in one pass.
