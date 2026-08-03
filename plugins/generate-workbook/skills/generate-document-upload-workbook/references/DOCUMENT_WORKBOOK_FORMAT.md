# Document upload workbook format

How to lay out `DOCUMENT_UPLOAD_WORKBOOK.xlsx`. The unit is the **attachment**: one row per document per
item. A document attached to two items gets two rows, and a document attached to none gets none — it goes
on the exception list instead.

## Sheets

- One data sheet per target entity, named `<entity_table>_documents`: `raw_materials_documents`,
  `products_documents`. The app agent reads this file against its own schema, so matching its table names
  is what saves it from guessing.
- A `Document Templates` sheet with `Name` and `id`, one row per document type that appears anywhere in the
  workbook. Compute the id the way `assign-documents` does — `dt_` followed by the first 12 hex characters
  of the SHA-256 of the lower-cased, stripped name — so a type resolves to the same id in both flows and
  across re-runs.
- A `README` sheet first, before everything else. One row per data sheet with: sheet name, which app entity
  it attaches documents to, which column holds the item identifier and which app column that is, the
  document count, and the folder the rows came from. Below that, the exceptions, one row each with the file
  name, its folder and why it is not in a data sheet: no manifest entry, so never uploaded; no category; or
  a folder the user could not resolve to an item.
- Data starts at cell `A1` with the header row, values from row 2 down. No title banner, no merged cells,
  no blank spacer rows.

## Columns

In this order, on every data sheet:

| column | holds |
| --- | --- |
| the item identifier | the anchor value, in a column named exactly as the app spells the column it looks the item up by — `code`, `primary_identifier` |
| `document_category` | the document type's name, as the app's own list spells it |
| `documentTemplateId` | that type's id, matching the `Document Templates` sheet |
| `file_name` | the document's file name, as the manifest holds it |
| `alreadyUploadedFileSHA` | the document's SHA-256, lower-case hex |
| `alreadyUploadedFileSupabaseStoragePath` | the `storageKey` from the manifest entry that SHA matched |
| `source_folder_path` | the document's folder, relative to the folder the user gave, so any row can be traced back to what it was read from |

Where the app attaches documents through a link table rather than a column, the identifier column still
comes first and still names the item — the app agent resolves the link. Say which shape the app has in
`README`.

Every value is text as written: identifiers keep leading zeros, SHAs and storage paths are never
reformatted, and an unknown is an empty cell rather than `N/A`. No formulas, no cross-sheet references.

## Before handing it over

- Every row's identifier value appears in the anchor level of `TREE.json`.
- Every row's SHA appears in `UPLOAD_MANIFEST.json`, and every `documentTemplateId` in
  `Document Templates`.
- Every document in `DOCUMENTS.json` is in exactly one place: a data sheet row, or the `README` exception
  list. Counts across the two add up to the file count `map_tree.py` reported.

## Human-readable finish, and writing it

Both are as `${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/references/WORKBOOK_FORMAT.md` describes —
frozen bold header, autofilter, fitted column widths, and a `build_workbook.py` in the session directory
that is run rather than a workbook written cell by cell. Add one thing to its checks: load the file back
and confirm the three conditions above.
