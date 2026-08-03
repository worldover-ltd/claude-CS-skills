# Categorising the documents

Every row of the workbook names a document type, and there are two ways to get one. The tree usually
holds it; where it does not, `assign-documents` reads the documents that are left.

## From the tree

For a branch whose **category level** was confirmed in Step 5, the category is that folder's name — no
document opened. Land each name in the app's own document type list from `APP_SCHEMA.md`:

- **Exact or obvious match** — `SDS` against "Safety Data Sheet", `CoA` against "Certificate of Analysis".
  Record the app's name, not the folder's.
- **No match** — the app has no such type yet. Keep the folder's name, and record it in the mapping as a
  document type the app will need. Say so in the workbook's `README` sheet too, since somebody has to
  create it before the migration runs.

A folder name that names several types at once ("SDS + TDS") is one folder holding two kinds of document.
Put it to the user rather than picking one.

## From the documents, for the branches the tree leaves silent

Documents in a branch with no category level are the only ones that get opened, and `assign-documents`
owns that work — it holds the taxonomy, the fan-out and the reconciliation. Hand it a spreadsheet of the
items, since that is the shape it reads:

1. **Check it is there.** Look for the `assign-documents` skill. Absent, tell the user it is a separate
   plugin (`/plugin install assign-documents`) and offer the alternative: they name the document type per
   folder themselves, recorded as user-supplied.
2. **Build the items sheet.** Write `.workflow/active/${sessionId}/ITEMS.xlsx` with one tab per target
   entity, named for the app table, holding one row per item that has silent-branch documents: the
   identifier column as the anchor values give it, plus any human-readable name the folders carry.
3. **Prepare its inputs in this same session directory**, so it has nothing to re-derive:
   `DOCUMENT_FILES.json` (written by `join_manifest.py`) cut down to the silent-branch documents only, and
   `UPLOAD_MANIFEST.json`, which is already there from Step 6.
4. **Invoke the skill**, giving it `ITEMS.xlsx` as the customer's data sheet and the prepared document list
   when it asks for them.
5. **Read the categories back** out of the `ITEMS_with_documents.xlsx` it writes: its `Document Templates`
   tab maps each type name to its id, and each annotated row's
   `alreadyUploadedToSupabaseMatchedDocuments` column holds a JSON string naming the documents matched to
   that item and the `documentTemplateId` each was given. Invert that to one category per document.

**Take the category and nothing else.** `assign-documents` matches documents to items as well, and here the
tree has already decided that — under a rule the user confirmed and against items that already exist. Where
its match disagrees with the tree, the tree stands; the disagreement is worth one line to the user, since a
run of them means Step 5 read the tree wrong.

Documents it returns as `NONE`, as a new category it invented, or as unprocessed all go to the user in Step
6's exception pile — with the file name and its folder, which is usually enough for them to say what it is.
