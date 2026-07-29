# Reading the source files

What to do per file type in Step 2, and what to record. The aim is a written note per file, not a
full transcription: enough to bring recommended answers into the grilling.

Keep the notes at `.workflow/active/${sessionId}/SOURCE_NOTES.md`, one section per source file, each
with the file path so a field can be traced back to it later.

## Archives

`.zip`, `.7z`, `.rar`: expand into `.workflow/active/${sessionId}/extracted/<archive_name>/` and treat
each file inside as its own source. Archives nest — expand what you find inside too. Note the folder
structure itself: customers often encode the item a document belongs to in its folder name.

## Spreadsheets

`.xlsx`, `.xls`, `.csv`, `.tsv`: read **every** tab, not the first one. Per tab record the tab name,
the header row, the row count, and for each column its distinct-value count against the row count —
a column whose distinct count equals the row count is a candidate identifier, which is the evidence
Step 3 needs.

Watch for headers that do not start at row 1, merged header cells spanning two rows, and repeated
blocks of the same table stacked down one sheet.

## Documents

`.docx`, `.doc`, `.rtf`, `.txt`, `.md`: read the text and note which items it names and any tables it
holds. Specification and safety-data documents usually describe a single item, and the file name is
often the identifier.

## PDFs and scans

`.pdf`: read with the Read tool's `pages` parameter, 20 pages per request at most. `.png`, `.jpg`,
`.tiff`: read with the Read tool, which renders them visually.

For a scan, record what you could read and what you could not, and bring the unreadable parts to the
user in Step 3 rather than inferring the values.

## Anything else

Report the file to the user with its extension and ask what it is. A customer export in an unfamiliar
format is usually text underneath — check that before writing it off.
