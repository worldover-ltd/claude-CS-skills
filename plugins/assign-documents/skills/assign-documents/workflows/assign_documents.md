## TASK OBJECTIVE

Match each document to the item(s) it references and categorize it, then write the assignments back
into annotated copies of the customer's Excel files (one `<original>_with_documents.xlsx` per file).

## SESSION PATHS
Input:
  - EXCEL_FILES_ITEMS: .workflow/active/${sessionId}/EXCEL_FILES_ITEMS.md
  - DOCUMENT_FILES: .workflow/active/${sessionId}/DOCUMENT_FILES.json
  - UPLOAD_MANIFEST: .workflow/active/${sessionId}/UPLOAD_MANIFEST.json
    (the user-provided manifest of documents already uploaded to the customer's app;
     shape: `{ "documents": [ { "fileName": string, "storageKey": string, "sha": string } ] }`)
Outputs:
  - For each provided customer Excel file, an annotated copy named `<original>_with_documents.xlsx`
    written next to the original (see Step 5). No standalone report file is produced.


## INSTRUCTIONS

# Step 1

This workflow spawns many sub-agents and is token-intensive. If the `ultracode` effort mode is
available in this environment, prefer switching to it (```/effort ultracode```); if it is already
active, let the user know. If `ultracode` is not available, proceed anyway — it is a performance
preference, not a hard requirement.

# Step 2

Read the EXCEL_FILES_ITEMS.md for context.

# Step 3

Take all excel files mentioned in EXCEL_FILES_ITEMS.md and generate a json file with the following structure:

```json
{
  "excel_files": [
    {
      "SHA": "<EXCEL_FILE_SHA_VALUE>",
      "path": "<EXCEL_FILE_PATH>",
      "rows": [
        {
          "ref": "<EXCEL_REF>",
          "data": {
            "<COLUMN_KEY": "<COLUMN_VALUE>"
          }
        }
      ]
    }
  ]
}
```

where:
  - EXCEL_FILE_SHA_VALUE: SHA-256 value of the excel file
  - EXCEL_FILE_PATH: path to the excel file
  - EXCEL_REF: reference to the row in the excel file, formatted as `${EXCEL_SHA}::${TAB_KEY}::${ROW_NUMBER}`
    where EXCEL_SHA is the file's SHA-256 and ROW_NUMBER is the 1-based worksheet row number.
    The SHA prefix makes the ref globally unique across files (two files can share a tab name and
    row number), so Step 5 can route each edit back to the exact file/tab/row. TAB_KEY must not
    contain "::". Sub-agents echo this ref verbatim — their task is unchanged.
  - COLUMN_KEY: key of each excel column, one key on the object per column
  - COLUMN_VALUE: value of the excel column

Store the file on: .workflow/active/${sessionId}/EXCEL_FILES_DATA.json

# Step 4

Assign every document to the Excel row(s) it references (zero, one, or many) and categorize it, by
fanning the work out across sub-agents.

> **Critical — read before implementing.** The batch each agent works on MUST be partitioned in
> the orchestration code and passed to the agent as an **explicit, literal list of file paths**.
> Do NOT give agents the shared `DOCUMENT_FILES.json` plus a prose "handle indices X–Y"
> instruction — models miscount, which silently produces overlapping and dropped batches. The
> only thing that guarantees disjoint, complete coverage is the data each agent is actually given.
> Every fan-out MUST also be reconciled against the authoritative input list (see the reconcile
> loop below) so any gap surfaces instead of being hidden by duplicate results.

## 4.1 — Read the authoritative input (orchestrator, in the main loop)

Workflow scripts have no filesystem access, so read the inputs first and pass them into the
workflow via `args`:

1. Read `.workflow/active/${sessionId}/DOCUMENT_FILES.json` → the authoritative array of
   `{ SHA, path }` documents. This array is the source of truth for completeness.
2. Invoke the Workflow tool with:
   `args = { documents: <that array>, sessionId: "${sessionId}", pluginRoot: "${CLAUDE_PLUGIN_ROOT}" }`

## 4.2 — Workflow script

Run the following as the workflow. It chunks the document list **in code**, gives each agent its
own explicit slice, forces structured output with a schema, then reconciles and re-runs gaps.

```javascript
export const meta = {
  name: 'assign-documents-match',
  description: 'Match each document to an Excel row and categorize it, with reconciled fan-out',
  phases: [{ title: 'Match' }, { title: 'Reconcile' }],
}

const BATCH_SIZE = 10
const MAX_RECONCILE_ROUNDS = 2

// One result object PER input document (even documents with no match).
// Returning every input document is what lets us verify complete coverage.
// A document may match MULTIPLE items: row_refs holds every matched row.ref
// (empty array = no match). Categorization is per-document, not per-match.
const BATCH_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['results'],
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['doc_path', 'row_refs', 'category', 'is_new_category'],
        properties: {
          doc_path: { type: 'string' },                       // must equal an input path, verbatim
          row_refs: {                                          // every matched row.ref; [] = no match
            type: 'array',
            items: { type: 'string' },
          },
          category: { type: 'string' },                       // chosen/created category name, or "NONE"
          is_new_category: { type: 'boolean' },               // true if not from document_categories.txt
        },
      },
    },
  },
}

const { documents, sessionId, pluginRoot } = args

const chunk = (arr, n) =>
  Array.from({ length: Math.ceil(arr.length / n) }, (_, i) => arr.slice(i * n, i * n + n))

const promptFor = (batch) => `
### DOCUMENT FILES

Process exactly these ${batch.length} document files (and no others). Use the path verbatim as
"doc_path" in your output:

${batch.map((d, i) => `${i + 1}. ${d.path}`).join('\n')}

### INSTRUCTIONS

For EACH document file above, do the following:
- Read the document file and access its content.
- Read the Excel data at ".workflow/active/${sessionId}/EXCEL_FILES_DATA.json".
- Determine every item in the "rows" arrays of that file that the document references — a single
  document can relate to more than one item. Set "row_refs" to the list of ALL matching rows'
  "ref" values. If it matches none, set "row_refs" to an empty array [].
- Categorize the document by picking the most relevant category from
  "${pluginRoot}/skills/assign-documents/lib/document_categories.txt". If none fits, create a new
  category name (max 20 characters) and set "is_new_category" to true; otherwise false. When the
  category is "NONE", "is_new_category" is false.

Return one result object for EVERY document listed above — never omit one, even for "NONE"
matches. "doc_path" MUST equal the listed path exactly.
`

// Run one round of matching over a set of documents; returns a flat array of result objects.
async function matchRound(docs, phase) {
  const batches = chunk(docs, BATCH_SIZE)
  const perBatch = await parallel(
    batches.map((batch, i) => () =>
      agent(promptFor(batch), { label: `match:batch-${i}`, phase, schema: BATCH_SCHEMA })
        .then(r => (r?.results ?? []).filter(x => docs.some(d => d.path === x.doc_path)))
    )
  )
  return perBatch.filter(Boolean).flat()
}

// First pass.
phase('Match')
const byPath = new Map()                                       // dedup: first occurrence wins
for (const r of await matchRound(documents, 'Match')) {
  if (!byPath.has(r.doc_path)) byPath.set(r.doc_path, r)
}

// Reconcile against the authoritative list; re-run only the gaps.
phase('Reconcile')
let round = 0
let missing = documents.filter(d => !byPath.has(d.path))
while (missing.length && round < MAX_RECONCILE_ROUNDS) {
  round++
  log(`Reconcile round ${round}: ${missing.length} document(s) had no result — re-running.`)
  for (const r of await matchRound(missing, 'Reconcile')) {
    if (!byPath.has(r.doc_path)) byPath.set(r.doc_path, r)
  }
  missing = documents.filter(d => !byPath.has(d.path))
}

if (missing.length) {
  log(`WARNING: ${missing.length} document(s) still unmatched after ${MAX_RECONCILE_ROUNDS} rounds — they will be written as UNPROCESSED, not dropped.`)
}

// Return results aligned to the authoritative list. Every input document appears exactly once,
// each carrying zero or more matched row_refs.
return {
  results: documents.map(d =>
    byPath.get(d.path) ?? { doc_path: d.path, row_refs: [], category: 'NONE', is_new_category: false, unprocessed: true }
  ),
  unprocessed: missing.map(d => d.path),
}
```

## 4.3 — After the workflow

- The workflow returns exactly one result per input document, in the same order as
  `DOCUMENT_FILES.json`. Confirm the count equals the input count before continuing.
- If `unprocessed` is non-empty, tell the user which documents could not be matched after retries.
  These are carried into the output (Step 5), never silently dropped.

# Step 5 — annotate and write the customer Excel files

Produce an annotated copy of each excel file the user provided, carrying the assignment data back into the file itself.

Inputs available to you (the main agent) at this point:
- the workflow return value: `results` — one object per document `{ doc_path, row_refs[], category, is_new_category }`
- `UPLOAD_MANIFEST.json` — `{ "documents": [ { fileName, storageKey, sha } ] }`
- `DOCUMENT_FILES.json` — `{ SHA, path }` per document
- `EXCEL_FILES_DATA.json` — file/tab/row data, whose `rows[].ref` is `${EXCEL_SHA}::${TAB_KEY}::${ROW_NUMBER}`
- `EXCEL_FILES_ITEMS.md` — which tabs/columns identify items, and which columns are human-readable

## 5.1 — Join each document to its upload manifest entry

For each document in `results`, take its `SHA` from `DOCUMENT_FILES.json` (join by `path`), then find
the `UPLOAD_MANIFEST.json` entry with the same `sha` — that yields `fileName` and `storageKey`. Use
`fileName` only as a sanity check (warn on a basename mismatch). If a matched document has no
manifest entry, warn the user and omit it from the JSON column (still list its name in the
human-readable column). Join on `sha`, not filename — filenames may collide.

## 5.2 — Deterministic category → documentTemplateId map

Collect the set of categories that actually appear in `results` (exclude `"NONE"`; include any new
categories agents created). For each category name compute a stable id:

```
documentTemplateId = "dt_" + sha256(name.strip().lower()).hexdigest()[:12]
```

This makes the same category resolve to the same id across every file and across re-runs. Exception:
if a file already has a `Document Templates` tab containing a name, **reuse that tab's existing id**
for that name rather than the computed one.

## 5.3 — Invert assignments to per-(file, tab, row)

For each result, for each `ref` in `row_refs`, split on `"::"` into `(excel_sha, tab_key, row_number)`.
Group into `editsByFile[excel_sha][tab_key][row_number] = [ {fileName, storageKey, sha, category, documentTemplateId} ]`.
Resolve `excel_sha` → the file's `path` via `EXCEL_FILES_DATA.json`. Documents with empty `row_refs`
(including `unprocessed`) contribute no edits — they simply don't annotate any row.

## 5.4 — Write each annotated file

For every customer excel file, copy it to `<original>_with_documents.xlsx` **next to the original**,
then edit the copy:

1. **`Document Templates` tab** (columns `Name`, `id`): create it if absent; if present, append the
   assigned categories that aren't already listed (dedupe by `Name`, case-insensitive) — never
   remove or reorder existing rows.
2. For each item tab that has edits, add two columns (headers on the same header row Step 3 used):
   - **`Matched Documents`** — human-readable. **Insert** it next to the item's human-readable
     identifier column(s) (per `EXCEL_FILES_ITEMS.md`), in a sensible place. Value: the matched file
     names grouped by category, one line per category, e.g. `Certificate of Analysis (CoA): a.pdf, b.pdf`.
   - **`alreadyUploadedToSupabaseMatchedDocuments`** — machine-readable, appended as the **last**
     column. Value: a JSON string mirroring the manifest shape, holding that row's matched docs:
     `{"documents":[{"fileName":…,"storageKey":…,"sha":…,"documentTemplateId":…}, …]}`.
   - Only matched rows get values; leave the columns blank on all other rows.

Apply the edits with a script (below) rather than by hand — `openpyxl` preserves the workbook's other
tabs and data. Be careful: inserting a column mid-sheet shifts later columns; verify formulas,
merged cells, and styling on a sample file before trusting the result on the customer's real files.

```python
import json, hashlib, shutil, openpyxl

def template_id(name):
    return "dt_" + hashlib.sha256(name.strip().lower().encode()).hexdigest()[:12]

def col_index_by_header(ws, header_row, header):
    for c in range(1, ws.max_column + 1):
        if str(ws.cell(header_row, c).value).strip() == header:
            return c
    return None

def upsert_document_templates(wb, categories):
    ws = wb["Document Templates"] if "Document Templates" in wb.sheetnames else None
    if ws is None:
        ws = wb.create_sheet("Document Templates")
        ws.cell(1, 1, "Name"); ws.cell(1, 2, "id")
        existing = {}
        next_row = 2
    else:
        name_c = col_index_by_header(ws, 1, "Name") or 1
        id_c = col_index_by_header(ws, 1, "id") or 2
        existing = {str(ws.cell(r, name_c).value).strip().lower(): ws.cell(r, id_c).value
                    for r in range(2, ws.max_row + 1) if ws.cell(r, name_c).value}
        next_row = ws.max_row + 1
    for name in categories:
        if name.strip().lower() in existing:
            continue
        ws.cell(next_row, 1, name); ws.cell(next_row, 2, template_id(name))
        existing[name.strip().lower()] = template_id(name)
        next_row += 1
    return existing  # name(lower) -> id, authoritative for this file

# `plan` is what you build in 5.1–5.3, per file:
# {
#   "src": ..., "dst": ...,
#   "categories": [names...],                       # assigned categories (for the templates tab)
#   "tabs": [{
#       "tab": "products", "header_row": 1,
#       "human_before_header": "<existing header to insert Matched Documents before>",
#       "rows": [{"row": 7, "human": "...", "docs": [ {fileName, storageKey, sha, category} ]}]
#   }]
# }
def apply(plan):
    shutil.copyfile(plan["src"], plan["dst"])
    wb = openpyxl.load_workbook(plan["dst"])
    ids = upsert_document_templates(wb, plan["categories"])
    for t in plan["tabs"]:
        ws = wb[t["tab"]]; hr = t["header_row"]
        before = col_index_by_header(ws, hr, t["human_before_header"]) or (ws.max_column + 1)
        ws.insert_cols(before); ws.cell(hr, before, "Matched Documents")
        json_c = ws.max_column + 1; ws.cell(hr, json_c, "alreadyUploadedToSupabaseMatchedDocuments")
        for r in t["rows"]:
            ws.cell(r["row"], before, r["human"])
            docs = [{"fileName": d["fileName"], "storageKey": d["storageKey"], "sha": d["sha"],
                     "documentTemplateId": ids[d["category"].strip().lower()]}
                    for d in r["docs"] if d["category"].strip().lower() in ids]
            ws.cell(r["row"], json_c, json.dumps({"documents": docs}, ensure_ascii=False))
    wb.save(plan["dst"])
```

## 5.5 — Report

Tell the user the task is complete and list each `<original>_with_documents.xlsx` path. Surface any
documents that were `unprocessed` or had no manifest entry.
