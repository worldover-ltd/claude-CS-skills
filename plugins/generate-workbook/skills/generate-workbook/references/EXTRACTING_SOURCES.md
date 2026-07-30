# Reading the source files

What to do per file type in Step 2, and what to record. The aim is a written note per file, not a
full transcription: enough to bring recommended answers into the grilling.

Keep the notes at `.workflow/active/${sessionId}/SOURCE_NOTES.md`, one section per source file, each
with the file path so a field can be traced back to it later.

## Archives

`.zip`, `.7z`, `.rar`: expand into `.workflow/active/${sessionId}/extracted/<archive_name>/` and treat
each file inside as its own source. Archives nest — expand what you find inside too. Note the folder
structure itself: customers often encode the item a document belongs to in its folder name.

For `.zip`, the Python resolved in the preflight step handles it on every platform, where `unzip` and
`tar` are not always present:

```sh
<interpreter> -m zipfile -e "<archive.zip>" ".workflow/active/${sessionId}/extracted/<name>"
```

Other archive formats need a tool that may not be installed. Check before relying on one, and if none
is available, ask the user to expand it themselves and point you at the folder.

## Spreadsheets

`.xlsx`, `.xls`, `.csv`, `.tsv`: use the `xlsx` skill, whose own remit covers messy customer data —
malformed rows, misplaced headers, junk columns.

Read **every** tab, not the first one. Per tab record the tab name, the header row, the row count, and
for each column its distinct-value count against the row count — a column whose distinct count equals
the row count is a candidate identifier, which is the evidence Step 6 needs.

Watch for headers that do not start at row 1, merged header cells spanning two rows, and repeated
blocks of the same table stacked down one sheet.

## Documents

`.docx`, `.dotx`: use the `docx` skill. `.doc`, `.rtf`, `.txt`, `.md`: read directly.

Note which items the document names and any tables it holds. Specification and safety-data documents
usually describe a single item, and the file name is often the identifier.

## PDFs and scans

`.pdf` with a text layer: use the `pdf` skill for text and tables. `.png`, `.jpg`, `.tiff`: read with
the Read tool, which renders them visually.

A **scan** has no text layer — a photographed or faxed page wrapped in a PDF — so text extraction
returns nothing and the values have to be read off the image. The `pdf` skill prescribes OCR through
`pytesseract` and `pdf2image`, and both are wrappers around system binaries (`tesseract`, Poppler's
`pdftoppm`) that need administrator rights. Where those are absent, render the page and read it
yourself:

```sh
<interpreter> -c "import pypdfium2 as p; d=p.PdfDocument('<file.pdf>'); [d[i].render(scale=2).to_pil().save(f'<out>/page_{i+1}.png') for i in range(len(d))]"
```

`pypdfium2` needs no system binary and renders a page whatever its internal compression, so this route
survives scans that OCR cannot reach at all. Read the resulting images with the Read tool. Confirm
`pypdfium2` and `Pillow` import before relying on it — the preflight step covers the document skills'
own requirements, not this fallback.

Either way, record for each scan what you could read and what you could not, and bring the unreadable
parts to the user in Step 6 rather than inferring the values.

## When a file type is not covered

The preflight step records which document skills passed their probes. For a file type whose skill is
unavailable, say so as you reach the file and ask the user to tell you what it contains, rather than
guessing from the file name. Record it in the mapping as user-supplied.

## Anything else

Report the file to the user with its extension and ask what it is. A customer export in an unfamiliar
format is usually text underneath — check that before writing it off.
