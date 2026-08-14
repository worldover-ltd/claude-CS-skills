# Document upload workbook format

How to lay out `DOCUMENT_UPLOAD_WORKBOOK.xlsx`. The unit is the **attachment**: one row per document per
item. A document attached to two items gets two rows, and a document attached to none gets none — it goes
on `IGNORED_FILES` or `FILES_WITH_ISSUES` instead.

Every row comes from `CLASSIFICATIONS.json`, and every id, template and section comes from
`WORKFLOW.json`. Nothing here invents a name or an id: the migration can only land on what the app
already has, and the export already carries it.

## Where it goes

**Beside the documents, not in the session directory**: `<the folder the user gave>/DOCUMENT_UPLOAD_WORKBOOK.xlsx`.
The user opens it against the folder it describes, and a workbook two levels deep in `.workflow/active/`
is one they have to be told how to find.

That puts the file inside the folder a later run walks, so `map_tree.py` and `hash_documents.py` both skip
it by name — a run never reads its own output as though it were a customer's document. Build it in the
session directory if that is easier, but the copy that is handed over lives with the documents.

## Sheets

Three named sheets come first, in this order, before any data sheet. Every file under the folder is on
exactly one of them or on a data sheet.

- **`README`** — what the run did. One row per data sheet with: sheet name, which *item_kind* it attaches
  documents to, which column holds the item identifier and which app column that is, the document count,
  how many of that table's items the documents reached, and the folder the rows came from. Then the
  counts that let the totals be checked: files in the folder, files carried, attachments written, files
  ignored, files with issues. Then the two blocks of work for a person in the app — templates to create
  and templates no section renders — described under "What needs a person" below. No per-file rows: the
  two sheets after it hold those.
- **`IGNORED_FILES`** — one row per file nobody wanted, with `file_name`, `source_folder_path` and
  `reason`. These are decisions, not failures: the exclusion gate's rules (`in a folder named 'Oud'`,
  `a .msg file`), plus anything the user said to leave out during the run. The rule that caught it is the
  reason, in the words `EXCLUSIONS.json` recorded.
- **`FILES_WITH_ISSUES`** — one row per file the run could not attach, with `file_name`,
  `source_folder_path`, `reason` and, where there is one, the `evidence` the classifier gave. Each reason
  is somebody's next action, in the words of the step that found it — see the list below.

Keeping the two apart is the point of having two sheets. A file on `IGNORED_FILES` needs nobody: it is
there so the totals add up and so a rule that caught more than intended is visible. Every file on
`FILES_WITH_ISSUES` needs somebody, and on a real folder the second list is the short one — mixing them
buries it.

Then the data and lookup sheets:

- One data sheet per *item_kind*, named `<table>_documents` as `WORKFLOW.json` spells the table:
  `raw_materials_documents`, `products_documents`. Several *item_template*s share one table and so share
  one sheet. The app agent reads this file against its own schema, so matching its table names is what
  saves it from guessing.
- A `Document Templates` sheet with `name`, `id`, `table`, `item_template`, `section_id` and `is_new` —
  one row per template **per *item_template* it appears under**, since the same template sits in a
  different section on each. The `id` is the app's own `documentTemplates[].id`, copied, never derived.
- A `Document Sections` sheet with `label`, `key`, `id`, `item_template`, `table`, `sort_order` and
  `is_new`, one row per section that holds at least one template the workbook uses. The app's export carries no section id,
  so this is the one id the workbook derives: `ds_` followed by the first 12 hex characters of the SHA-256
  of `<item_template>:<key>`. The *item_template* is in the hash because the app scopes a section to one
  owner, so two *item_template*s with a "Safety" section have two sections rather than one shared. The
  `key` is the label lower-cased with spaces as underscores (`Safety and Regulatory` →
  `safety_and_regulatory`), and `sort_order` is the section's own order in `documentSections`, counting
  from 0.
- Data starts at cell `A1` with the header row, values from row 2 down. No title banner, no merged cells,
  no blank spacer rows.

### `is_new`, on both reference sheets

`yes` where the app does not have this template or section yet and somebody must create it, `no` where it
came from the export. Filled yellow for `yes`, green for `no` — the only colour anywhere in the workbook,
and it earns the exception because these two sheets are the ones a person reads to decide what to build
before the migration runs. On one real export, 68 of 82 template rows had no section, so most of what the
section step returns is new; a sheet that does not say which is which is a sheet nobody can act on.

Two things to get right, because both have already gone wrong once:

- **openpyxl reads a fill back as `00FFC7CE`, not `FFFFC7CE`.** Compare on the last six hex digits or the
  verification below fails against a file it has just written correctly.
- **`is_new` is a column, not a formatting convention.** The colour is for the eye; the word is what any
  later step reads. A run that writes only the fill has written nothing.

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

## What goes on `FILES_WITH_ISSUES`

Every file that is not a data row and was not ignored, one row each, with its reason in the words of
whichever step found it. The reasons, and where each comes from:

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

Each of these is somebody's next action, so the reason is carried in these words rather than a generic
"skipped". Sort the sheet by reason, so the run of forty documents waiting on one missing template reads
as one problem rather than forty.

## What goes on `IGNORED_FILES`

One row per file, with the rule that caught it as the reason: `in a folder named 'Oud'`, `a .msg file`.
Both come straight from `EXCLUSIONS.json`'s `files`, which already records the rule per file.

**Ignored is not failed.** These are the user's own decisions from the gate, and they are listed per file
rather than summarised per rule so that a rule which caught more than they intended is visible — a count
of `4,102 — in a folder named 'Oud'` cannot show them that it also swallowed a live folder somebody named
`Oud` by mistake. `README` carries the per-rule totals; this sheet carries what those totals are made of.

## What needs a person, on `README`

Two blocks, both grouped rather than per-file, because the action is taken once and clears many documents:

- **Templates to create** — one row per proposed name with the number of documents waiting on it, from
  `CLASSIFICATIONS.json`'s `proposedTemplates`. Create the template once and every document under it
  becomes attachable.
- **Templates no section renders** — one row per *item_template* and template, listing the sections that
  item template does have, from `unarrangedTemplates`. Somebody arranges the template into one of them in
  the app.

The documents themselves still appear on `FILES_WITH_ISSUES`, one row each, so nothing is only ever a
count. These blocks are the short version that says what to actually do.

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
- Every file under the folder is in exactly one place: a data sheet row, an `IGNORED_FILES` row, or a
  `FILES_WITH_ISSUES` row. Distinct file paths across the three add up to the count `map_tree.py`
  reported, less the workbook itself. Excluded files never enter `DOCUMENTS.json`, so the tree's total is
  the only figure all three reconcile against — and a document attached to two items is two data rows but
  one file, so count paths rather than rows.
- Two rows carrying the same `file_sha` and the same `table` carry the same `document_template`. One
  reading covers every copy of one content on one table, so a difference here means the fan-out went
  wrong rather than that two classifiers disagreed.
- Every `is_new` cell says `yes` or `no`, and every `yes` is filled yellow and every `no` green. Compare
  fills on the last six hex digits — see above.
- Two rows on the same `table` whose documents are printed on the same *form* carry the same
  `document_template`, unless a person marked that form as splitting by value. That is ADR-0005's claim
  written as a check: one answer stood for all of them, so a difference means the fan-out lost track of
  which form a document belongs to.

## Human-readable finish

Apply to every sheet that has a header row — the data sheets, `IGNORED_FILES` and `FILES_WITH_ISSUES`:
freeze the header row, bold it, turn on the autofilter, and set column widths to fit their content. This
costs a few lines and is what makes the file usable by the person who has to check it. On the two file
lists the autofilter is the whole point: it is how somebody reads one reason at a time.

The `is_new` fills on the two reference sheets are the only colour in the workbook. Everything else stays
unshaded on purpose: shading that means something is worth reading, and shading that is decoration
teaches a reader to ignore both.

## Writing it

Write the file with `openpyxl`, under whichever interpreter the preflight step resolved. Keep the script
at `.workflow/active/${sessionId}/build_workbook.py` and generate the workbook by running it, rather than
writing cells one at a time — a correction then costs a re-run.

Write it to `<the folder the user gave>/DOCUMENT_UPLOAD_WORKBOOK.xlsx`. If that path is open in Excel the
write fails with a permission error; say so and ask them to close it rather than writing to a second name,
since two workbooks in one folder is the thing that gets the wrong one uploaded.

The script has to run wherever the user is, so build paths with `pathlib` rather than joining strings,
and pass `encoding="utf-8"` on every text file you open — the default differs by platform and silently
mangles accented names on Windows.

Before handing over, load the file back and confirm the four conditions above.
