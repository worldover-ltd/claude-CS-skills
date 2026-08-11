# Reading the source files

What to do per file type in Step 5, and what to record. The aim is a written note per file, not a full
transcription: enough to bring recommended answers into the grilling.

Keep the notes at `.workflow/active/${sessionId}/SOURCE_NOTES.md`, one section per source file, each with
the file path so a field can be traced back to it later.

## Extract everything first

One pass converts the whole pile before any of it is read. Invoke the `extract-document-text` skill, giving
it the folder or file list the user confirmed as its input and `.workflow/active/${sessionId}` as its output
directory. It writes each file's Markdown into `extracted/` there and records every file in
`EXTRACTED.json`, whose `kind` per file is what the rest of this page turns on.

Read that summary before opening anything. It tells you which files converted, which are pictures of
pages, and which could not be read at all — which is the difference between reading a file and asking
the user about it.

## Archives

`.zip`, `.7z`, `.rar`: expand into `.workflow/active/${sessionId}/expanded/<archive_name>/` and treat each
file inside as its own source, extracted along with the rest. Archives nest — expand what you find inside
too. Note the folder structure itself: customers often encode the item a document belongs to in its folder
name, and that structure is lost if you only read the files.

For `.zip`, the Python resolved in the preflight step handles it on every platform, where `unzip` and
`tar` are not always present:

```sh
<interpreter> -m zipfile -e "<archive.zip>" ".workflow/active/${sessionId}/expanded/<name>"
```

Other archive formats need a tool that may not be installed. Check before relying on one, and if none is
available, ask the user to expand it themselves and point you at the folder.

## Spreadsheets

`.xlsx`, `.xls`, `.csv`, `.tsv`: the extraction gives you every sheet as a Markdown table, one `##` heading
per sheet — so read **every** tab rather than the first one, and watch for what a table flattens: headers
that do not start at row 1, merged header cells spanning two rows, and repeated blocks of the same table
stacked down one sheet.

A header that is not on row 1 is visible in the Markdown rather than silent: the columns come out named
`Unnamed: 1`, `Unnamed: 2`, empty cells read `NaN`, and the real header sits in the body as a data row. Take
that as the signal to find the true header row before reading any values off the table.

What a Markdown table cannot tell you is which column identifies an item, and on a sheet of any size that
is not countable by eye. Profile the file instead:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/lib/profile_spreadsheet.py" "<file.xlsx>"
```

Per sheet it prints the row count, the header row it found, and per column the filled count against the
distinct count. A column whose distinct count equals the row count is a candidate identifier, which is
exactly the evidence Step 6 needs — and it comes as a number you can put to the user rather than an
impression.

## Documents

`.docx`, `.dotx`, `.pptx`, `.msg`, `.html`, `.txt`, `.md`, `.json`, `.xml`: the extraction covers them, and
the Markdown is what you read.

`.doc`, `.rtf` and OpenDocument files (`.odt`, `.ods`) come back `unsupported` — MarkItDown has no converter
for them. Ask the user to re-save each one as `.docx`, `.xlsx` or PDF and re-run the extraction, which is a
smaller ask than describing the contents.

Note which items each document names and any tables it holds. Specification and safety-data documents
usually describe a single item, and the file name is often the identifier.

## PDFs and scans

A `.pdf` with a text layer comes back `text`, and the Markdown holds its text and tables. A **scan** comes
back `image-only` or `sparse-text`, with its first page already rendered to a PNG — read what its `kind`
points at, as the extraction's contract defines it.

What this run wants from a scan is its **values**, which one cover page rarely carries, so re-run the
extraction for those files with `--scans all`; `extract-document-text`'s flag table holds what else to
reach for when a rendered page still will not read. Send batches of pages to sub agents with the question
you need answered, rather than pulling every rendered page into this run's context.

`.png`, `.jpg`, `.tiff`: read with the Read tool, which renders them visually.

Record for each scan which values you read and which you could not, and bring the gaps to the user in
Step 6, so a value nobody read stays distinguishable from one that was.

## When a file could not be read

`unsupported`, `failed` and `empty` are the three that need the user. Say so as you reach the file — with
what it costs, since a file nothing could open is a file whose data will not be in the workbook — and ask
them to describe what it holds or to re-save it. Record whatever they tell you in the mapping as
user-supplied, so a value nobody read is never mistaken for one that was.

## Anything else

Report the file to the user with its extension and ask what it is. A customer export in an unfamiliar
format is usually text underneath — check that before writing it off.
