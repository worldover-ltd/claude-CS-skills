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

### The vocabulary

A run needs the app's own words for two things, and **the user supplies both** — nothing here reads the
customer's app. Hold them at `.workflow/active/${sessionId}/APP_TEMPLATES.json`:

```json
{
  "documentTemplates": ["Safety Data Sheet (SDS)", "Certificate of Analysis (CoA)", "Spec Sheet"],
  "entityTemplates": [
    {
      "name": "Raw Material",
      "table": "raw_materials",
      "identifierColumn": "code",
      "sections": [
        { "label": "Safety", "documentTemplates": ["Safety Data Sheet (SDS)"] },
        { "label": "Quality", "documentTemplates": ["Certificate of Analysis (CoA)", "Spec Sheet"] }
      ]
    }
  ]
}
```

- **`documentTemplates`** — every kind of document the app knows. This is a **closed list**: it is what
  the migration can land on, so a document is given one of these names or none at all.
- **`entityTemplates`** — the kinds of item documents attach to, each with the sections its page carries
  and which document templates sit in each section.
- **`table`** and **`identifierColumn`** are what the workbook is built from: the sheet is named after the
  table, and the identifier column is spelled the way the app spells it. Ask for them explicitly — the
  user may know them as "the raw materials table" and "the code field", and the exact spellings are what
  the migration matches on.

### The tree

The user gives you one folder of documents: **the tree**. Its folder names carry the one thing reading a
document can never recover: **which item** the document belongs to. So the tree answers *which item*, and
reading answers *what kind of document* — two questions, two sources, neither guessing at the other's job.

Every level of a tree plays one of three roles:

- **entity level** — its names are kinds of item ("Raw Materials", "Products"), each matching an
  `entityTemplates` entry.
- **anchor level** — its names carry the identifier of one item. The anchor is the level the whole mapping
  hangs off. It can be a folder level, or the file names themselves when documents sit flat in an item's
  folder (`RM-0142_SDS.pdf`).
- **noise** — dates, "Final", "OLD", "scans", and folders naming a kind of document. A level that looks
  like a document type is not read as one here: it becomes a hint the classifier sees, and the document's
  contents settle it.

A tree is **legible** when every document under it resolves to exactly one item through an anchor whose
name yields an identifier value the app can look that item up by. An illegible tree stops the run — a
guessed attachment is a document filed against the wrong substance, which is worse than no workbook.

### Process

# Step 1 — preflight

Send **one sub agent**, briefed per
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/PREFLIGHT.md`, to settle its
two questions: `uv`, which reads the documents in Step 5, and a Python with `openpyxl`, which writes the
workbook in Step 8.

Either one missing stops the run, as that reference describes: tell the user which and what it blocks,
then wait.

Done when the sub agent has reported, and the `uv` command and the interpreter name are recorded.

# Step 2 — take the app's vocabulary

Ask the user for the two lists in "### The vocabulary" and write `APP_TEMPLATES.json` from what they give
you. They will usually paste or describe rather than hand over JSON, so put your reading back to them as
two tables — one row per document template, one row per entity template with its sections and the
templates under each — and have them correct it.

Where they have the document templates but not the sections, say what that costs: the workbook can still
attach every document, and the `Document Sections` sheet comes back empty, so somebody arranges each
item's page in the app afterwards.

Done when `APP_TEMPLATES.json` holds at least one document template and at least one entity template
carrying a `table` and an `identifierColumn`, and the user has confirmed the tables you read back.

# Step 3 — map the tree

Ask the user for the folder of documents, then map it with
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/READING_THE_TREE.md`.

Done when `TREE.json` holds every file under the folder, its summary has been read, and no document has
been opened.

# Step 4 — the legibility gate

Reach a verdict on the tree per that same reference.

**Legible** — put your reading to the user before acting on it, as **the board**: one row per branch, every
cell you have not settled still a `?`. Carry two or three real folder names as the evidence for each
identifier, so they are checking your reading against something rather than taking it on trust.

Then work down it one branch at a time, asking them to confirm or correct that row, the entity choices
offered as options from `APP_TEMPLATES.json` rather than making them recall the app's vocabulary. Redraw
the board as each answer lands, and write the confirmed branches into
`.workflow/active/${sessionId}/BRANCHES.json` in the shape that reference gives — the machine-readable
form of the board, and what the next step reads.

**Illegible** — stop, and hand back something they can act on: which folders you could not resolve and
what was missing in each, what a legible tree looks like for their case (one folder per item, named with
the code the app knows it by), and the two moves they own — reorganise those folders and come back, or
tell you the item each one belongs to, which you record as user-supplied. Build nothing until the tree is
legible.

Done when every branch in `BRANCHES.json` carries an entity from `APP_TEMPLATES.json`, an identifier rule,
and the user's confirmation — or the run has stopped with the unresolved folders named.

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

That resolves each document's identifier value from its branch rule, pairs it with what to read, and
writes one input file per batch plus `BATCHES.json`. It reports two things worth reading before going on:
documents whose identifier rule yielded nothing, and documents with nothing readable — both go to the
user rather than into a batch.

Done when `BATCHES.json` names at least one batch, every document in `DOCUMENTS.json` is either in a batch
or on the reported exception list, and the user has seen that list.

# Step 6 — classify, and reconcile

Each batch goes to one sub agent, which reads its input file and says, per document, which document
template it is, which section fits, how confident it is, and the evidence for it. Follow
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/CLASSIFYING_DOCUMENTS.md` —
it holds the prompt, the output shape, and the model to run them on.

Then reconcile in code rather than by eye:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/collect_classifications.py" ".workflow/active/${sessionId}"
```

That writes `CLASSIFICATIONS.json` and prints the roll call: how many documents answered, which batches
are missing, the spread of confidence, and every document that came back without a template or under the
confidence floor. Send any missing batch again; that reference holds how many rounds to give it.

What is left over is the **exception pile**, and it is the user's to settle: documents with no template,
documents below the floor, and documents nothing could read. Put them to the user with the evidence the
classifier gave, since a file name plus one line of evidence is usually enough for them to say what a
document is.

Done when `CLASSIFICATIONS.json` holds one entry per batched document, every batch has answered or been
reported as unanswered, and the exception pile has been through the user.

# Step 7 — show the workbook before building it

Load the `artifact-design` skill, then publish one **markdown** artifact to
`.workflow/active/${sessionId}/tree.md` holding, in this order:

1. The tree as a `flowchart TD`, each level labelled by the role Step 4 gave it, drawn per
   `${CLAUDE_PLUGIN_ROOT}/vendor/mermaid-diagrams/references/FLOWCHARTS.md`. A tree too wide to read is
   one diagram per branch, not one crowded diagram.
2. One card per branch: entity, identifier column, item count, document count.
3. The document templates the classifier actually used, with a count each, and the sections they fall into
   per entity — so the shape an item's page will take is visible before it is built.
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
sheet's exception list, every identifier value traces back to an anchor name, and the file loads back with
the row counts `CLASSIFICATIONS.json` predicted.

# Step 9 — hand it over

Give the user the full path to `DOCUMENT_UPLOAD_WORKBOOK.xlsx`, one line per sheet saying which kind of
item it attaches documents to and how many, the sections each entity ended up with, whatever ended up on
the exception pile, and the two or three attachments worth spot-checking — the lowest-confidence rows in
the workbook.

Then what happens next, since two things are still to come and one of them can catch them out: they start
a migration with this workbook, and the migration then asks them for the document files themselves. Those
files have to be the ones this run hashed — an edited or re-exported document no longer matches its row.

### Helping the user

A run is one stage of a longer journey the user does the rest of by hand: they start the migration with
the workbook you hand over, then upload the document files from the migration card.
`${CLAUDE_PLUGIN_ROOT}/docs/DOCUMENT_UPLOADING.md` holds both stages, and is what to read when the user
asks how the upload works or what to do with the workbook. Offer that help as it comes up rather than
waiting to be asked.
