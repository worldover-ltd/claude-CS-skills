---
name: extract-document-text
description: "Convert document files to Markdown with MarkItDown, and render the pages of scanned PDFs that hold no text to PNGs. Triggers on \"extract-document-text\" or \"MarkItDown\", when the text or tables inside spreadsheets, Word documents, PDFs, presentations or archives are wanted, or when a PDF turns out to be a scan."
allowed-tools: Read, Write, Bash, Glob, Grep
---

### What it does

One script, `lib/extract_documents.py`, over a list of files. Per file it writes a Markdown conversion, and
where a PDF holds no text layer — a **scan**, a photographed or faxed page wrapped in a PDF — it renders the
pages to PNGs instead. Every file it touched lands in one JSON manifest.

The engine is [MarkItDown](https://github.com/microsoft/markitdown), and rendering is `pypdfium2`. Both run
locally, and the script declares them inline for `uv` to fetch, so it installs nothing into any Python on
the machine.

### Setup

`uv` is the only requirement. `uv --version` answers whether it is there; where it is missing, it installs
into the user's own home directory and needs no administrator rights:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS and Linux take the first, Windows the second. Both put `uv` in `~/.local/bin`, which a shell opened
before the install will not have on `PATH` yet — call it by full path in that case (`~/.local/bin/uv`, or
`$HOME\.local\bin\uv.exe`).

`uv run` then fetches the script's libraries into a cache on first use, and a Python 3.10 or newer if the
machine has none. That first run takes a minute or two; every run after it is immediate.

### Running it

```sh
uv run "${CLAUDE_PLUGIN_ROOT}/skills/extract-document-text/lib/extract_documents.py" "<folder-or-json>" "<out_dir>" --scans first
```

`${CLAUDE_PLUGIN_ROOT}` is set by Claude Code; from a raw checkout, use the folder containing this
`skills/` directory. Write paths with forward slashes, quote any that could contain a space, and keep the
command on one line — a trailing backslash continues a line in `sh` and breaks it in PowerShell.

It prints a progress line every 25 files, then a summary: the count per `kind`, and the file names under
each heading that converted to something other than text. On a folder of thousands, the summary is the
short read and the manifest holds the rest.

Re-running reuses whatever is already in `<out_dir>/extracted/` — both the Markdown and any page already
rendered — so a second pass at other flags only costs what it actually changes. `--force` redoes everything.

Thousands of files are a normal input, and they take a while. Measured on 3529 mixed files, 1.46 GB, mostly
PDFs: **29 minutes cold, 8 seconds re-run**. Conversion dominates that at roughly half a second a file —
rendering was 436 pages of it, a few minutes. So budget **half a second per file** and start the run before
you need the answer. `--scans none` skips rendering, which trims the tail rather than the bulk.

Rendering is **serialised**, because pdfium forbids concurrent calls from different threads even on different
documents, so `--jobs` raises conversion throughput only.

### Input

`<folder-or-json>` takes either shape:

- **A folder** — walked recursively, every file in it treated as an input.
- **A `.json` file** — a bare array of paths, or `{"documents": [{"path": …}]}`. A listed path that is not on
  disk still gets a record, under `kind: "missing"`, so the manifest answers for every input.

`<out_dir>` is any directory; it is created if absent, and everything the run produces goes inside it.

### Output

```
<out_dir>/EXTRACTED.json                       the manifest
<out_dir>/extracted/<slug>.md                  one Markdown file per converted document
<out_dir>/extracted/<slug>.capped.md           the head and tail of it, under --max-chars
<out_dir>/extracted/<slug>/page_001.png        rendered pages, for scans
<out_dir>/converted/<slug>.pdf                 legacy Office files LibreOffice turned into PDFs
```

`<slug>` is 8 hex characters of the SHA-256 of the file's path, then its stem — so two documents with the
same name in different folders stay separate.

```json
{
  "root": "C:/…/docs",
  "extractedDir": "C:/…/out/extracted",
  "scans": "first",
  "maxChars": 0,
  "libreOffice": "C:/Program Files/LibreOffice/program/soffice.exe",
  "counts": { "text": 104, "image-only": 12, "unsupported": 2 },
  "documents": [
    {
      "path": "C:/…/RM-0142/SDS_2026.pdf",
      "relativePath": "Raw Materials/RM-0142/SDS_2026.pdf",
      "kind": "text",
      "textFile": "C:/…/out/extracted/a1b2c3d4_SDS_2026.md",
      "images": [],
      "chars": 8421,
      "letters": 6180,
      "pages": 4,
      "pagesRendered": 0,
      "note": null
    }
  ]
}
```

`documents` holds one record per input file, sorted by `relativePath`, with `path` verbatim as it was given
so a caller can join on it. `textFile` and `images` are absolute, which is what the Read tool takes.
`relativePath` is relative to the input folder, or the bare file name when the input was a JSON list.
`chars` counts the stripped Markdown and `letters` counts only its letters, which is what decides whether a
PDF is really text — a scan often leaks a handful of bullet glyphs, enough to pass a character count while
holding no words. Both are counted on the **whole** conversion even under `--max-chars`, so a cap never
changes what a file is judged to be; `charsRead` is what a reader is actually given, and `fullTextFile`
points at the uncapped text where the two differ. `pages` is filled for PDFs only; `note` carries anything
that qualifies the record, such as a page cap that was hit, a file whose bytes contradicted its name, a
conversion LibreOffice made possible, or one that only the renderer rescued.

`kind` is the per-file outcome:

| `kind` | what happened | where the content is |
| --- | --- | --- |
| `text` | converted, and holds text | `textFile` |
| `image-only` | a PDF with no text layer at all, or one no converter would read | `images` |
| `sparse-text` | a PDF averaging under 40 letters a page — part text, part picture | both `textFile` and `images` |
| `image` | the input was already an image file | `path` itself |
| `empty` | converted, and held no text | — |
| `unsupported` | MarkItDown has no converter for the extension | — |
| `failed` | conversion raised and the pages would not render either; `note` holds what it said | — |
| `missing` | the input listed the path and it is not on disk | — |

### Flags

| flag | default | effect |
| --- | --- | --- |
| `--scans first\|all\|none\|N` | `first` | pages rendered for a PDF with no text layer: its first page, every page, none, or the first N. Page one of a scanned dossier is often its cover sheet, so `--scans 3` costs little and reaches the first real content |
| `--max-chars N` | `0` (no cap) | cap what `textFile` points at, keeping the head and the last quarter with a marker between them — a document names itself at the top and carries its form number at the bottom. The whole conversion stays at `fullTextFile`, and `chars`, `letters` and `kind` are all counted on it, so capping never changes what a file is judged to be |
| `--max-pages N` | `40` | page cap under `--scans all`; the cap it hit is recorded in `note` |
| `--no-libreoffice` | off | leave `.doc`, `.rtf` and OpenDocument files unconverted even where LibreOffice is installed |
| `--scale F` | `2.0` | render scale, where 1.0 is 72 dpi. 2.5 sharpens a small or dense page. `--max-px` caps it, and the render goes straight to the capped size rather than shrinking afterwards |
| `--max-px N` | `2000` | longest side of a rendered page. A PDF's page can be any size, and past this a render gains detail an agent's vision downsamples away. Lowering it makes a long `--scans all` run cheaper |
| `--enhance` | off | grayscale, raise contrast, denoise and sharpen each render — legible on a faxed or photocopied page, and it discards colour, so a stamp or a highlighted row goes with it |
| `--jobs N` | `4` | files **converted** at once. Rendering ignores it, being serialised by pdfium's own rule |
| `--force` | off | redo files already converted or rendered |

### What it converts

PDF, Word (`.docx`), Excel (`.xlsx`, `.xls`, `.csv`, `.tsv`), PowerPoint (`.pptx`), Outlook (`.msg`), HTML,
plain text, Markdown, JSON, XML, EPub and ZIP, which is converted by expanding it and converting what is
inside. A spreadsheet comes out as one Markdown table per sheet under a `##` heading of the sheet's name.

`.doc`, `.rtf` and OpenDocument files (`.odt`, `.ods`, `.odp`) are converted to PDF by **LibreOffice, where
it is installed**, and read as that PDF — the record still answers for the file the customer has, and says
so in `note`. LibreOffice is probed once at the start of a run, not per file, and where it is absent these
come back `unsupported` with a note naming it, so the difference between "install this" and "the user has
to re-save this" is visible rather than guessed at. On the first customer folder this ran against that was
333 files. `.pages`, `.numbers`, `.key`, `.7z` and `.rar` stay `unsupported` either way. Image files come
back `image` for reading directly.

**A file's first bytes outrank its name.** Customer folders are full of files saved under the wrong
extension, and MarkItDown picks its converter off the extension alone, so the name being wrong is the whole
failure. A JPEG called `.pdf` comes back `image`; an `.xls` called `.xlsx` is converted as the `.xls` it is;
a PDF whose bytes pdfminer refuses is rendered instead. Each of those says so in `note`. What survives as
`unsupported` or `failed` is a file the user genuinely has to re-save.

### One file, without the script

```sh
uvx --from "markitdown[pdf,docx,pptx,xlsx,xls,outlook]" markitdown "<file>" -o "<out>.md"
```

`uvx` runs MarkItDown and installs nothing permanently;
`uv tool install "markitdown[pdf,docx,pptx,xlsx,xls,outlook]"` puts a `markitdown` command on the PATH for
good. Neither renders a scan — that is the script's `--scans` work.
