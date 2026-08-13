# Classifying the documents

How Step 7 turns a folder of extracted documents into one document template, a runner-up, a confidence and
a line of evidence per reading. `plan_batches.py` has already written the batch input files; this page is
what to do with them.

## The shape of the fan-out

**One batch per sub agent, sent as one wave.** Send the whole wave **in a single message with one `Agent`
call per batch** — calls in separate messages run one after another. More than twenty batches goes in
waves of twenty.

`plan_batches.py` has already decided how much is in each: twenty readings, or twelve images, whichever
bit first. Do not re-cut them.

**Each sub agent is given one file path, not twenty.** Its batch input file already holds the vocabulary,
the readings, and what to read for each — so the prompt stays the same length whatever the batch holds,
and the agent reads the list rather than being told it. A prompt carrying twenty paths spends its context
on a list it has to keep straight; a prompt carrying one path spends it on the documents.

**Send them as `subagent_type: "document-classifier"`**, the agent this plugin ships. It carries the model
and the tools, so neither is a thing to remember per call: `claude-haiku-4-5`, and `Read` and `Write`
alone.

Both of those are deliberate. Picking a document's type from a closed list is high-volume and mechanical,
so the cheapest, fastest model is the right one — $1/$5 per million tokens against $3/$15 for Sonnet 5. Its
context window is 200K, the only current model under 1M, which is why the extractor caps what each document
contributes; if the categories come back poor, the fix is `claude-sonnet-5` on the same prompt before
anything else. And a classifier needs nothing but reading: the first run of this pipeline saw agents reach
for `Bash`, write their own extraction scripts and open a browser, because extraction had not been done for
them. It has been now, so those tools are only a way to go wrong.

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
    }
  },
  "documents": [
    {
      "readingId": "a8ff60c4",
      "table": "raw_materials",
      "folderHints": ["SDS", "Veiligheid"],
      "readFrom": ["C:/…/extracted/a1b2c3d4_SDS_2026.md"]
    }
  ]
}
```

`readingId` is what the answer is joined on, and it is **not a path**. Eight hex characters of the
document's own sha, short enough to copy back without mangling and opaque enough that there is no name to
tidy. On the first run of this pipeline, eighteen answers came back with the file name normalised — a
non-breaking space turned into a space — and every one silently failed to match.

`documentTemplates` is keyed by **table**, so the closed list a document is picked from is the one the app
allows on *its* table: a `Spec Sheet` the app only permits on products is never offered for a raw
material. Only the tables this batch's own readings sit on appear.

**Sections are not here, and the classifier is never asked about one.** The section a document lands in is
looked up afterwards, in code, from the item template each copy's item is on — see `docs/adr/0002`. One
reading can cover copies on several item templates, so there is no single section for it to name, and it
is shown no section list it could name one from. Where the app renders a template in no section at all,
the collector reports that with the sections that item template *does* have, which is a list somebody
picks from in the app rather than a name anybody guesses.

`folderHints` is every folder a copy of this document sat in, where that folder looked like a kind of
document, or empty. It is a hint and the contents outrank it. Two copies filed under differently-named
folders is itself worth noticing.

`fallbackTemplates` is a **path, not a list**: around 285 document types across cosmetics, chemicals and
compliance, some 4,000 tokens if read whole. Passing the path keeps that out of every batch's context and
puts it in reach of the batches that actually meet a document the app has no word for.

`readFrom` is the extracted Markdown, the rendered pages of a scan, or the image itself — whatever
`EXTRACTED.json` pointed at. The Markdown may be capped, with the middle elided and a marker saying so.

## The prompt

Substitute the batch's input path and its output path. Nothing else changes between batches.

```
Read the JSON file at <batch input path>. It holds a `vocabulary` and a list of `documents`.

Every document gets either a **pick** — something the app already has — or a **proposal**. Picking is
always the better answer: a pick attaches on its own, a proposal is work for a person before this document
can land. Propose only what you could not pick.

For each document in that list:

1. Read the file(s) at its `readFrom` paths. That is the document's contents — extracted Markdown, or
   rendered page images for a scan. If a path will not open, or holds nothing, say so with
   `"received": false` and move on. An honest miss costs one re-read; a guess costs a document filed
   as the wrong thing.
2. **Pick the document template** from `vocabulary.documentTemplates[<the document's table>]` — the full
   list of what this kind of item can carry. Return the `id` of the closest fit as `documentTemplateId`,
   copied exactly.
3. **Name the runner-up.** Return the id of the second-best fit as `runnerUpTemplateId`, or `null` where
   nothing else came close.
4. **Only where nothing in that list is what the document is**, open the file at `fallbackTemplates` and
   find the name that does fit. Return it as `proposedTemplate` with `documentTemplateId` set to `null`.
   That file is a few hundred lines, so open it for the documents that need it rather than up front. Where
   even it holds nothing, write the name yourself in the same field. Where you cannot tell what the
   document is at all, leave both `null` and say what you read in evidence.
5. **Score the gap between your pick and your runner-up**, 0 to 1. This is not how clearly the document
   announces itself: a sheet headed TECHNICAL DATA SHEET that is equally a Product Specification scores
   low, because two templates fit it. 0.9 and up when one template fits and nothing else comes close; 0.7
   to 0.9 when a second is possible but weaker; below 0.5 when two fit and you are choosing between them.
   A low score is not a failure — it is the thing that gets the document a second reading, and a wrong
   high score is what stops that happening.
6. **Quote one line from the document**, verbatim, as `quote`. Copy it exactly as it appears — this is
   checked against the file you were given, and an answer whose quotation is not in the document is
   treated as unread. A title, a header, a form number, a section heading.
7. Write one line of evidence: what that quotation tells you, and why the runner-up lost. "Header reads
   SAFETY DATA SHEET and section 3 lists hazard classifications, so not the CoA" is evidence; "appears to
   be an SDS" is not.

`folderHints` are the folders the document's copies sat in, where they looked like a kind of document.
Treat them as hints only — the contents outrank them. Where they disagree, follow the contents and say so
in evidence.

Then write your results to <batch output path> as JSON:

{"results": [{"readingId": "a8ff60c4", "received": true, "documentTemplateId": "dt_sds",
              "runnerUpTemplateId": "dt_coa", "proposedTemplate": null,
              "confidence": 0.94, "quote": "SAFETY DATA SHEET", "evidence": "…"}]}

`readingId` MUST be copied verbatim from the input file — it is what your results are joined on. Return
one entry for EVERY document in the input, including the ones you could not read, marked
`"received": false`. Reply with the count you wrote and nothing else.
```

The output path is `.workflow/active/${sessionId}/classified/batch_003.json`, matching the input's number.
A second round writes to `classified_r2/` and reads from `batches_r2/`.

## The roll call

`collect_classifications.py` is the authority on who answered, and it counts against `BATCHES.json` rather
than against your memory of what you sent. A batch whose output file is missing or short goes out again —
same prompt, same input file — for at most **two further rounds**. Anything still missing after that is
reported as unread and joins the exception pile, named rather than left looking classified.

This is the whole reason the fan-out is trustworthy, so it is a count you actually make: run the collector
after every round and read its roll call before moving on.

## Reading a document twice

The collector writes `REREAD.json` naming the readings a second opinion would settle, and spends nothing
on its own. Plan them with `plan_batches.py <session> --round 2`, fan them out the same way, and run the
collector again.

Two readings that hold up and name the same template clear the floor — that agreement is the evidence a
thin margin was short of. Two that differ put the row in front of a person carrying both names, which is
the one outcome the first version of this pipeline could not produce: it read 3,440 documents more than
once, disagreed on 1,081, and settled every one of them by which file happened to be merged last.

A reading whose answer could not be shown to have read the document is **replaced** by its second reading
rather than argued with. Nothing is sent a third time.

## What comes back needing a person

The collector lists each of these separately, because each is a different action:

- **A proposed template** — the classifier read the document, and the app has no word for it. Grouped **by
  proposed name with a count**, folding spellings that differ only in case or punctuation, because the
  user's action is creating each template once, not settling each document. A name from
  `DOCUMENT_TYPES.txt` and a name the classifier wrote itself arrive the same way; the app has neither.
- **A template no section renders** — see below; grouped by *item_template* and template name, listing
  the sections that item template does have. Cheaper to act on than a template, and often the answer is
  to leave it: a document with no section still attaches.
- **No template at all** — not even a proposal, so the classifier could not tell what it read. This is the
  one that needs the user to open the document.
- **A template the app cannot take** — an id that does not exist, or one the app does not allow on that
  document's table. Rejected rather than carried into the workbook, since the migration would refuse it.
- **A template with no section to render it** — allowed on the table, but arranged into no section of the
  *item_template* this item is on. The reading is kept, since the document really is that type; what is
  missing is a section attachment somebody adds in the app.
- **Not shown to have been read** — the classifier said the document never reached it, or quoted something
  that is not in the file. Re-read once; still failing, it goes to the user.
- **Read twice, settled differently** — both readings held up and named different templates. The user
  picks, and the row carries both.
- **Below the confidence floor** (0.7 by default; `--floor` moves it) — two templates fitted. These are the
  rows a second reading is for, not the rows to discard.
- **Nothing readable** — `plan_batches.py` never batched them, because `EXTRACTED.json` had no contents for
  them. The user describes them or re-saves them.

Take each to the user with its file name, its folder, and the evidence line. That trio is usually enough
for them to answer in one pass.
