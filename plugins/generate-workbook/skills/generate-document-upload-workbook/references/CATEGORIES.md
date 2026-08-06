# Categorising the documents

Every row of the workbook names a document type, and there are two ways to get one. The tree usually
holds it; only the documents it leaves silent are opened.

## The vocabulary

Categories come from the app's own document type list in `APP_SCHEMA.md` — those are the names the
migration can land on. Where the app has no such list yet, the `categorise-documents` skill falls back to
its own taxonomy of cosmetics, chemical and compliance document types, which is why an empty vocabulary is
passed rather than an invented one.

## From the tree

For a branch whose **category level** was confirmed in Step 5, the category is that folder's name — no
document opened. Land each name in the app's list:

- **Exact or obvious match** — `SDS` against "Safety Data Sheet (SDS)", `CoA` against "Certificate of
  Analysis (CoA)". Record the app's name, not the folder's.
- **No match** — keep the folder's name and record it in the mapping as a document type the app will need.
  Say so in the workbook's `README` sheet too, since somebody has to create it before the migration runs.

A folder name that names several types at once ("SDS + TDS") is one folder holding two kinds of document.
Put it to the user rather than picking one.

## From the documents, for the branches the tree leaves silent

Documents in a branch with no category level are the only ones opened, and the `categorise-documents`
skill does that reading:

1. **Check it is there.** Absent, tell the user it is a separate plugin
   (`/plugin install categorise-documents`) and offer the alternative: they name the document type per
   folder themselves, recorded as user-supplied.
2. **Write its input** to `.workflow/active/${sessionId}/TO_CATEGORISE.json` — the silent-branch documents
   from `DOCUMENTS.json` and nothing else, plus the app's document type list as the `vocabulary`, or `[]`
   when the app has none.
3. **Invoke it**, passing this run's `${sessionId}` so it writes back into the same session directory, and
   the document tooling verdict from Step 1 so it does not probe again.
4. **Read `CATEGORIES.json` back** and join to the tree on `path`.

What comes back marked `invented`, `unknown` or `unread` goes to the user in Step 6's exception pile —
with the file name and its folder, which is usually enough for them to say what it is. A category marked
`invented` is also a document type the app will need, so it belongs in the workbook's `README` sheet
alongside the unmatched folder names.
