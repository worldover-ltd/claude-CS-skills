---
name: generate-workbook
description: "Build the upload workbook for a Worldmaker app when the customer did not supply one. Triggers on \"generate-workbook\", or when the user wants a workbook/spreadsheet built out of raw customer source files (zip, excel, docx, pdf, export) so an app agent can upload or migrate that data."
allowed-tools: Agent, Skill, AskUserQuestion, TodoWrite, Read, Write, Edit, Bash, Glob, Grep, Artifact
---

### Status

Work in progress. The process below is a first pass and will change with use.

### Context

The user is on the Customer Service team and is not a developer. How a run talks to them — what gets
asked, what gets tabled, what gets drawn — is `${CLAUDE_PLUGIN_ROOT}/docs/PRESENTING.md`, read at the
start of a run and applied to every message after it.

A Worldmaker app's agent uploads customer data from a **workbook**: one Excel file it reads as the
source of truth. Some customers supply that workbook. When one does not, this skill builds it from
whatever the customer did send — zips, spreadsheets, Word documents, PDFs, system exports.

### Session setup

All intermediate and output files live under `.workflow/active/${sessionId}/`, relative to the
user's current working directory. At the start of a run, if `${sessionId}` is not already set for
this conversation, generate one (a UUID, or a timestamp-based slug) and create the directory before
writing any files. Reuse the same `${sessionId}` for every file in the run.

Files inside this skill are referenced with `${CLAUDE_PLUGIN_ROOT}`, set by Claude Code when the
plugin is installed. Running from a raw checkout instead, treat it as the plugin root — the folder
containing this `skills/` directory.

The user may be on macOS, Linux or Windows, and the shell differs with them. Write every path with
forward slashes, quote any that could contain a space, and keep each command on a single line — a
trailing backslash continues a line in `sh` and breaks it in PowerShell.

### The app schema

The Worldmaker app the data lands in already has a fixed set of concepts, and **its repo is the
truth about them**. The app's own word for them is **entities** — in a PLM app: Product, Component,
Raw Material, Formulation. Reading them before opening the customer's files is what turns a vague
"what is in these files" into a specific "which of this app's entities does this file feed".

Hold the app schema at `.workflow/active/${sessionId}/APP_SCHEMA.md`, one entry per entity:

- **name** — the entity, and the table backing it.
- **what it is** — one sentence of business language, the way you would explain it to the user.
- **fields** — the columns the app stores for it, and which of them the app requires.
- **relationships** — which other entities it links to, and in which direction.

### The mapping

The **mapping** is the customer's data expressed in the app's entities — the bridge from source
files to workbook, and the thing the user actually approves. Hold it at
`.workflow/active/${sessionId}/MAPPING.md` and update it as each answer lands, so the file is always
what you would show the user right now.

The mapping is complete when all four hold for **every** item the customer has data for:

- **target entity** — the app schema entity this data feeds.
- **identifier** — the source field whose value is unique per item ("id", "primary identifier",
  "code", "SKU"), or a recorded decision that it has none and the workbook will carry a generated one.
- **fields** — every piece of data to upload, each traced to the source file it was read from, and
  each naming the app field it feeds. A field with no home in the app schema is recorded as one the
  app will need to hold as a custom field — flag it, rather than dropping it.
- **relationships** — every link to another item, with cardinality in both directions, checked
  against what the app schema allows. A product has many formulations; a raw material has at most one
  formulation; a formulation holds ingredients, raw materials, or other formulations.

### Process

# Step 1 — preflight, in parallel

The user may be on macOS, Linux or Windows, so nothing here is assumed. Send **both sub agents in a
single message**, briefed per
`${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/references/PREFLIGHT.md`, and read their answers
together. The customer's files arrive as spreadsheets, Word documents and PDFs, and Anthropic's
official document skills are what read them in Step 5.

- **Python or repo access missing** — stop here, as that reference describes, and wait for the user to
  come back with it.
- **Document tooling partial** — workable. Carry forward which file types are covered; the rest become
  files the user describes to you in Step 5. Tell them which ones, and that engineering can fix it.

Done when both sub agents have reported, the interpreter name is recorded, repo access is confirmed,
and the covered file types are known.

# Step 2 — find the customer's app

Ask the user for the customer's name and the app's name. Repos live at
`https://github.com/WorldoverProd`, named `<customer>-<app>`.

Follow `${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/references/READING_APP_SCHEMA.md` to resolve
the pair to one repo. Customers often have several apps, so name the repo you settled on and have the
user confirm it before reading anything.

Done when the user confirms one repo.

# Step 3 — learn what the app holds

Build the **app schema** from that repo, per the same reference file.

Then write it back to the user as a short list — entity, one sentence, what it links to — so they can
correct you before it drives the rest of the run.

Done when every entity in `APP_SCHEMA.md` carries all four parts, and the user has seen the list.

# Step 4 — collect the source files

Ask the user for the files to build the workbook from, and wait for them to name specific files or a
folder. Then write back a sample of the file names (10 at most) in a list, plus the total count, and
ask the user to check it.

Done when the user confirms the list.

# Step 5 — read what is in them

Read every source file and note what each one holds: item names, headers, tab names, row counts,
which fields look unique, and which app entity it appears to feed. Follow
`${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/references/EXTRACTING_SOURCES.md` for zips, Excel
files, Word documents, PDFs and scans.

Done when every source file is either read or reported to the user as unreadable with the reason.

# Step 6 — grill out the mapping

Invoke the `grilling` skill and interview the user until the **mapping** is complete on all four
counts above.

Look facts up in the source files and the app schema yourself, and bring them as your recommended
answer — "this column has 412 distinct values across 412 rows and the app stores a `code` on raw
materials, so I read it as the raw material code; confirm?" beats asking the user what the unique
code is. The decisions are theirs; the digging is yours.

Between questions, show the shape so far as a small markdown table per item — those render in the
user's terminal where a diagram does not.

Done when the completion test in "### The mapping" holds for every item, with no field left untraced,
no relationship left with an open end, and every app entity the customer has data for accounted for.

# Step 7 — show the workbook before building it

Load the `artifact-design` skill, then publish one **markdown** artifact to
`.workflow/active/${sessionId}/mapping.md` holding, in this order:

1. An `erDiagram` of the items and their relationships, drawn per
   `${CLAUDE_PLUGIN_ROOT}/vendor/mermaid-diagrams/references/CLASS-ER.md`.
2. One card per item: its target entity, its identifier, its fields, what it links to, and any field
   the app has no home for.
3. A preview of each sheet the workbook will have — real header row, and three to five sample rows
   taken from the actual source data.

The sheet preview is what the user can judge, so fill it with real values rather than placeholders.

Iterate: take their corrections, update `MAPPING.md`, republish to the same file path so the URL
holds. Done when the user approves what the artifact shows.

# Step 8 — write the workbook

Build the Excel file per
`${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/references/WORKBOOK_FORMAT.md`, writing to
`.workflow/active/${sessionId}/WORKBOOK.xlsx`.

Done when every item in the mapping has its sheet, every relationship is carried by a real column or
link sheet, and every row traces back to a source file.

# Step 9 — hand it over

Give the user the full path to `WORKBOOK.xlsx`, one line per sheet saying which app entity it feeds,
and the two or three things worth spot-checking before they give it to the app agent — the ones you
had least evidence for.

### Helping the user

The user may need help with the parts they do themselves: finding where the customer's files landed,
linking a folder to you, getting the finished workbook out of the session directory, handing it to
the Worldmaker app agent. Offer that help as it comes up rather than waiting to be asked.

What becomes of the workbook after you hand it over — starting the migration in Worldmaker, and what the
migration expects a workbook to be — is in `${CLAUDE_PLUGIN_ROOT}/docs/DOCUMENT_UPLOADING.md`.
