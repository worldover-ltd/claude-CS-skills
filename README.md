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

Both skills share two things in `docs/`. `DOCUMENT_UPLOADING.md` is the Worldmaker stages that follow a run,
which you do by hand: starting the migration with the finished workbook, then uploading the document files
themselves from the warning on the migration card. `PRESENTING.md` is how a run talks to you — what it puts
as a multiple-choice question rather than a paragraph, what it tables, and the three places it draws a
diagram. It sits on top of two vendored MIT skills in `vendor/`: `communication-style` from
[tzachbon/smart-ralph](https://github.com/tzachbon/smart-ralph) for the shape of a message, and
`mermaid-diagrams` from [ccheney/robust-skills](https://github.com/ccheney/robust-skills) for drawing one.
Both are copies rather than dependencies, so there is nothing extra to install; `vendor/NOTICE.md` records
the upstream commit and what was cut.

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

Attach a folder of documents onto items that **already exist** in the app. The items are there and the
documents are a folder on your computer; this builds the workbook that links the two. The files themselves
are uploaded at the end, out of the migration.

Invoke it by running `/generate-document-upload-workbook`, or ask Claude to "assign these documents to the
items already in the app".

**What it does**

1. Preflights the same prerequisites, then reads the app repo for the document side of its schema: which
   kinds of item can hold documents, how one attaches, which document templates the app knows and how it
   groups them into sections.
2. Maps the folder you give it — *the tree* — and works out what each level of it means: which level names
   the kind of item, which one identifies the item, which one names the type of document, and which is
   noise.
3. Puts that reading to you branch by branch, with real folder names as evidence and item counts to
   check against.
4. **Stops if the tree can't be read.** Folder names are the only evidence for which item a document
   belongs to, and a guessed attachment is a document filed against the wrong substance. You get the exact
   folders that failed and what would fix them.
5. Hashes every document, since SHA-256 is how the upload screen matches a file to its row later — so
   two documents called `SDS.pdf` in different item folders stay distinct.
6. Takes each document's **template** — what kind of document it is — from its folder, and fans sub-agents
   out to read only the documents whose folder doesn't say.
7. Groups those templates into **sections** per kind of item, the way they'll sit on the item's page, and
   puts the grouping to you to move, rename or merge.
8. Publishes an artifact — the tree, the decisions per branch, the sections, real sample rows — and
   iterates until you approve.
9. Writes `DOCUMENT_UPLOAD_WORKBOOK.xlsx`: one row per attachment, carrying the item's identifier, the
   document template, and the `file_name` / `file_sha` pair the migration looks for, plus a sheet each for
   the templates and the sections.

Documents nothing could place are listed on the workbook's `README` sheet rather than dropped.

### `categorise-documents`

Give every file in a list its document type. One job, so anything that has already collected a pile of
documents can hand them over: `generate-document-upload-workbook` calls it for the documents whose folder
name doesn't say what they are.

Invoke it by running `/categorise-documents`, or ask Claude to "sort these documents by type".

Categories come from a vocabulary the caller passes — the app's own document type list, usually — falling
back to a built-in taxonomy of ~280 cosmetics, chemical and compliance document types. Reading is fanned
out in batches of ten, driven by a workflow script when there are enough documents to be worth it.

Nothing is quietly dropped: every document that goes out to a sub-agent has to answer, silent ones are
sent again, and whatever is still missing comes back marked `unread`. Documents that fit nothing in the
vocabulary come back marked `invented` rather than forced into the nearest category.

Input and output are two files in the run's session directory, `TO_CATEGORISE.json` and
`CATEGORIES.json`, joined on the document's path.

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
    docs/                                        # shared across the plugin's skills
    vendor/                                      # MIT copies of third-party skills, used as references
    skills/generate-workbook/                    # SKILL.md + references/ + lib/
    skills/generate-document-upload-workbook/    # SKILL.md + references/ + lib/
  categorise-documents/
    .claude-plugin/plugin.json
    skills/categorise-documents/                 # SKILL.md + references/ + lib/
  verify-document-skills-requirements/
    .claude-plugin/plugin.json
    skills/verify-document-skills-requirements/
  data-site/
    .claude-plugin/plugin.json
    skills/data-site/                 # SKILL.md + template/ (the React shell)
```

## License

MIT — see [LICENSE](LICENSE).
