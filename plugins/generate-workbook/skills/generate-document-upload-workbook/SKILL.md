---
name: generate-document-upload-workbook
description: "Build the workbook that attaches a folder of documents onto items that already exist in a Worldmaker app, reading the assignment off the folder tree the customer organised. Triggers on \"generate-document-upload-workbook\", or when the user wants documents assigned to existing items for a migration."
allowed-tools: Agent, Skill, AskUserQuestion, TodoWrite, Read, Write, Edit, Bash, Glob, Grep, Artifact
---

### Status

Work in progress. The process below is a first pass and will change with use.

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
this `skills/` directory. Some of those files live under the sibling `generate-workbook` skill, which is
the plugin's authority on reading an app's schema and writing a workbook.

The user may be on macOS, Linux or Windows, and the shell differs with them. Write every path with
forward slashes, quote any that could contain a space, and keep each command on a single line — a
trailing backslash continues a line in `sh` and breaks it in PowerShell.

### The tree

The user gives you one folder of documents: **the tree**. Its folder names and nesting are the evidence
for which item each document belongs to, and they are evidence enough — customers organise documents by
item, so `Raw Materials/RM-0142/SDS_2026.pdf` already says raw material `RM-0142`. Read the tree; leave
the documents closed.

Every level of a tree plays one of four roles, and naming them is what turns a folder listing into a
mapping:

- **entity level** — its names are kinds of item ("Raw Materials", "Products"), each pointing at an app
  entity.
- **anchor level** — its names carry the identifier of one item. The anchor is the level the whole
  mapping hangs off. It can be a folder level, or the file names themselves when documents sit flat in
  an item's folder (`RM-0142_SDS.pdf`).
- **template level** — its names are kinds of document ("SDS", "CoA"), repeating across branches. Each one
  is a **document template**, and the sections that group those templates are worked out later, from the
  templates themselves.
- **noise** — dates, "Final", "OLD", "scans": levels that identify nothing.

A tree is **legible** when every document under it resolves to exactly one item through an anchor whose
name yields an identifier value the app can look that item up by. An illegible tree stops the run — a
guessed attachment is a document filed against the wrong substance, which is worse than no workbook.

### The mapping

The **mapping** is the tree expressed in the app's terms, and the thing the user approves. Hold it at
`.workflow/active/${sessionId}/MAPPING.md`, one entry per branch of the tree:

- **target entity** — the app entity, and the table backing it, whose items these documents attach to.
- **identifier** — the anchor level, and the app column its names feed (`code`, `primary_identifier`).
- **template** — the level that names the kind of document, or a recorded decision that the tree is silent
  and the templates come from reading the documents.
- **sections** — the groups those templates fall into on this entity, settled once the templates are.
- **counts** — how many items and how many documents that branch holds, so the user can sanity-check the
  reading against what they know they sent.

### Process

# Step 1 — preflight, in parallel

Send **both sub agents in a single message**, briefed per
`${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/references/PREFLIGHT.md`, and read their answers
together.

- **Python or repo access missing** — stop here, as that reference describes, and wait for the user to
  come back with it.
- **Document tooling partial** — workable, and often costs nothing. The documents are only ever opened
  to work out the kind of document where the folder does not say, so carry the covered file types forward
  and tell the user which are missing and that engineering can fix it.

Done when both sub agents have reported, the interpreter name is recorded, repo access is confirmed, and
the covered file types are known.

# Step 2 — find the customer's app

Ask the user for the customer's name and the app's name. Repos live at
`https://github.com/WorldoverProd`, named `<customer>-<app>`.

Follow `${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/references/READING_APP_SCHEMA.md` to resolve the
pair to one repo. Customers often have several apps, so name the repo you settled on and have the user
confirm it before reading anything.

Done when the user confirms one repo.

# Step 3 — learn how the app holds documents

Extract the schema per that same reference, then read its "## The document side" section and record, at
`.workflow/active/${sessionId}/APP_SCHEMA.md`: which entities can hold documents, how a document attaches
to one, which columns the app can look an existing item up by, and the app's own document templates and the
sections they are grouped into.

Then put it back to the user as a table — which kinds of item can carry documents, what identifies each kind
— and ask them to confirm or correct it, since it drives the rest of the run. Anything the app's own data
does not tell you, say what it means for them rather than where you looked.

Done when all four are recorded and the user has confirmed or corrected what you read back.

# Step 4 — map the tree

Ask the user for the folder of documents, then map it with
`${CLAUDE_PLUGIN_ROOT}/skills/generate-document-upload-workbook/references/READING_THE_TREE.md`.

Done when `TREE.json` holds every file under the folder, its summary has been read, and no document has
been opened.

# Step 5 — the legibility gate

Reach a verdict on the tree per that same reference.

**Legible** — put your reading to the user before acting on it, as **the board**: one row per branch, every
cell you have not settled still a `?`. Carry two or three real folder names as the evidence for each
identifier, so they are checking your reading against something rather than taking it on trust.

Then work down it one branch at a time, asking them to confirm or correct that row, the entity choices
offered as options rather than making them recall the app's vocabulary. Redraw the board as each answer
lands and write the confirmed branch into `MAPPING.md`.

**Illegible** — stop, and hand back something they can act on: which folders you could not resolve and
what was missing in each, what a legible tree looks like for their case (one folder per item, named with
the code the app knows it by), and the two moves they own — reorganise those folders and come back, or
tell you the item each one belongs to, which you record as user-supplied. Build nothing until the tree is
legible.

Done when every branch of the tree has a target entity and an identifier the user confirmed, or the run
has stopped with the unresolved folders named.

# Step 6 — resolve every document

Two facts are still missing per document: which file it is, and what type of document it is.

**Identity.** A document is carried into the workbook as its SHA-256, because that is what the upload
screen matches on later — names collide between item folders and paths change, the hash does neither.
Hash the tree:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/generate-document-upload-workbook/lib/hash_documents.py" "<folder>" ".workflow/active/${sessionId}"
```

That writes `DOCUMENTS.json`, and reports the same file filed under more than one item — one document
belonging to several items, which is a row each rather than a problem.

**Template.** Follow Part 1 of
`${CLAUDE_PLUGIN_ROOT}/skills/generate-document-upload-workbook/references/TEMPLATES_AND_SECTIONS.md`: a
folder that names the kind of document gives its template directly, and only the documents whose folders
are silent get read.

Then put the documents left without a template to the user, since that is theirs to resolve.

Done when every file in `TREE.json` carries a SHA-256 and either a document template or a place on the
exception pile the user has seen.

# Step 7 — group the templates into sections

Only now is there a full list of templates to group, and grouping them is what gives each item's page its
shape in the app. Follow Part 2 of that same reference: per entity, take the tree's own grouping where it
has one, otherwise sort the templates into two to six sections.

This is a judgement rather than a reading, so it goes to the user as **the board** — one row per section,
the templates under it, the document count behind each — and they move a template, rename a section or
merge two until it is theirs.

Done when every template the workbook uses belongs to exactly one section of its entity, every section
holds at least one template, and the user has approved the grouping.

# Step 8 — show the workbook before building it

Load the `artifact-design` skill, then publish one **markdown** artifact to
`.workflow/active/${sessionId}/tree.md` holding, in this order:

1. The tree as a `flowchart TD`, each level labelled by the role Step 5 gave it, drawn per
   `${CLAUDE_PLUGIN_ROOT}/vendor/mermaid-diagrams/references/FLOWCHARTS.md`. A tree too wide to read is
   one diagram per branch, not one crowded diagram.
2. One card per branch: target entity, identifier column, document templates found, item count, document
   count.
3. The sections per entity, each with the templates under it, so the shape an item's page will take is
   visible before it is built.
4. A preview of each sheet the workbook will have — real header row, and three to five real rows, with
   real folder names, real file names and real template names.
5. The exception pile, listed by file name.

The sheet preview is what the user can judge, so fill it with real values rather than placeholders.

Iterate: take their corrections, update `MAPPING.md`, republish to the same file path so the URL holds.
Done when the user approves what the artifact shows.

# Step 9 — write the workbook

Build the Excel file per
`${CLAUDE_PLUGIN_ROOT}/skills/generate-document-upload-workbook/references/DOCUMENT_WORKBOOK_FORMAT.md`,
writing to `.workflow/active/${sessionId}/DOCUMENT_UPLOAD_WORKBOOK.xlsx`.

Done when every document in `DOCUMENTS.json` appears either as a row in a data sheet or on the `README`
sheet's exception list, every identifier value traces back to an anchor name, and the file loads back
with the row counts `MAPPING.md` predicted.

# Step 10 — hand it over

Give the user the full path to `DOCUMENT_UPLOAD_WORKBOOK.xlsx`, one line per sheet saying which kind of
item it attaches documents to and how many, the sections each entity ended up with, whatever ended up on
the exception pile, and the two or three attachments worth spot-checking — the ones whose folder names you
had least evidence for.

Then what happens next, since two things are still to come and one of them can catch them out: they start
a migration with this workbook, and the migration then asks them for the document files themselves. Those
files have to be the ones this run hashed — an edited or re-exported document no longer matches its row.

### Helping the user

A run is one stage of a longer journey the user does the rest of by hand: they start the migration with
the workbook you hand over, then upload the document files from the migration card.
`${CLAUDE_PLUGIN_ROOT}/docs/DOCUMENT_UPLOADING.md` holds both stages, and is what to read when the user
asks how the upload works or what to do with the workbook. Offer that help as it comes up rather than
waiting to be asked.
