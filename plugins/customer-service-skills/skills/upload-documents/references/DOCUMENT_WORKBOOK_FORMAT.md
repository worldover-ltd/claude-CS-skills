# Document upload workbook format

How to lay out `DOCUMENT_UPLOAD_WORKBOOK.xlsx`. The unit is the **attachment**: one row per document per
item. A document attached to two items gets two rows, and a document attached to none gets none — it goes
on the exception list instead.

Every row comes from `CLASSIFICATIONS.json`, and every id, template and section comes from
`WORKFLOW.json`. Nothing here invents a name or an id: the migration can only land on what the app
already has, and the export already carries it.

## Sheets

- One data sheet per *item_kind*, named `<table>_documents` as `WORKFLOW.json` spells the table:
  `raw_materials_documents`, `products_documents`. Several *item_template*s share one table and so share
  one sheet. The app agent reads this file against its own schema, so matching its table names is what
  saves it from guessing.
- A `Document Templates` sheet with `name`, `id`, `table`, `item_template` and `section_id` — one row per
  template **per *item_template* it appears under**, since the same template sits in a different section on
  each. The `id` is the app's own `documentTemplates[].id`, copied, never derived.
- A `Document Sections` sheet with `label`, `key`, `id`, `item_template`, `table` and `sort_order`, one row
  per section that holds at least one template the workbook uses. The app's export carries no section id,
  so this is the one id the workbook derives: `ds_` followed by the first 12 hex characters of the SHA-256
  of `<item_template>:<key>`. The *item_template* is in the hash because the app scopes a section to one
  owner, so two *item_template*s with a "Safety" section have two sections rather than one shared. The
  `key` is the label lower-cased with spaces as underscores (`Safety and Regulatory` →
  `safety_and_regulatory`), and `sort_order` is the section's own order in `documentSections`, counting
  from 0.
- A `README` sheet first, before everything else. One row per data sheet with: sheet name, which
  *item_kind* it attaches documents to, which column holds the item identifier and which app column that
  is, the document count, how many of that table's items the documents reached, and the folder the rows
  came from. Below that, the exceptions, one row each with the file name, its folder and why it is not in
  a data sheet — see the list below.
- Data starts at cell `A1` with the header row, values from row 2 down. No title banner, no merged cells,
  no blank spacer rows.

## Columns

In this order, on every data sheet:

| column | holds |
| --- | --- |
| the item identifier | the identifier that matched an item in `ITEMS.csv`, in a column named exactly as `WORKFLOW.json` spells that table's `identifierColumn` — `code`, `sku` |
| `item_id` | that item's database key, copied from `ITEMS.csv` |
| `document_template` | the document template's name, as the app's own list spells it |
| `documentTemplateId` | that template's app id, matching the `Document Templates` sheet |
| `file_name` | the document's file name with its extension and no path: `SDS_2026.pdf` |
| `file_sha` | the document's SHA-256, lower-case hex |
| `item_template` | the *item_template* the item is on, which is what decides its sections |
| `source_folder_path` | the document's folder, relative to the folder the user gave, so any row can be traced back to what it was read from |
| `confidence` | the gap between the classifier's pick and its runner-up, 0 to 1 — not how legible the document was |
| `evidence` | the one line of evidence it gave for that template |
| `quote` | the line it copied out of the document, which is what was checked against the file |

`file_name` and `file_sha` are the two the migration agent looks for, and finding them is what makes it
expect documents at all — so they are spelled exactly like that, on every data sheet.

`item_id` is the item's own key, so a row can be checked against the app without going through the
identifier at all. The migration still finds items by the identifier column; this is the column that makes
a wrong attachment provable rather than arguable.

`confidence`, `evidence`, `quote` and `item_template` are review aids rather than migration inputs: the
migration ignores columns it does not recognise, and these let the user sort by confidence and see why each
row says what it says. Keep them behind the migration's own columns.

`confidence` is a **margin**, not a legibility score, and the README says so where the user will read it.
A row at 0.55 is one where two templates fitted, not one where the document was hard to read — sorting by
it surfaces the genuinely ambiguous documents rather than the badly-scanned ones.

A data row carries no section. A section groups templates rather than documents, so it is a property of the
template and lives on the `Document Templates` sheet — the same shape the app has, where
`section_attachments` links a section to a document template and never to a document. Nobody chooses it:
the section is whichever one on that row's *item_template* renders the template the document turned out to
be, which is why one document under two *item_template*s can sit in two differently-named sections.

Where the app attaches documents through a link table rather than a column, the identifier column still
comes first and still names the item — the app agent resolves the link. Say which shape the app has in
`README`.

Every value is text as written: identifiers keep leading zeros, SHAs are never reformatted or
upper-cased, and an unknown is an empty cell rather than `N/A`. No formulas, no cross-sheet references.

## The exception list

Every document that is not a data row appears on `README` with its reason, in the words of whichever step
found it. The reasons, and where each comes from:

| reason | from |
| --- | --- |
| no branch covered its folder | `BATCHES.json` → `exceptions.unbranched` |
| its branch rule yielded no identifier | `BATCHES.json` → `exceptions.unidentified` |
| no item in the app has that identifier | `BATCHES.json` → `exceptions.unmatched` |
| several items share that identifier, so it names none | `BATCHES.json` → `exceptions.ambiguous` |
| the item it names is archived | `BATCHES.json` → `exceptions.archived` |
| nothing could be read from it | `BATCHES.json` → `exceptions.unreadable` |
| no classifier answered for it | `CLASSIFICATIONS.json`, `review` starting `unread` |
| the classifier could not be shown to have read it | `CLASSIFICATIONS.json`, `review` naming the receipt or the quotation |
| two readings settled it differently | `CLASSIFICATIONS.json`, `review` saying it was read twice |
| nothing fitted and nothing was proposed | `CLASSIFICATIONS.json`, no `documentTemplate` and no `proposedTemplate` |
| it proposes a template the app does not have | `CLASSIFICATIONS.json`, `proposedTemplate` |
| the template named is not one the app allows there | `CLASSIFICATIONS.json`, `review` naming the proposal |
| no section on that *item_template* renders that template | `CLASSIFICATIONS.json`, `review` saying it sits in no section |
| the user described it rather than it being read | recorded as user-supplied during the run |
| **excluded by decision** | `EXCLUSIONS.json`, with the rule that caught it |

Each of these is somebody's next action, so `README` carries the reason in these words rather than a
generic "skipped".

**Excluded is not failed, and the two do not share a list.** Everything above is a file the run could not
place; an exclusion is a file the user decided not to migrate, back at the gate before anything was read.
Those go in their own block, **as a count per rule** — `1,263 — a .msg file`, `4,102 — in a folder named
'Oud'` — rather than as thousands of rows. The user made that call and does not need it read back to them
one file at a time; what they need is to be able to check the totals and see that nothing went missing
under a rule they did not intend.

**Proposals get their own block on `README`, above the per-document list**: one row per proposed template
with its name and the number of documents waiting on it, and the same for templates no section renders with the
*item_template* they were proposed for. Create the template once and every document under it becomes
attachable, so a list of names is the useful artefact and a list of documents is not. The counts come from
`CLASSIFICATIONS.json`'s `proposedTemplates` and `unarrangedTemplates`.

Two more need a person in the app rather than in the folder: a **template the app does not allow on that
table**, which somebody has to permit before the migration runs, and an **archived item**, which somebody
has to unarchive if its documents are wanted.

## Before handing it over

- Every row's identifier value and `item_id` come from the same `ITEMS.csv` row, and that row is not
  archived.
- Every row's `file_sha` appears in `DOCUMENTS.json`, and every `documentTemplateId` in
  `Document Templates` — and in `WORKFLOW.json`, since the workbook derives no template id.
- Every `Document Templates` row names a template the app allows on that row's `table`, and carries either
  a `section_id` that appears in `Document Sections` or an empty one where no section was picked; every
  section listed holds at least one template.
- Every document in `DOCUMENTS.json` is in exactly one place: a data sheet row, or the `README` exception
  list. Those two plus `EXCLUSIONS.json`'s count add up to the file count `map_tree.py` reported — the
  excluded files are not in `DOCUMENTS.json` at all, so the tree's total is the only figure all three
  reconcile against.
- Two rows carrying the same `file_sha` and the same `table` carry the same `document_template`. One
  reading covers every copy of one content on one table, so a difference here means the fan-out went
  wrong rather than that two classifiers disagreed.

## Human-readable finish

Apply to every data sheet: freeze the header row, bold it, turn on the autofilter, and set column widths
to fit their content. This costs a few lines and is what makes the file usable by the person who has to
check it.

## Writing it

Write the file with `openpyxl`, under whichever interpreter the preflight step resolved. Keep the script
at `.workflow/active/${sessionId}/build_workbook.py` and generate the workbook by running it, rather than
writing cells one at a time — a correction then costs a re-run.

The script has to run wherever the user is, so build paths with `pathlib` rather than joining strings,
and pass `encoding="utf-8"` on every text file you open — the default differs by platform and silently
mangles accented names on Windows.

Before handing over, load the file back and confirm the four conditions above.
