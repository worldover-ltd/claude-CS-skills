---
name: generate-workbook
description: "Build the upload workbook for a Worldmaker app when the customer did not supply one. Triggers on \"generate-workbook\", or when the user wants a workbook/spreadsheet built out of raw customer source files (zip, excel, docx, pdf, export) so an app agent can upload or migrate that data."
allowed-tools: Skill, AskUserQuestion, TodoWrite, Read, Write, Edit, Bash, Glob, Grep, Artifact
---

### Status

Work in progress. The process below is a first pass and will change with use.

### Context

The user is on the Customer Service team and is not a developer. Put every question in plain
business language — items, names, codes, "which of these belongs to which" — and keep column
types, file formats and scripting out of what they have to decide.

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

### The entity model

Every sheet, column and row in the finished workbook comes from the **entity model**: the items to
upload and how they connect. Hold it at `.workflow/active/${sessionId}/ENTITY_MODEL.md` and update
it as each answer lands, so the file is always what you would show the user right now.

The entity model is complete when all four hold for **every** item:

- **name** — what the item is (products, raw materials, formulations, ingredients, documents, …).
- **identifier** — the field whose value is unique for one item ("id", "primary identifier", "code",
  "SKU"), or a recorded decision that the item has none and the workbook will carry a generated one.
- **fields** — every piece of data to upload for that item, each traced to the source file and
  location it was read from.
- **relationships** — every link to another item, with cardinality in both directions. A product has
  many formulations; a formulation belongs to many products; a raw material has at most one
  formulation; a formulation holds ingredients, raw materials, or other formulations.

### Process

# Step 1 — collect the source files

Ask the user for the files to build the workbook from, and wait for them to name specific files or a
folder. Then write back a sample of the file names (10 at most) in a list, plus the total count, and
ask the user to check it.

Done when the user confirms the list.

# Step 2 — read what is in them

Read every source file and note what each one holds: item names, headers, tab names, row counts,
which fields look unique. Follow
`${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/references/EXTRACTING_SOURCES.md` for zips, Excel
files, Word documents, PDFs and scans.

Done when every source file is either read or reported to the user as unreadable with the reason.

# Step 3 — grill out the entity model

Invoke the `grilling` skill and interview the user until the **entity model** is complete on all four
counts above.

Look facts up in the source files yourself and bring them as your recommended answer — "this column
has 412 distinct values across 412 rows, so it looks like the unique code; confirm?" beats asking the
user what the unique code is. The decisions are theirs; the digging is yours.

Between questions, show the shape so far as a small markdown table per item — those render in the
user's terminal where a diagram does not.

Done when the completion test in "### The entity model" holds for every item, with no field left
untraced and no relationship left with an open end.

# Step 4 — show the workbook before building it

Load the `artifact-design` skill, then publish one artifact to
`.workflow/active/${sessionId}/entity_model.html` holding, in this order:

1. A mermaid ER diagram of the items and their relationships.
2. One card per item: its identifier, its fields, what it links to.
3. A preview of each sheet the workbook will have — real header row, and three to five sample rows
   taken from the actual source data.

The sheet preview is what the user can judge, so fill it with real values rather than placeholders.

Iterate: take their corrections, update `ENTITY_MODEL.md`, republish to the same file path so the URL
holds. Done when the user approves what the artifact shows.

# Step 5 — write the workbook

Build the Excel file per
`${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/references/WORKBOOK_FORMAT.md`, writing to
`.workflow/active/${sessionId}/WORKBOOK.xlsx`.

Done when every item in the entity model has its sheet, every relationship is carried by a real
column or link sheet, and every row traces back to a source file.

# Step 6 — hand it over

Give the user the full path to `WORKBOOK.xlsx`, one line per sheet saying what is in it, and the two
or three things worth spot-checking before they feed it to the app agent — the ones you had least
evidence for.

### Helping the user

The user may need help with the parts they do themselves: finding where the customer's files landed,
linking a folder to you, getting the finished workbook out of the session directory, handing it to
the Worldmaker app agent. Offer that help as it comes up rather than waiting to be asked.
