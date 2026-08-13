# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "markitdown[pdf,docx,pptx,xlsx,xls,outlook]",
#     "pypdfium2",
#     "pillow",
# ]
# ///
"""Turn document files into Markdown, and render the ones with no text layer to page images.

Usage:
    uv run extract_documents.py <folder-or-json> <out_dir> [--scans first|all|none|<pages>]
        [--max-chars 0] [--scale 2.0] [--max-pages 40] [--enhance] [--jobs 4] [--force]

<folder-or-json> is a folder to walk, or a JSON file holding either a list of paths or
{"documents": [{"path": ...}]}.

Writes text to <out_dir>/extracted/<slug>.md, page images to <out_dir>/extracted/<slug>/page_NNN.png,
and one record per input file to <out_dir>/EXTRACTED.json.

`--max-chars` caps what a reader is pointed at, keeping the head and the tail of the text: a document
names itself at the top, and carries its form number and revision block at the bottom. The full
conversion is always kept on disk; the cap only decides what `textFile` points at.

Nothing here interprets a document. A file becomes Markdown or PNGs; reading it is the caller's job.
"""

import argparse
import concurrent.futures
import hashlib
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import warnings
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
UNSUPPORTED_SUFFIXES = {".doc", ".rtf", ".odt", ".ods", ".odp", ".pages", ".numbers", ".key", ".7z", ".rar"}

# The ones LibreOffice converts, where it is installed. Everything else in UNSUPPORTED_SUFFIXES stays
# the user's to re-save.
LIBREOFFICE_SUFFIXES = {".doc", ".rtf", ".odt", ".ods", ".odp"}
LIBREOFFICE_NAMES = ("soffice", "libreoffice")
LIBREOFFICE_PLACES = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)
# One invocation converts a group rather than a file: LibreOffice's startup dominates its runtime, and a
# group large enough to amortise it is still small enough that one bad file loses only its neighbours.
LIBREOFFICE_GROUP = 12
LIBREOFFICE_TIMEOUT = 300

# Where the cap falls when --max-chars is set. Three parts head to one part tail: the title, the header
# block and the opening section are what name a document, and the tail is there for a form number.
TAIL_SHARE = 0.25

# A page carrying fewer letters than this is a picture of a page rather than a page. Letters rather than
# characters, because a scan often leaks a handful of bullet glyphs — enough to pass a character count
# while holding no words at all.
LETTERS_PER_PAGE_FLOOR = 40
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
SAMPLE = 15

# Leading bytes worth trusting over the file's name. Two-byte signatures are left out: they match too
# much ordinary text to be evidence of anything.
SIGNATURES = (
    (b"%PDF", ".pdf"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF8", ".gif"),
    (b"II*\x00", ".tif"),
    (b"MM\x00*", ".tif"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", ".ole2"),
    (b"PK\x03\x04", ".zip"),
)
LEGACY_FOR = {".xlsx": ".xls", ".docx": ".doc", ".pptx": ".ppt"}
MODERN_FOR = {".xls": ".xlsx", ".doc": ".docx", ".ppt": ".pptx"}

# pdfium is not thread-safe, so every call into it goes through one lock.
PDFIUM_LOCK = threading.Lock()
LOCAL = threading.local()


def converter():
    if not hasattr(LOCAL, "markitdown"):
        from markitdown import MarkItDown

        LOCAL.markitdown = MarkItDown(enable_plugins=False)
    return LOCAL.markitdown


def quieten_libraries():
    """pdfminer and openpyxl narrate once per file, which buries this script's own output.

    pdfminer logs a three-line notice for every PDF whose metadata asks not to be extracted, and
    openpyxl warns on every header it cannot parse. On a folder of thousands, that is the whole log.
    """
    warnings.filterwarnings("ignore", module="openpyxl")
    warnings.filterwarnings("ignore", message="Cannot parse header or footer")
    for name in ("pdfminer", "pdfplumber", "pypdf", "markitdown", "magika"):
        logging.getLogger(name).setLevel(logging.ERROR)


def sniff(path):
    """The extension the first bytes claim, or None. A customer's file often lies about its type."""
    try:
        with path.open("rb") as handle:
            head = handle.read(8)
    except OSError:
        return None
    return next((suffix for magic, suffix in SIGNATURES if head.startswith(magic)), None)


def mislabelled_as(suffix, signature):
    """The extension the bytes call for, when the name's own extension picks the wrong converter."""
    if signature == ".ole2" and suffix in LEGACY_FOR:
        return LEGACY_FOR[suffix]
    if signature == ".zip" and suffix in MODERN_FOR:
        return MODERN_FOR[suffix]
    if signature == ".pdf" and suffix != ".pdf":
        return ".pdf"
    return None


def note_that(record, text):
    """Notes accumulate: a file can be both mislabelled and short of a text layer."""
    record["note"] = f"{record['note']}; {text}" if record["note"] else text


def slug_for(path):
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:8]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("_")[:60] or "document"
    return f"{digest}_{stem}"


def scan_pages_from(value):
    """0 for none, None for every page, or how many pages from the front.

    `first` stays what it always meant. A number is there because page one of a scanned dossier is often
    its cover sheet, which is the least distinguishing page in the whole document.
    """
    if value == "none":
        return 0
    if value == "all":
        return None
    if value == "first":
        return 1
    try:
        pages = int(value)
    except ValueError:
        raise SystemExit(f"--scans takes first, all, none or a page count, not {value!r}")
    if pages < 1:
        raise SystemExit("--scans takes a page count of 1 or more, or the word none")
    return pages


def pages_wanted(pages, options):
    """The page numbers to render for a document of this length, under this run's --scans."""
    reach = options.max_pages if options.scan_pages is None else options.scan_pages
    return list(range(1, min(pages, reach) + 1))


def rendering_note(pages, rendered, options):
    """What was left unrendered, in the words of the flag that would fetch it."""
    if rendered >= pages:
        return None
    if options.scan_pages is None:
        return f"rendered {rendered} of {pages} pages — raise --max-pages for the rest"
    return f"rendered {rendered} of {pages} pages — raise --scans for the rest"


def elision(dropped):
    """The marker standing in for the cut middle, so a reader knows text is missing rather than absent."""
    return f"\n\n[... {dropped} characters omitted ...]\n\n"


def cap_text(text, max_chars):
    """(what a reader is pointed at, characters dropped) — the head and the tail, or the text unchanged.

    Cutting the middle rather than the tail keeps the two places a document says what it is: its title
    block, and the form number and revision table that so often sit at the very end.
    """
    if not max_chars or len(text) <= max_chars:
        return text, 0
    # Room for the marker comes out of the budget, costed at the longest it could ever print, so the
    # result honours --max-chars rather than exceeding it by the width of its own explanation.
    budget = max_chars - len(elision(len(text)))
    tail = int(budget * TAIL_SHARE)
    head = budget - tail
    dropped = len(text) - head - tail
    return text[:head] + elision(dropped) + (text[-tail:] if tail else ""), dropped


def page_count(path):
    import pypdfium2 as pdfium

    with PDFIUM_LOCK:
        document = pdfium.PdfDocument(str(path))
        try:
            return len(document)
        finally:
            document.close()


def render_pages(path, dest, scale, page_numbers, enhance, max_px, force):
    import pypdfium2 as pdfium
    from PIL import Image, ImageEnhance, ImageFilter

    dest.mkdir(parents=True, exist_ok=True)
    wanted = [(n, dest / f"page_{n:03d}.png") for n in page_numbers]
    todo = wanted if force else [(n, out) for n, out in wanted if not out.exists()]
    if not todo:
        return [out for _, out in wanted]

    # pdfium is not thread-safe, so the lock covers the render and nothing else: the Pillow work
    # after it is what the other threads get on with while this one holds it.
    for number, out in todo:
        with PDFIUM_LOCK:
            document = pdfium.PdfDocument(str(path))
            try:
                page = document[number - 1]
                # Render straight to the target size. Rendering large and shrinking afterwards costs
                # the render, then a resample, to arrive where a smaller scale lands directly.
                fitted = min(scale, max_px / max(page.get_size()))
                bitmap = page.render(scale=fitted).to_pil()
            finally:
                document.close()
        image = bitmap
        if max(image.size) > max_px:
            image.thumbnail((max_px, max_px), Image.LANCZOS)
        if enhance:
            image = image.convert("L")
            image = ImageEnhance.Contrast(image).enhance(2.0)
            image = image.filter(ImageFilter.MedianFilter()).filter(ImageFilter.SHARPEN)
        image.save(out)
    return [out for _, out in wanted]


def why_unsupported(suffix, options):
    """Why this file was not converted, naming the thing that would have converted it.

    A file LibreOffice would have read is a different problem from one nothing reads: the first is an
    install, the second is the user re-saving a document.
    """
    if suffix not in LIBREOFFICE_SUFFIXES:
        return f"MarkItDown does not convert {suffix} — ask the user to re-save it"
    if not options.libreoffice:
        return (
            f"MarkItDown does not convert {suffix}, and LibreOffice is not installed — install it and "
            "re-run, or ask the user to re-save this as .docx, .xlsx or PDF"
        )
    return (
        f"MarkItDown does not convert {suffix}, and LibreOffice could not either — ask the user to "
        "re-save it as .docx, .xlsx or PDF"
    )


def libreoffice_at():
    """The LibreOffice binary, or None. Installers on Windows leave it off PATH, so look where it lands."""
    for name in LIBREOFFICE_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return next((p for p in LIBREOFFICE_PLACES if Path(p).is_file()), None)


def convert_group(binary, group, dest, profile):
    """Convert one group of legacy files to PDF, returning {original path: pdf path} for those that took.

    LibreOffice names its output after the input's stem, so the conversion lands in a scratch folder and
    the results are moved out under a slug — two customer files called `spec.doc` in different folders
    are otherwise one PDF.
    """
    made = {}
    with tempfile.TemporaryDirectory() as scratch:
        command = [
            binary,
            f"-env:UserInstallation=file:///{Path(profile).as_posix().lstrip('/')}",
            "--headless", "--norestore", "--convert-to", "pdf", "--outdir", scratch,
            *[str(p) for p in group],
        ]
        try:
            subprocess.run(
                command, check=False, timeout=LIBREOFFICE_TIMEOUT,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except (subprocess.TimeoutExpired, OSError):
            return made
        for path in group:
            produced = Path(scratch) / f"{path.stem}.pdf"
            if not produced.is_file():
                continue
            landed = dest / f"{slug_for(path)}.pdf"
            shutil.move(str(produced), str(landed))
            made[path] = landed
    return made


def convert_legacy(binary, paths, dest, force):
    """{original path: pdf path} for every legacy file LibreOffice could turn into a PDF."""
    dest.mkdir(parents=True, exist_ok=True)
    made, todo = {}, []
    for path in paths:
        landed = dest / f"{slug_for(path)}.pdf"
        if landed.is_file() and not force:
            made[path] = landed
        else:
            todo.append(path)

    # One profile for the whole run, in a scratch folder: a headless LibreOffice sharing the desktop
    # user's profile refuses to start while the GUI is open.
    with tempfile.TemporaryDirectory() as profile:
        for start in range(0, len(todo), LIBREOFFICE_GROUP):
            group = todo[start:start + LIBREOFFICE_GROUP]
            made.update(convert_group(binary, group, dest, profile))
            print(f"  {min(start + LIBREOFFICE_GROUP, len(todo))}/{len(todo)} legacy files attempted")
    return made


def to_markdown(path, as_suffix=None):
    """Markdown for one file, or a ('unsupported'|'failed', reason) pair.

    MarkItDown picks its converter off the extension, so `as_suffix` converts a copy under the name the
    file's bytes call for — which is how an `.xls` saved as `.xlsx` gets read at all.
    """
    try:
        if as_suffix and as_suffix != path.suffix.lower():
            with tempfile.TemporaryDirectory() as folder:
                twin = Path(folder) / f"{path.stem}{as_suffix}"
                shutil.copy2(path, twin)
                return converter().convert(str(twin)).text_content or ""
        return converter().convert(str(path)).text_content or ""
    except Exception as error:  # every converter raises its own type
        kind = "unsupported" if "Unsupported" in type(error).__name__ else "failed"
        # MarkItDown's message spans lines, and a note breaking across lines breaks the summary's shape.
        return kind, " ".join(f"{type(error).__name__}: {error}".split())


def salvage(path, record, dest, note, options):
    """A conversion that raised can still be readable as pictures of its pages.

    pdfminer refuses PDFs that pdfium renders without complaint — a malformed stream, or bytes that do
    not begin with %PDF. Rendering is the second opinion, so `failed` means nothing worked rather than
    that one library gave up.
    """
    if options.scan_pages == 0:
        record["kind"] = "failed"
        note_that(record, note)
        return record
    try:
        pages = page_count(path)
        written = render_pages(
            path, dest, options.scale, pages_wanted(pages, options),
            options.enhance, options.max_px, options.force,
        )
    except Exception:
        record["kind"] = "failed"
        note_that(record, note)
        return record

    record["kind"] = "image-only"
    record["pages"] = pages
    record["images"] = [str(p.resolve()).replace("\\", "/") for p in written]
    record["pagesRendered"] = len(written)
    note_that(record, f"text extraction failed ({note}) — the rendered page(s) are what there is to read")
    left = rendering_note(pages, len(written), options)
    if left:
        note_that(record, left)
    return record


def extract(path, root, out_dir, options, converted=None):
    record = {
        "path": str(path).replace("\\", "/"),
        "relativePath": "/".join(path.relative_to(root).parts) if root else path.name,
        "kind": None,
        "textFile": None,
        "fullTextFile": None,
        "images": [],
        "chars": 0,
        "letters": 0,
        "charsRead": 0,
        "pages": None,
        "pagesRendered": 0,
        "note": None,
    }
    slug = slug_for(path)
    suffix = path.suffix.lower()
    signature = sniff(path)

    # A legacy Office file LibreOffice turned into a PDF is read as that PDF, while the record keeps
    # answering for the file the customer actually has.
    stand_in = (converted or {}).get(path)
    if stand_in:
        record["note"] = f"converted from {suffix} by LibreOffice"
        path, suffix, signature = stand_in, ".pdf", ".pdf"

    if suffix in IMAGE_SUFFIXES or signature in IMAGE_SUFFIXES:
        record["kind"] = "image"
        record["note"] = (
            "an image already — read the file itself, there is no text to extract"
            if suffix in IMAGE_SUFFIXES
            else f"a {signature.lstrip('.')} named {suffix} — read the file itself as an image"
        )
        return record

    twin = mislabelled_as(suffix, signature)
    if suffix in UNSUPPORTED_SUFFIXES and not twin:
        record["kind"] = "unsupported"
        record["note"] = why_unsupported(suffix, options)
        return record

    text_file = out_dir / f"{slug}.md"
    if text_file.exists() and not options.force:
        text = text_file.read_text(encoding="utf-8")
    else:
        # The name is tried first even when the bytes disagree, since MarkItDown reads some files its
        # extension has no business claiming; the twin is what a refusal is retried as.
        text = to_markdown(path)
        if isinstance(text, tuple) and twin:
            retried = to_markdown(path, twin)
            if not isinstance(retried, tuple):
                text = retried
                record["note"] = f"a {twin} file named {suffix} — converted as {twin}"
        if isinstance(text, tuple):
            kind, note = text
            if signature == ".ole2":
                # Both the name's converter and the legacy one refused, so the honest reading is a
                # pre-2007 Office file wearing a modern extension. That is the user's to re-save.
                record["kind"] = "unsupported"
                record["note"] = (
                    f"MarkItDown does not convert {suffix} — ask the user to re-save it"
                    if suffix in MODERN_FOR
                    else f"a pre-2007 Office file named {suffix} — MarkItDown converts neither, so ask "
                    "the user to re-save it as .docx, .xlsx or PDF"
                )
                return record
            if kind == "failed":
                return salvage(path, record, out_dir / slug, note, options)
            record["kind"], record["note"] = kind, note
            return record
        text_file.write_text(text, encoding="utf-8")

    # Counted on the whole conversion, before any cap: what kind of document this is has to be decided
    # on what the file holds, not on how much of it a reader was given.
    record["chars"] = len(text.strip())
    record["letters"] = len(LETTER.findall(text))
    record["fullTextFile"] = str(text_file.resolve()).replace("\\", "/")

    capped, dropped = cap_text(text, options.max_chars)
    if dropped:
        capped_file = out_dir / f"{slug}.capped.md"
        capped_file.write_text(capped, encoding="utf-8")
        record["textFile"] = str(capped_file.resolve()).replace("\\", "/")
        note_that(record, f"{dropped} characters past the {options.max_chars} cap are in fullTextFile only")
    else:
        record["textFile"] = record["fullTextFile"]
    record["charsRead"] = len(capped.strip())

    if suffix != ".pdf" and signature != ".pdf":
        record["kind"] = "text" if record["chars"] else "empty"
        if not record["chars"]:
            record["note"] = "converted, but held no text"
        return record

    try:
        pages = page_count(path)
    except Exception as error:
        record["kind"] = "text" if record["chars"] else "failed"
        note_that(record, f"page count unavailable ({type(error).__name__})")
        return record

    record["pages"] = pages
    per_page = record["letters"] / pages if pages else 0
    record["kind"] = "text" if per_page >= LETTERS_PER_PAGE_FLOOR else (
        "image-only" if record["chars"] == 0 else "sparse-text"
    )
    if record["kind"] == "sparse-text" and record["letters"] == 0:
        note_that(record, f"the text layer holds {record['chars']} characters and no words — glyphs, not text")

    if record["kind"] == "text" or options.scan_pages == 0:
        if record["kind"] != "text":
            note_that(record, "no text layer — nothing rendered, --scans was none")
        return record

    try:
        written = render_pages(
            path, out_dir / slug, options.scale, pages_wanted(pages, options),
            options.enhance, options.max_px, options.force,
        )
    except Exception as error:
        note_that(record, f"could not render pages: {type(error).__name__}: {error}")
        return record

    record["images"] = [str(p.resolve()).replace("\\", "/") for p in written]
    record["pagesRendered"] = len(written)
    left = rendering_note(pages, len(written), options)
    if left:
        note_that(record, left)
    return record


def inputs_from(target):
    """(root, files, missing) — a listed path that is not on disk is returned, never dropped in silence."""
    if target.is_dir():
        return target, sorted(p for p in target.rglob("*") if p.is_file()), []
    if target.suffix.lower() == ".json":
        data = json.loads(target.read_text(encoding="utf-8"))
        entries = data.get("documents", data) if isinstance(data, dict) else data
        paths = [Path(e["path"] if isinstance(e, dict) else e) for e in entries]
        return None, [p for p in paths if p.is_file()], [p for p in paths if not p.is_file()]
    raise SystemExit(f"not a folder or a .json list: {target}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", type=Path, help="folder to walk, or a .json list of paths")
    parser.add_argument("out_dir", type=Path, help="session directory, e.g. .workflow/active/<sessionId>")
    parser.add_argument("--scans", default="first",
                        help="pages to render for a PDF with no text layer: first, all, none, or a "
                             "page count (default: first)")
    parser.add_argument("--max-chars", type=int, default=0,
                        help="cap what textFile holds, keeping the head and tail (default: 0, no cap)")
    parser.add_argument("--no-libreoffice", action="store_true",
                        help="leave .doc, .rtf and OpenDocument files unconverted even where LibreOffice is installed")
    parser.add_argument("--scale", type=float, default=2.0, help="render scale, 1.0 is 72 dpi (default: 2.0)")
    parser.add_argument("--max-pages", type=int, default=40, help="page cap for --scans all (default: 40)")
    parser.add_argument("--max-px", type=int, default=2000, help="longest side of a rendered page (default: 2000)")
    parser.add_argument("--enhance", action="store_true", help="grayscale, raise contrast and sharpen each render")
    parser.add_argument("--jobs", type=int, default=4, help="files converted at once (default: 4)")
    parser.add_argument("--force", action="store_true", help="re-convert files already extracted")
    options = parser.parse_args()
    options.scan_pages = scan_pages_from(options.scans)
    if options.max_chars and options.max_chars < 200:
        raise SystemExit("--max-chars below 200 leaves too little to identify a document by")

    # Windows consoles default to a codepage that cannot print this summary's punctuation.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    quieten_libraries()

    # A missing library must be one loud failure, not every file quietly reported as failed.
    for module, purpose in (("markitdown", "converting documents"), ("pypdfium2", "rendering scanned pages")):
        try:
            __import__(module)
        except ImportError:
            raise SystemExit(
                f"{module} is not available, so {purpose} would fail for every file. Run this script with "
                "`uv run`, which fetches what it declares, rather than with a bare python."
            )

    root, paths, missing = inputs_from(options.target)
    if not paths:
        raise SystemExit(f"no files to extract from {options.target}")

    extracted_dir = options.out_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    # Probed once for the whole run rather than discovered per file, so a missing binary is one answer
    # rather than a rediscovery in every agent that meets a legacy file.
    options.libreoffice = None if options.no_libreoffice else libreoffice_at()
    legacy = [p for p in paths if p.suffix.lower() in LIBREOFFICE_SUFFIXES]
    converted = {}
    if legacy and options.libreoffice:
        print(f"{len(legacy)} legacy Office file(s) — converting with {options.libreoffice}")
        converted = convert_legacy(options.libreoffice, legacy, options.out_dir / "converted", options.force)
        if len(converted) < len(legacy):
            print(f"  {len(legacy) - len(converted)} would not convert — they stay unsupported")
    elif legacy:
        where = "--no-libreoffice was passed" if options.no_libreoffice else "LibreOffice is not installed"
        print(f"{len(legacy)} legacy Office file(s) will not be converted: {where}")

    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, options.jobs)) as pool:
        futures = {pool.submit(extract, p, root, extracted_dir, options, converted): p for p in paths}
        for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            path = futures[future]
            try:
                records.append(future.result())
            except Exception as error:
                records.append({
                    "path": str(path).replace("\\", "/"),
                    "relativePath": path.name,
                    "kind": "failed",
                    "textFile": None,
                    "fullTextFile": None,
                    "images": [],
                    "chars": 0,
                    "letters": 0,
                    "charsRead": 0,
                    "pages": None,
                    "pagesRendered": 0,
                    "note": f"{type(error).__name__}: {error}",
                })
            if done % 25 == 0 or done == len(paths):
                print(f"  {done}/{len(paths)} files")
    if missing:
        print(f"  {len(missing)} listed path(s) are not on disk")

    # A listed path that is not on disk still gets a record, so the manifest answers for every input.
    for path in missing:
        records.append({
            "path": str(path).replace("\\", "/"),
            "relativePath": path.name,
            "kind": "missing",
            "textFile": None,
            "fullTextFile": None,
            "images": [],
            "chars": 0,
            "letters": 0,
            "charsRead": 0,
            "pages": None,
            "pagesRendered": 0,
            "note": "listed in the input but not on disk",
        })

    records.sort(key=lambda r: r["relativePath"])
    counts = {}
    for record in records:
        counts[record["kind"]] = counts.get(record["kind"], 0) + 1

    manifest = {
        "root": str(root.resolve()).replace("\\", "/") if root else None,
        "extractedDir": str(extracted_dir.resolve()).replace("\\", "/"),
        "scans": options.scans,
        "maxChars": options.max_chars,
        "libreOffice": options.libreoffice,
        "counts": counts,
        "documents": records,
    }
    (options.out_dir / "EXTRACTED.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n{len(records)} files: " + ", ".join(f"{n} {k}" for k, n in sorted(counts.items())))
    for kind, headline in (
        ("image-only", "NO TEXT LAYER — read the rendered pages, the text is a picture"),
        ("sparse-text", "PART TEXT, PART PICTURE — read both the Markdown and the rendered pages"),
        ("unsupported", "NOT CONVERTED — the user has to re-save these, or tell you what they hold"),
        ("empty", "CONVERTED EMPTY — the file may hold only images, or nothing"),
        ("failed", "FAILED — report these rather than treating them as read"),
        ("missing", "LISTED BUT NOT ON DISK — the input named these and they are not there"),
    ):
        hits = [r for r in records if r["kind"] == kind]
        if not hits:
            continue
        print(f"\n{headline} ({len(hits)}):")
        for record in hits[:SAMPLE]:
            print(f"  {record['relativePath']}" + (f" — {record['note']}" if record["note"] else ""))
        if len(hits) > SAMPLE:
            print(f"  ... and {len(hits) - SAMPLE} more in EXTRACTED.json")

    print(f"\n-> {options.out_dir / 'EXTRACTED.json'}")


if __name__ == "__main__":
    main()
