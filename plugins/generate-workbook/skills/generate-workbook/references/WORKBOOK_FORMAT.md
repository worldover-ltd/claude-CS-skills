# Workbook format

How to lay out `WORKBOOK.xlsx` so a person can read it and an app agent can parse it without
guessing. The rule underneath all of it is **tidy data**: one sheet per item, one row per item
instance, one column per field, one value per cell.

## Sheets

- One sheet per item in the entity model, named for the item in plural lower snake case:
  `products`, `raw_materials`, `formulations`, `ingredients`, `documents`.
- A `README` sheet first, before the data sheets. One row per data sheet with: sheet name, what item
  it holds, which column is the identifier, which columns point at other sheets, and which source
  files it came from. Anything you decided during the grilling that a reader would otherwise have to
  guess belongs here.
- Data starts at cell `A1` with the header row, values from row 2 down. No title banner, no logo
  row, no merged cells, no blank spacer rows or columns.

## Columns

- Header names in lower snake case, no spaces, no units, no line breaks: `trade_name`, `cas_number`.
- The identifier column comes first and is named `id`. When the item had no unique field in the
  source, generate one with a readable prefix — `PROD-001`, `RM-014` — and say so in `README`.
- Units live in the header, not the cell: `weight_kg` holding `12`, rather than `weight` holding
  `12 kg`.
- Dates as ISO 8601 text: `2026-07-29`.
- Identifiers and codes written as text so leading zeros survive: `007` stays `007`.
- An unknown value is an empty cell. Leave it empty rather than filling `N/A`, `-` or `unknown`.
- Values only — no formulas, no cross-sheet references.

## Relationships

- **One-to-many**: the many side carries the one side's id, in a column named `<item>_id`. A
  `formulations` row pointing at its product gets `product_id`.
- **Many-to-many**: its own link sheet named `<item_a>_<item_b>`, holding exactly the two id columns
  (`products_formulations` with `product_id` and `formulation_id`), plus any field that belongs to
  the pairing itself, such as `percentage`.
- **Many values in one field**: one row each in a link sheet. Keep one value per cell; a cell holding
  `RM-001; RM-002; RM-003` is a parse the app agent has to guess at.
- Every id referenced from another sheet exists in its own sheet. Check this before handing over, and
  report any that do not resolve rather than dropping the row.

## Human-readable finish

Apply to every data sheet: freeze the header row, bold it, turn on the autofilter, and set column
widths to fit their content. This costs a few lines and is what makes the file usable by the person
who has to check it.

## Writing it

Write the file with a script rather than cell by cell, so a correction is a re-run.

Confirm the writer works before generating anything, because a missing library surfaces as a broken
run at the last step:

- `python -c "import openpyxl"` — the default, and what the sibling `assign-documents` skill uses.
- On Windows, `python` is often the Microsoft Store stub that only prints an install prompt. Treat
  any "Python was not found" output as no Python at all.
- Fallback: Node with `exceljs`, which covers freeze panes, autofilter and widths equally.

Whichever you use, install into the session directory and keep the script at
`.workflow/active/${sessionId}/build_workbook.py` (or `.js`) so the run can be repeated.
