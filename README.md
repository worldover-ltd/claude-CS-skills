# Worldover Skills — Claude Code Marketplace

A [Claude Code](https://claude.com/claude-code) plugin marketplace hosting skills for
document and compliance workflows.

## Install

```
/plugin marketplace add worldover-ltd/claude-CS-skills
/plugin install assign-documents
```

Then restart Claude Code (or reload plugins) when prompted.

## Plugins

### `assign-documents`

Categorize a set of documents and assign each one to an item found in a source of Excel
files, then produce a consolidated Excel report. Built for cosmetics, chemicals and other
substance-based industries.

Invoke it by running `/assign-documents`, or just ask Claude to "categorize these documents"
or "match these documents to items in this spreadsheet".

**What it does**

1. Collects the document files and the source Excel file(s) (with your confirmation).
2. Learns the structure of the Excel files and groups them by type.
3. Asks which items to assign documents to, and which tab/columns identify each item.
4. Fans out sub-agents to read each document, match it to an Excel row, and categorize it
   against a built-in taxonomy (`lib/document_categories.txt`).
5. Writes `ASSIGNED_DOCUMENTS.xlsx` into the run's session directory.

Intermediate and output files are written under `.workflow/active/<sessionId>/` in your
current working directory.

### `generate-workbook`

**Work in progress.** Two skills that build the workbook a Worldmaker app agent migrates from. Both read
the customer's app repo first, so the workbook is written in the app's own vocabulary.

Needs Python with `openpyxl`, and `gh` authenticated against the `WorldoverProd` organisation. Runs on
macOS, Linux and Windows. Intermediate and output files are written under `.workflow/active/<sessionId>/`
in your current working directory.

#### `generate-workbook` — the data

Build the upload workbook when the customer didn't supply one, out of whatever they did send — zips,
spreadsheets, Word documents, PDFs, exports.

Invoke it by running `/generate-workbook`, or ask Claude to "build a workbook from these files".

**What it does**

1. Preflights everything the run needs, in two parallel sub-agents — the document tooling via
   `verify-document-skills-requirements`, and its own prerequisites (a Python with `openpyxl`, plus `gh`
   access to the `WorldoverProd` repos) — and stops early if the latter aren't there.
2. Asks which customer and which app, resolves that to the app's repo, and reads the *app schema*
   out of it — the entities the app holds and how they relate.
3. Collects the customer's source files (with your confirmation) and reads every one of them.
4. Runs a grilling session to agree the *mapping* with you: which app entity each pile of data feeds,
   what identifies each item, which app field each column fills, and what has no home in the app yet.
5. Publishes an artifact — an ER diagram plus a preview of every sheet with real sample rows — and
   iterates on it until you approve.
6. Writes `WORKBOOK.xlsx` in tidy-data layout, with sheets and headers named after the app's own
   tables and columns so its agent doesn't have to guess.

#### `generate-document-upload-workbook` — the documents

Attach a folder of documents onto items that **already exist** in the app. The items are there, the
documents are already uploaded to the app's storage; this builds the workbook that links the two.

Invoke it by running `/generate-document-upload-workbook`, or ask Claude to "assign these documents to the
items already in the app".

**What it does**

1. Preflights the same prerequisites, then reads the app repo for the document side of its schema: which
   kinds of item can hold documents, how one attaches, and which document types the app knows.
2. Maps the folder you give it — *the tree* — and works out what each level of it means: which level names
   the kind of item, which one identifies the item, which one names the type of document, and which is
   noise.
3. Puts that reading to you branch by branch, with real folder names as evidence and item counts to
   check against.
4. **Stops if the tree can't be read.** Folder names are the only evidence for which item a document
   belongs to, and a guessed attachment is a document filed against the wrong substance. You get the exact
   folders that failed and what would fix them.
5. Joins each document to the upload manifest you exported from the app by SHA-256, not by file name — so
   two documents called `SDS.pdf` in different item folders each resolve to their own upload.
6. Takes each document's category from its folder, and only reads the documents whose folder doesn't say
   (that part is handed to `assign-documents`).
7. Publishes an artifact — the tree, the decisions per branch, real sample rows — and iterates until you
   approve.
8. Writes `DOCUMENT_UPLOAD_WORKBOOK.xlsx`: one row per attachment, carrying the item's identifier, the
   document type, and the `alreadyUploadedFileSHA` / `alreadyUploadedFileSupabaseStoragePath` pair.

Documents that were never uploaded, or that nothing could categorise, are listed on the workbook's
`README` sheet rather than dropped.

### `verify-document-skills-requirements`

Checks this machine can actually read the customer's file types before a run depends on it. Installs
Anthropic's official [document skills](https://github.com/anthropics/skills) (`xlsx`, `docx`, `pdf`)
if they aren't present, reads what each one declares it needs, then probes every tool for real. Missing
tooling is reported as the file types it blocks, with a pointer to the engineering team.

Each probe *exercises* the capability rather than importing it — a wrapper around a missing system binary
imports cleanly and dies on first use, which is exactly the trap worth catching. Installing anything is
put to you first, so a preflight never quietly rebuilds your Python.

Runs its probing in a sub-agent and returns just the verdict, so the calling run's context stays clear.

Invoke it by running `/verify-document-skills-requirements`. `generate-workbook` calls it in its
preflight step.

Requirement lists are read from the installed skills at run time rather than copied here, so they stay
correct as Anthropic updates them.

### `data-site`

Display a dataset as a site you can click through instead of a table in chat: an icon rail of big
concepts, a nav panel of lists inside each one, a table per list, and a detail page per row with
field blocks and document-style item lists.

The plugin ships a finished React app — the shell — that renders whatever a JSON config describes.
A run copies the shell into your working directory, writes the config from your data, and bundles
everything into one self-contained `bundle.html`. The config is validated with Zod first, so a bad
field is reported as a JSON path rather than a blank page.

Invoke it by running `/data-site`, or ask Claude to "show this data as a site".

Needs Node with npm. The shell lives at `plugins/data-site/skills/data-site/template`; each run
edits its own copy, never that folder.

## Repo layout

```
.claude-plugin/marketplace.json     # marketplace manifest (lists plugins)
plugins/
  assign-documents/
    .claude-plugin/plugin.json       # plugin manifest
    skills/assign-documents/         # the skill itself (SKILL.md + supporting files)
  generate-workbook/
    .claude-plugin/plugin.json
    skills/generate-workbook/                    # SKILL.md + references/ + lib/
    skills/generate-document-upload-workbook/    # SKILL.md + references/ + lib/
  verify-document-skills-requirements/
    .claude-plugin/plugin.json
    skills/verify-document-skills-requirements/
  data-site/
    .claude-plugin/plugin.json
    skills/data-site/                 # SKILL.md + template/ (the React shell)
```

## License

MIT — see [LICENSE](LICENSE).
