# Workbook format

How to lay out `WORKBOOK.xlsx` so a person can read it and an app agent can parse it without
guessing. The rule underneath all of it is **tidy data**: one sheet per item, one row per item
instance, one column per field, one value per cell.

## Sheets

- One sheet per item in the mapping, **named for the app table it feeds**: `products`,
  `raw_materials`, `formulations`, `documents`. The app agent reads this file against its own schema,
  so matching its names is what saves it from guessing.
- A `README` sheet first, before the data sheets. One row per data sheet with: sheet name, which app
  entity it feeds, which column is the identifier, which columns point at other sheets, and which
  source files it came from. Anything you decided during the grilling that a reader would otherwise
  have to guess belongs here — above all, which columns the app has no home for yet and will need as
  custom fields.
- Data starts at cell `A1` with the header row, values from row 2 down. No title banner, no logo
  row, no merged cells, no blank spacer rows or columns.

## Columns

- Header names match the app column the field feeds, exactly as `APP_SCHEMA.json` spells it. For a
  field the app has no column for, lower snake case, no spaces, no units, no line breaks:
  `trade_name`, `cas_number`.
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

Write the file with `openpyxl`, under whichever interpreter the preflight step resolved. Keep the
script at `.workflow/active/${sessionId}/build_workbook.py` and generate the workbook by running it,
rather than writing cells one at a time — a correction then costs a re-run.

The script has to run wherever the user is, so build paths with `pathlib` rather than joining strings,
and pass `encoding="utf-8"` on every text file you open — the default differs by platform and
silently mangles accented ingredient names on Windows.

Before handing over, load the file back and check what you wrote: every sheet present, every
cross-sheet id resolving, row counts matching what the mapping said to expect.
