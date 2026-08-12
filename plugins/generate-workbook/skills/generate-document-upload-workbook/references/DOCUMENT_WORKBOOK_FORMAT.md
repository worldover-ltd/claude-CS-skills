# Document upload workbook format

How to lay out `DOCUMENT_UPLOAD_WORKBOOK.xlsx`. The unit is the **attachment**: one row per document per
item. A document attached to two items gets two rows, and a document attached to none gets none — it goes
on the exception list instead.

Every row comes from `CLASSIFICATIONS.json`, and every template and section name comes from
`APP_TEMPLATES.json`. Nothing here invents a name: the migration can only land on words the app already has.

## Sheets

- One data sheet per entity, named `<table>_documents` as `APP_TEMPLATES.json` spells the table:
  `raw_materials_documents`, `products_documents`. The app agent reads this file against its own schema, so
  matching its table names is what saves it from guessing.
- A `Document Templates` sheet with `Name`, `id`, `entity` and `section_id`, one row per document template
  that appears anywhere in the workbook. The id is `dt_` followed by the first 12 hex characters of the
  SHA-256 of the lower-cased, stripped name, so the same template resolves to the same id across re-runs and
  across workbooks. `section_id` is the section that template belongs to on that entity, taken from that
  entity's `sections`.
- A `Document Sections` sheet with `label`, `key`, `id`, `entity` and `sort_order`, one row per section that
  holds at least one template the workbook uses. The id is `ds_` followed by the first 12 hex characters of
  the SHA-256 of `<entity>:<key>` — the entity is in the hash because the app scopes a section to one owner,
  so two entities with a "Safety" section have two different sections rather than one shared. The `key` is
  the label lower-cased with spaces as underscores (`Safety and Regulatory` → `safety_and_regulatory`), and
  `sort_order` is the order the user listed the sections in, counting from 0. Where the user gave no
  sections, this sheet has its header row and nothing under it.
- A `README` sheet first, before everything else. One row per data sheet with: sheet name, which entity it
  attaches documents to, which column holds the item identifier and which app column that is, the document
  count, and the folder the rows came from. Below that, the exceptions, one row each with the file name, its
  folder and why it is not in a data sheet — see the list below.
- Data starts at cell `A1` with the header row, values from row 2 down. No title banner, no merged cells,
  no blank spacer rows.

## Columns

In this order, on every data sheet:

| column | holds |
| --- | --- |
| the item identifier | the identifier `plan_batches.py` resolved, in a column named exactly as `APP_TEMPLATES.json` spells that entity's `identifierColumn` — `code`, `primary_identifier` |
| `document_template` | the document template's name, as the app's own list spells it |
| `documentTemplateId` | that template's id, matching the `Document Templates` sheet |
| `file_name` | the document's file name with its extension and no path: `SDS_2026.pdf` |
| `file_sha` | the document's SHA-256, lower-case hex |
| `source_folder_path` | the document's folder, relative to the folder the user gave, so any row can be traced back to what it was read from |
| `confidence` | the classifier's score, 0 to 1 |
| `evidence` | the one line of evidence it gave for that template |

`file_name` and `file_sha` are the two the migration agent looks for, and finding them is what makes it
expect documents at all — so they are spelled exactly like that, on every data sheet.

`confidence` and `evidence` are review aids rather than migration inputs: the migration ignores columns it
does not recognise, and these two let the user sort by confidence and see why each row says what it says.
Keep them last so the migration's columns stay together at the front.

A data row carries no section. A section groups templates rather than documents, so it is a property of the
template and lives on the `Document Templates` sheet — the same shape the app has, where
`section_attachments` links a section to a document template and never to a document.

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
| nothing could be read from it | `BATCHES.json` → `exceptions.unreadable` |
| no classifier answered for it | `CLASSIFICATIONS.json`, `review` starting `unread` |
| nothing in the app's list fitted | `CLASSIFICATIONS.json`, no `documentTemplate` |
| the classifier named a template the app does not have | `CLASSIFICATIONS.json`, `review` naming the proposal |
| the user described it rather than it being read | recorded as user-supplied during the run |

A template the classifier proposed and the app does not have is worth its own line in `README`, since
somebody has to create it in the app before the migration runs.

## Before handing it over

- Every row's identifier value appears in `BATCHES.json` for that document.
- Every row's `file_sha` appears in `DOCUMENTS.json`, and every `documentTemplateId` in
  `Document Templates`.
- Every `Document Templates` row carries a `section_id` that appears in `Document Sections`, or an empty
  `section_id` where the user gave no sections; every section listed holds at least one template.
- Every document in `DOCUMENTS.json` is in exactly one place: a data sheet row, or the `README` exception
  list. Counts across the two add up to the file count `map_tree.py` reported.

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
