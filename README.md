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

**Work in progress.** Two skills that build the workbook a Worldmaker app agent migrates from, each written
in the app's own vocabulary — `generate-workbook` reads that vocabulary out of the app's repo, and
`generate-document-upload-workbook` is given it by you.

Needs the `extract-document-text` plugin installed alongside it, since both skills call it. Then
[`uv`](https://docs.astral.sh/uv/) to read the customer's files and Python with `openpyxl` to write the
workbook. `generate-workbook` additionally needs `gh` authenticated against the `WorldoverProd`
organisation; the document skill needs no repo access at all. Runs on macOS, Linux and Windows. Intermediate
and output files are written under `.workflow/active/<sessionId>/` in your current working directory.

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

1. Preflights everything the run needs in a sub-agent — `uv`, a Python with `openpyxl`, and `gh` access to
   the `WorldoverProd` repos — and stops early if any of the three is missing.
2. Asks which customer and which app, resolves that to the app's repo, and reads the *app schema*
   out of it — the entities the app holds and how they relate.
3. Collects the customer's source files (with your confirmation), extracts the whole pile to Markdown via
   `extract-document-text`, and reads what came out — profiling each spreadsheet so a candidate identifier
   column is a count rather than an impression.
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

This skill reads no repo. Instead you give it the app's **vocabulary**: the customer's list of document
templates, and the entity templates documents attach to — each with the sections on its page and which
document templates sit in each section.

**What it does**

1. Preflights two prerequisites in a sub-agent — `uv` and a Python with `openpyxl` — and stops early if
   either is missing.
2. Asks you for the vocabulary and reads it back as two tables to correct, including the table name and
   identifier column per entity, since those are what the workbook is built from.
3. Maps the folder you give it — *the tree* — for the one thing reading a document can't recover: which
   item each document belongs to. Levels are either the kind of item, the item's identifier, or noise.
4. Puts that reading to you branch by branch, with real folder names as evidence and item counts to check
   against, and **stops if the tree can't be read** — a guessed attachment is a document filed against the
   wrong substance. You get the exact folders that failed and what would fix them.
5. Hashes every document (SHA-256 is how the upload screen matches a file to its row later, so two files
   called `SDS.pdf` in different item folders stay distinct), extracts them all to Markdown, resolves each
   identifier **in code** from the branch rule, and cuts the work into batches of twenty.
6. Fans out up to twenty sub-agents at once on Claude Haiku 4.5, one per batch. Each reads one JSON file and
   returns, per document, the document template it is, the section that fits, a confidence score and a line
   of evidence — then a script joins the answers back, re-sends silent batches, and rejects any template or
   section name the app doesn't have.
7. Publishes an artifact — the tree, the decisions per branch, the templates and sections actually used,
   real sample rows, and the lowest-confidence rows worth spot-checking — and iterates until you approve.
8. Writes `DOCUMENT_UPLOAD_WORKBOOK.xlsx`: one row per attachment, carrying the item's identifier, the
   document template, the `file_name` / `file_sha` pair the migration looks for, and the confidence and
   evidence behind the classification — plus a sheet each for the templates and the sections.

Documents nothing could place are listed on the workbook's `README` sheet with the reason, rather than
dropped.

### `categorise-documents`

Give every file in a list its document type. One job, so anything that has already collected a pile of
documents can hand them over. Nothing in this repo calls it today —
`generate-document-upload-workbook` used to, and now classifies documents itself against the app's own
template list — so reach for it directly, or from your own skills, when you want types out of a pile of files
and nothing else.

Invoke it by running `/categorise-documents`, or ask Claude to "sort these documents by type".

Documents go through `extract-document-text` first — so that plugin needs to be installed alongside this
one — and a sub-agent then reads a document's Markdown, or the rendered page of a scan, rather than the file
itself. That is both cheaper and the only way a scanned page gets read at all.

Categories come from a vocabulary the caller passes — the app's own document type list, usually — falling
back to a built-in taxonomy of ~280 cosmetics, chemical and compliance document types. Reading is fanned
out in batches of ten, driven by a workflow script when there are enough documents to be worth it.

Nothing is quietly dropped: every document that goes out to a sub-agent has to answer, silent ones are
sent again, and whatever is still missing comes back marked `unread`. Documents that fit nothing in the
vocabulary come back marked `invented` rather than forced into the nearest category.

Input and output are two files in the run's session directory, `TO_CATEGORISE.json` and
`CATEGORIES.json`, joined on the document's path.

### `extract-document-text`

Turn a pile of document files into Markdown an agent can read. Everything the other skills read goes
through this one: `generate-workbook` for the customer's source files, `categorise-documents` for the
documents it has to identify.

Invoke it by running `/extract-document-text`, or ask Claude to "extract these documents".

The engine is [MarkItDown](https://github.com/microsoft/markitdown), which covers PDF, Word, Excel,
PowerPoint, Outlook messages, HTML, CSV, JSON, XML, EPub and ZIP. It runs on your machine and sends
nothing anywhere.

**Setup is one thing:** [`uv`](https://docs.astral.sh/uv/). It installs into your own home directory
without administrator rights, and the extraction script declares its own libraries inline — so `uv`
fetches those (and a Python, if this machine has none) on the first run and nothing else is ever installed.

**Scanned PDFs are handled rather than skipped.** A page with no text layer converts to nothing, so those
pages are rendered to PNGs and read as images instead — the first page by default, since one page is
usually enough to tell what a document is, and every page on request. Rendering goes through `pypdfium2`,
which needs no system binary, so it works where OCR through Tesseract can't be installed at all.

Input is a folder or a JSON list of paths; output is `EXTRACTED.json` plus an `extracted/` folder, both in
whichever directory you point it at. Every file in the manifest carries a `kind` — `text`, `image-only`,
`sparse-text`, `image`, `empty`, `unsupported`, `failed` or `missing` — recording what came of it and where
its content ended up.

It is a tool rather than a procedure: it converts what it is given and reports what it did, and what to do
with the result is the caller's.

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
  extract-document-text/
    .claude-plugin/plugin.json
    skills/extract-document-text/       # SKILL.md + lib/extract_documents.py
  data-site/
    .claude-plugin/plugin.json
    skills/data-site/                 # SKILL.md + template/ (the React shell)
```

## License

MIT — see [LICENSE](LICENSE).
