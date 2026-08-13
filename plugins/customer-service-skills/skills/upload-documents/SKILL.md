---
name: upload-documents
description: "Build the workbook that attaches a folder of documents onto items that already exist in a Worldmaker app, reading each document to decide what kind of document it is. Triggers on \"upload-documents\", or when the user wants documents assigned to existing items for a migration."
allowed-tools: Agent, Skill, AskUserQuestion, TodoWrite, Read, Write, Edit, Bash, Glob, Grep, Artifact
---

### Context

The user is on the Customer Service team and is not a developer. How a run talks to them — what gets asked,
what gets tabled, what gets drawn — is `${CLAUDE_PLUGIN_ROOT}/docs/PRESENTING.md`, read at the start of a run
and applied to every message after it.

The **items** already exist in the customer's Worldmaker app. The **documents** are a folder of files on
the user's computer. What is missing is the link between them, and this skill builds the workbook that
carries it — one row per document, naming the item it attaches to and identifying the file by its
SHA-256.

The files themselves are uploaded last, by the user, out of the migration once it exists. So a run reads
documents and never sends them anywhere:
`${CLAUDE_PLUGIN_ROOT}/docs/DOCUMENT_UPLOADING.md` is that wider journey.

### Session setup

All intermediate and output files live under `.workflow/active/${sessionId}/`, relative to the user's
current working directory. At the start of a run, if `${sessionId}` is not already set for this
conversation, generate one (a UUID, or a timestamp-based slug) and create the directory before writing
any files. Reuse the same `${sessionId}` for every file in the run.

Files inside this plugin are referenced with `${CLAUDE_PLUGIN_ROOT}`, set by Claude Code when the plugin
is installed. Running from a raw checkout instead, treat it as the plugin root — the folder containing
this `skills/` directory.

The user may be on macOS, Linux or Windows, and the shell differs with them. Write every path with
forward slashes, quote any that could contain a space, and keep each command on a single line — a
trailing backslash continues a line in `sh` and breaks it in PowerShell.

### The export

Nothing here reads the customer's app. Its own agent does that, through the
`worldover-export-data-for-document-upload` skill, and hands the user **two files**. They are what a run
is built from, and a run without them cannot start.

**The workflow** — `<PROJECT>_DOCUMENT_UPLOAD_WORKFLOW_<uuid>.json`, the app's vocabulary:

```json
{
  "documentTemplates": [
    { "id": "dt_sds", "name": "Safety Data Sheet (SDS)", "for_tables": ["raw_materials"] },
    { "id": "dt_coa", "name": "Certificate of Analysis (CoA)", "for_tables": ["raw_materials", "products"] }
  ],
  "itemTemplates": [
    {
      "name": "Raw Material",
      "table": "raw_materials",
      "identifierColumn": "code",
      "documentSections": [
        { "label": "Safety", "documentTemplates": ["dt_sds"] },
        { "label": "Quality", "documentTemplates": ["dt_coa"] }
      ]
    }
  ]
}
```

**The items** — `<PROJECT>_DOCUMENT_UPLOAD_ITEMS_<uuid>.csv`, every item documents can attach to:

```
table,id,identifier,name,template,archived
raw_materials,1,RM-0142,Glycerin,Raw Material,false
```

Both file names end in the **same uuid**. A mismatched pair is a workflow read against a stale item list,
which is why the check reports it.

Two words the app uses, and this skill uses with it:

- An ***item_kind*** is a type of item documents attach to, and it **is the `table`** — `raw_materials`,
  `products`. One sheet of the workbook per *item_kind*.
- An ***item_template*** is a blueprint an item is built from, and the owner of the **sections** its
  Documents tab renders. One *item_kind* has **many** *item_template*s, all on the same `table`, and the
  items file says which one each item is on. So the table decides the sheet and the *item_template*
  decides the sections.

`documentTemplates` is a **closed list**, and `for_tables` narrows it further: a document on a
`raw_materials` item can only be a template whose `for_tables` holds `raw_materials`. Every template
carries the app's own `id`, so nothing in a run invents one.

### The tree

The user gives you one folder of documents: **the tree**. Its folder names carry the one thing reading a
document can never recover: **which item** the document belongs to. So the tree answers *which item*, and
reading answers *what kind of document* — two questions, two sources, neither guessing at the other's job.

Every level of a tree plays one of three roles:

- **item_kind level** — its names are kinds of item ("Raw Materials", "Products"), each matching a
  `table` in the workflow.
- **anchor level** — its names carry the identifier of one item. The anchor is the level the whole mapping
  hangs off. It can be a folder level, or the file names themselves when documents sit flat in an item's
  folder (`RM-0142_SDS.pdf`).
- **noise** — dates, "Final", "OLD", "scans", and folders naming a kind of document. A level that looks
  like a document type is not read as one here: it becomes a hint the classifier sees, and the document's
  contents settle it.

A tree is **legible** when every document under it reaches **exactly one live item in the items file**.
That is a fact to be measured rather than judged, and Step 4 measures it. What cannot be placed is named
to the user rather than guessed at — a guessed attachment is a document filed against the wrong
substance, which is worse than no row at all.

### Process

# Step 1 — preflight

Send **one sub agent**, briefed per
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/PREFLIGHT.md`, to settle its
two questions: `uv`, which reads the documents in Step 5, and a Python with `openpyxl`, which writes the
workbook in Step 8.

Either one missing stops the run, as that reference describes: tell the user which and what it blocks,
then wait.

Done when the sub agent has reported, and the `uv` command and the interpreter name are recorded.

# Step 2 — take the two exported files

Ask the user for the workflow JSON and the items CSV described in "### The export", then check them:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/read_export.py" "<workflow.json>" "<items.csv>" ".workflow/active/${sessionId}"
```

That copies them in as `WORKFLOW.json` and `ITEMS.csv` — the names every later step reads — and prints
what the app holds: per table, the identifier column, the item count, the *item_template*s, the document
templates allowed on it, and anything that will cost them documents later. Put that back to the user as
a table per *item_kind* and have them confirm it is the app they mean.

Three things in that report are worth naming to them rather than leaving in the output, because each one
is documents that will not attach: items that are **archived**, items with **no identifier**, and
identifiers **held by more than one item**. A folder named by a colliding identifier resolves to no item
at all, so those are the user's to settle in the app before a run can place them.

**Without the files, stop.** They come from the customer's app, not from this machine: the user asks
their app agent for them by running `worldover-export-data-for-document-upload`, and comes back with
both. Describing the app's templates in chat is not a substitute — a run matches documents against real
items, and there is nothing here to match against.

Done when `WORKFLOW.json` and `ITEMS.csv` are in the session directory, the check reported no error, and
the user has confirmed the tables read back to them.

# Step 3 — map the tree

Ask the user for the folder of documents, then map it with
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/READING_THE_TREE.md`.

Done when `TREE.json` holds every file under the folder, its summary has been read, and no document has
been opened.

# Step 4 — the legibility gate

Read the roles off the summary per that same reference, and write your reading into
`.workflow/active/${sessionId}/BRANCHES.json` — one branch per part of the tree, each naming a `table`
from `WORKFLOW.json` and the rule that gets an identifier out of a path.

Then **test it against the app's real items rather than reasoning about it**:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/check_branches.py" ".workflow/active/${sessionId}"
```

That opens no document and writes nothing. It applies each branch's rule to every path and prints, per
branch, how many files reach exactly one live item, and names the ones that do not — with the app's
nearest identifiers where a folder name looks like a misspelling of one. A branch whose anchor is one
level off reads as a match rate near zero, which is the cheapest possible moment to find out.

Correct the branches and run it again until the rate stops improving. This loop costs nothing: no
document has been hashed or read yet.

**Legible** — every file reaches one item. Put your reading to the user before acting on it, as **the
board**: one row per branch with its *item_kind*, its identifier rule, its match rate, and two or three
real folder names as the evidence. The *item_kind* choices are offered as options from `WORKFLOW.json`
rather than making them recall the app's vocabulary. Redraw the board as each answer lands.

**Not legible** — hand back what the check found, which is already specific: the folders that reach no
item, the ones naming an archived item, the ones whose identifier is held by two items, and the near
misses. Then the moves they own — fix the spelling or the folder names and come back, unarchive an item
in the app, or tell you the item a folder belongs to, which you record as user-supplied.

A tree can be legible in part, and a partly legible tree is worth building from: the branches that pass
go into the workbook, and the rest go to the user as the exception pile. Say which is which rather than
stopping the whole run over one bad folder.

Done when `check_branches.py` reports every file it can place, the user has confirmed the board, and
whatever it cannot place has been named to them.

# Step 5 — hash, extract, and batch

Three mechanical passes, in order. Each writes a file the next one reads.

**Hash.** A document is carried into the workbook as its SHA-256, because that is what the upload screen
matches on later — names collide between item folders and paths change, the hash does neither.

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/hash_documents.py" "<folder>" ".workflow/active/${sessionId}"
```

That writes `DOCUMENTS.json`, and reports the same file filed under more than one item — one document
belonging to several items, which is a row each rather than a problem.

**Extract.** Invoke the `extract-document-text` skill, giving it the documents folder as its input and
`.workflow/active/${sessionId}` as its output directory. It writes `EXTRACTED.json`, one record per file
with the Markdown or rendered pages a classifier can read.

**Batch.** Join the three files and cut the work into batches:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/plan_batches.py" ".workflow/active/${sessionId}"
```

That resolves each document to a **real item** — branch rule to identifier, identifier to a row in
`ITEMS.csv` — pairs it with what to read, and writes one input file per batch plus `BATCHES.json`. Each
batch carries only the document templates its own tables allow and only the sections of the
*item_template*s its own documents sit on, so a classifier is never shown a choice the app would refuse.

Six kinds of document never reach a batch, and it reports each separately: no branch covers it, the rule
yielded no identifier, no item has that identifier, several items share it, the item is archived, or
nothing could be read from it. Step 4 should have emptied the first five; anything left here goes to the
user.

Done when `BATCHES.json` names at least one batch, every document in `DOCUMENTS.json` is either in a batch
or on the reported exception list, and the user has seen that list.

# Step 6 — classify, and reconcile

Each batch goes to one sub agent, which reads its input file and says, per document, the **id** of the
document template it is, which section fits, how confident it is, and the evidence for it. Follow
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/CLASSIFYING_DOCUMENTS.md` —
it holds the prompt, the output shape, and the model to run them on.

Then reconcile in code rather than by eye:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/collect_classifications.py" ".workflow/active/${sessionId}"
```

That writes `CLASSIFICATIONS.json` and prints the roll call: how many documents answered, which batches
are missing, the spread of confidence, and every document that came back without a template, with a
template the app does not allow on that table, with a section its *item_template* does not carry, or
under the confidence floor. Send any missing batch again; that reference holds how many rounds to give it.

A classifier that finds nothing fitting in the app's list **proposes** a name instead, and the collector
groups those by name with a count. Put them to the user that way — as a short list of templates and
sections to create in the app, each with how many documents are waiting on it — rather than as one
question per document. Creating a template once clears every document that proposed it.

What is left over is the **exception pile**, and it is the user's to settle: documents that got neither a
pick nor a proposal, documents below the floor, and documents nothing could read. Put them to the user
with the evidence the classifier gave, since a file name plus one line of evidence is usually enough for
them to say what a document is.

Done when `CLASSIFICATIONS.json` holds one entry per batched document, every batch has answered or been
reported as unanswered, and the exception pile has been through the user.

# Step 7 — show the workbook before building it

Load the `artifact-design` skill, then publish one **markdown** artifact to
`.workflow/active/${sessionId}/tree.md` holding, in this order:

1. The tree as a `flowchart TD`, each level labelled by the role Step 4 gave it, drawn per
   `${CLAUDE_PLUGIN_ROOT}/vendor/mermaid-diagrams/references/FLOWCHARTS.md`. A tree too wide to read is
   one diagram per branch, not one crowded diagram.
2. One card per branch: *item_kind*, identifier column, how many of that table's items the documents
   reached, and document count. Reaching 40 of 300 items is worth seeing before the workbook is built.
3. The document templates the classifier actually used, with a count each, and the sections they fall into
   per *item_template* — so the shape an item's page will take is visible before it is built.
4. A preview of each sheet the workbook will have — real header row, and three to five real rows, with
   real identifier values, real file names and real template names.
5. The exception pile, listed by file name with its evidence.
6. The attachments worth spot-checking: the lowest-confidence rows that are still going into the workbook.

The sheet preview is what the user can judge, so fill it with real values rather than placeholders.

Iterate: take their corrections, update `CLASSIFICATIONS.json`, republish to the same file path so the URL
holds. Done when the user approves what the artifact shows.

# Step 8 — write the workbook

Build the Excel file per
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/DOCUMENT_WORKBOOK_FORMAT.md`,
writing to `.workflow/active/${sessionId}/DOCUMENT_UPLOAD_WORKBOOK.xlsx`.

Done when every document in `DOCUMENTS.json` appears either as a row in a data sheet or on the `README`
sheet's exception list, every identifier value traces back to a row in `ITEMS.csv`, and the file loads
back with the row counts `CLASSIFICATIONS.json` predicted.

# Step 9 — hand it over

Give the user the full path to `DOCUMENT_UPLOAD_WORKBOOK.xlsx`, one line per sheet saying which
*item_kind* it attaches documents to and how many, the sections each *item_template* ended up with,
whatever ended up on the exception pile, and the two or three attachments worth spot-checking — the
lowest-confidence rows in the workbook.

Then what happens next, since two things are still to come and one of them can catch them out: they start
a migration with this workbook, and the migration then asks them for the document files themselves. Those
files have to be the ones this run hashed — an edited or re-exported document no longer matches its row.

### Helping the user

A run is one stage of a longer journey the user does the rest of by hand: they start the migration with
the workbook you hand over, then upload the document files from the migration card.
`${CLAUDE_PLUGIN_ROOT}/docs/DOCUMENT_UPLOADING.md` holds both stages, and is what to read when the user
asks how the upload works or what to do with the workbook. Offer that help as it comes up rather than
waiting to be asked.
