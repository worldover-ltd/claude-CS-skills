# Fanning the reading out with a workflow

The script below reads the documents in batches, forces structured output with a schema, and runs the
roll call in code. Two things about it are load-bearing, and both are mistakes that were paid for once
already:

- **The batches are partitioned in code, and each sub agent is handed its own literal list of paths.**
  A shared file plus "handle documents 40 to 50" produces overlapping and dropped batches, because
  counting is exactly what models get wrong. The batch a sub agent works on is the data it was given.
- **Runtime values are substituted into the script text as literals, not passed through `args`.**
  Passing `args` alongside `scriptPath` has silently delivered `undefined`, which corrupts every path
  into `.workflow/active/undefined/…` and returns an empty run that looks like a clean one. The guards
  at the top of the script turn a missed substitution into a loud failure instead.

## Running it

1. Read `TO_CATEGORISE.json` and record its document count as `N` — this is the roll call's authority.
2. Take the template below and replace each placeholder with a literal value:
   - `__DOCUMENTS_JSON__` → the documents array, as a JSON literal
   - `__VOCABULARY_JSON__` → the vocabulary array, as a JSON literal (`[]` when falling back to the
     taxonomy)
   - `__TAXONOMY_PATH__` → the absolute path to `lib/document_categories.txt`
3. Write the substituted script into the session directory and launch it with `Workflow({ scriptPath })`,
   with no `args`.
4. Assert `results.length === N` before using anything it returned. A mismatch means the run did not do
   its job — report it rather than writing a `CATEGORIES.json` that quietly covers fewer documents than
   it was asked about.

## The script

```javascript
export const meta = {
  name: 'categorise-documents',
  description: 'Read each document and give it a type from the vocabulary',
  phases: [{ title: 'Read' }, { title: 'Roll call' }],
}

const BATCH_SIZE = 10
const MAX_ROUNDS = 2
// Picking a document's type is high-volume and mechanical, so it runs on a cheap model.
// Raise this if the categories come back poor on your documents.
const MODEL = 'haiku'

// One result per input document, including the ones that could not be placed — returning every
// document is what makes the roll call meaningful.
const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['results'],
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['path', 'category', 'source'],
        properties: {
          path: { type: 'string' },                                  // verbatim, as listed in the prompt
          category: { type: 'string' },
          source: { type: 'string', enum: ['vocabulary', 'invented', 'unknown'] },
        },
      },
    },
  },
}

const documents = __DOCUMENTS_JSON__
const vocabulary = __VOCABULARY_JSON__
const taxonomyPath = '__TAXONOMY_PATH__'

if (!Array.isArray(documents) || documents.length === 0) {
  throw new Error('documents were not substituted into the script — aborting')
}
if (!Array.isArray(vocabulary) || taxonomyPath.includes('__')) {
  throw new Error('vocabulary or taxonomy path were not substituted — aborting')
}

const chunk = (arr, n) =>
  Array.from({ length: Math.ceil(arr.length / n) }, (_, i) => arr.slice(i * n, i * n + n))

const vocabularySection = vocabulary.length
  ? `Pick from this list, writing the name exactly as it appears:\n${vocabulary.map(v => `- ${v}`).join('\n')}`
  : `Pick from the list at "${taxonomyPath}". Each line is "<n>: <canonical name> | <alias> | <alias>" — write the canonical name, the part before the first "|".`

const promptFor = (batch) => `
### DOCUMENTS

Read exactly these ${batch.length} files and no others. Use each path verbatim as "path" in your output:

${batch.map((d, i) => `${i + 1}. ${d.path}`).join('\n')}

### VOCABULARY

${vocabularySection}

### WHAT TO RETURN

For each file above, open it, work out what kind of document it is, and return one result:
- "category" — the name you picked, and "source": "vocabulary".
- Nothing in the list fits — invent a name of at most 40 characters and set "source": "invented".
- The file cannot be read, or its contents place it nowhere — set "category" to "unknown" and
  "source": "unknown".

Return one result for EVERY file listed above. "path" MUST equal the listed path exactly.
`

async function readRound(batch_documents, phase) {
  const batches = chunk(batch_documents, BATCH_SIZE)
  const perBatch = await parallel(
    batches.map((batch, i) => () =>
      agent(promptFor(batch), { label: `read:batch-${i}`, phase, model: MODEL, schema: SCHEMA })
        .then(r => (r?.results ?? []).filter(x => batch.some(d => d.path === x.path)))
    )
  )
  return perBatch.filter(Boolean).flat()
}

phase('Read')
const byPath = new Map()
for (const r of await readRound(documents, 'Read')) {
  if (!byPath.has(r.path)) byPath.set(r.path, r)
}

phase('Roll call')
let round = 0
let silent = documents.filter(d => !byPath.has(d.path))
while (silent.length && round < MAX_ROUNDS) {
  round++
  log(`Roll call ${round}: ${silent.length} document(s) did not answer — sending them out again.`)
  for (const r of await readRound(silent, 'Roll call')) {
    if (!byPath.has(r.path)) byPath.set(r.path, r)
  }
  silent = documents.filter(d => !byPath.has(d.path))
}

if (silent.length) {
  log(`${silent.length} document(s) still silent after ${MAX_ROUNDS} rounds — returned as unread.`)
}

// Aligned to the authoritative list: every input document appears exactly once.
return {
  results: documents.map(d =>
    byPath.get(d.path) ?? { path: d.path, category: 'unknown', source: 'unknown' }
  ),
  unread: silent.map(d => d.path),
}
```
