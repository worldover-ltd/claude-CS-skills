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

**Work in progress.** Build the upload workbook for a Worldmaker app when the customer didn't supply
one, out of whatever they did send — zips, spreadsheets, Word documents, PDFs, exports.

Invoke it by running `/generate-workbook`, or ask Claude to "build a workbook from these files".

**What it does**

1. Checks it can reach `python3` and the `WorldoverProd` repos, and stops early if it can't.
2. Asks which customer and which app, resolves that to the app's repo, and reads the *app schema*
   out of it — the entities the app holds and how they relate.
3. Collects the customer's source files (with your confirmation) and reads every one of them.
4. Runs a grilling session to agree the *mapping* with you: which app entity each pile of data feeds,
   what identifies each item, which app field each column fills, and what has no home in the app yet.
5. Publishes an artifact — an ER diagram plus a preview of every sheet with real sample rows — and
   iterates on it until you approve.
6. Writes `WORKBOOK.xlsx` in tidy-data layout, with sheets and headers named after the app's own
   tables and columns so its agent doesn't have to guess.

Needs Python with `openpyxl`, and `gh` authenticated against the `WorldoverProd` organisation. Runs on
macOS, Linux and Windows.

Intermediate and output files are written under `.workflow/active/<sessionId>/` in your current
working directory.

## Repo layout

```
.claude-plugin/marketplace.json     # marketplace manifest (lists plugins)
plugins/
  assign-documents/
    .claude-plugin/plugin.json       # plugin manifest
    skills/assign-documents/         # the skill itself (SKILL.md + supporting files)
  generate-workbook/
    .claude-plugin/plugin.json
    skills/generate-workbook/         # SKILL.md + references/ + lib/
```

## License

MIT — see [LICENSE](LICENSE).
