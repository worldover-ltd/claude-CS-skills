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

## Repo layout

```
.claude-plugin/marketplace.json     # marketplace manifest (lists plugins)
plugins/
  assign-documents/
    .claude-plugin/plugin.json       # plugin manifest
    skills/assign-documents/         # the skill itself (SKILL.md + supporting files)
```

## License

MIT — see [LICENSE](LICENSE).
