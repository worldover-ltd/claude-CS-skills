## TASK OBJECTIVE

Generate a json file containing all of the relevant data of each excel file as described on "### Phase 1"

## SESSION PATHS
Input:
  - EXCEL_FILES_ITEMS: .workflow/active/${sessionId}/EXCEL_FILES_ITEMS.md
  - DOCUMENT_FILES: .workflow/active/${sessionId}/DOCUMENT_FILES.json
Outputs:
  - ASSIGNED_DOCUMENTS: .workflow/active/${sessionId}/ASSIGNED_DOCUMENTS.xlsx


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
  - EXCEL_REF: reference to the row in the excel file, formatted as such: `${TAB_KEY}::${ROW_NUMBER}`
  - COLUMN_KEY: key of each excel column, one key on the object per column
  - COLUMN_KEY: value of the excel column

Store the file on: .workflow/active/${sessionId}/EXCEL_FILES_DATA.json

# Step 4

Assign every document to an Excel row (or "NONE") and categorize it, by fanning the work out
across sub-agents.

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

// One result object PER input document — including non-matches (row_ref: "NONE").
// Returning every input document is what lets us verify complete coverage.
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
        required: ['doc_path', 'row_ref', 'category', 'is_new_category'],
        properties: {
          doc_path: { type: 'string' },                       // must equal an input path, verbatim
          row_ref: { type: 'string' },                        // matched row.ref, or "NONE"
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
- Determine whether the document references any item in the "rows" arrays of that file. If it
  does, set "row_ref" to that row's "ref"; if it matches none, set "row_ref" to "NONE".
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

// Return results aligned to the authoritative list. Every input document appears exactly once.
return {
  results: documents.map(d =>
    byPath.get(d.path) ?? { doc_path: d.path, row_ref: 'NONE', category: 'NONE', is_new_category: false, unprocessed: true }
  ),
  unprocessed: missing.map(d => d.path),
}
```

## 4.3 — After the workflow

- The workflow returns exactly one result per input document, in the same order as
  `DOCUMENT_FILES.json`. Confirm the count equals the input count before continuing.
- If `unprocessed` is non-empty, tell the user which documents could not be matched after retries.
  These are carried into the output (Step 5), never silently dropped.

# Step 5

Generate an excel file where each row is one of the documents, iterating the **authoritative**
`DOCUMENT_FILES.json` list joined to the workflow results by `doc_path` (never iterate only what
the agents returned). For a matched `row_ref`, look up the row in `EXCEL_FILES_DATA.json` to fill
the Excel-side columns. For `row_ref === "NONE"` (including any `unprocessed` documents), leave the
Excel-side columns blank. Columns:

- "Document File" -> file name of the document (from `doc_path`)
- "Category Name" -> `category` of the document
- "Is New Category" -> "YES" if `is_new_category` is true, otherwise "NO"
- "Matched Item" -> primary column value of the matched item (prefer the item's name if available); blank when `row_ref` is "NONE"
- "Matched Excel File" -> file name of the excel file the matched row belongs to; blank when "NONE"
- "excel_row_ref" -> `row_ref` value of the row item ("NONE" when unmatched)
- "excel_path" -> file path of the row item's excel file; blank when "NONE"
- "excel_sha" -> SHA value of the excel file; blank when "NONE"
- "doc_path" -> file path of the document file
- "doc_sha" -> SHA value of the document file (from `DOCUMENT_FILES.json`)

For any document flagged `unprocessed`, write its row with the document columns populated and the
category/Excel columns blank, so the count of rows always equals the count in `DOCUMENT_FILES.json`.

Place the file on ".workflow/active/${sessionId}/ASSIGNED_DOCUMENTS.xlsx"
