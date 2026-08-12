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
    uv run extract_documents.py <folder-or-json> <out_dir> [--scans first|all|none]
        [--scale 2.0] [--max-pages 40] [--enhance] [--jobs 4] [--force]

<folder-or-json> is a folder to walk, or a JSON file holding either a list of paths or
{"documents": [{"path": ...}]}.

Writes text to <out_dir>/extracted/<slug>.md, page images to <out_dir>/extracted/<slug>/page_NNN.png,
and one record per input file to <out_dir>/EXTRACTED.json.

Nothing here interprets a document. A file becomes Markdown or PNGs; reading it is the caller's job.
"""

import argparse
import concurrent.futures
import hashlib
import json
import logging
import re
import shutil
import sys
import tempfile
import threading
import warnings
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
UNSUPPORTED_SUFFIXES = {".doc", ".rtf", ".odt", ".ods", ".odp", ".pages", ".numbers", ".key", ".7z", ".rar"}

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
    if options.scans == "none":
        record["kind"], record["note"] = "failed", note
        return record
    try:
        pages = page_count(path)
        wanted = [1] if options.scans == "first" else list(range(1, min(pages, options.max_pages) + 1))
        written = render_pages(
            path, dest, options.scale, wanted, options.enhance, options.max_px, options.force
        )
    except Exception:
        record["kind"], record["note"] = "failed", note
        return record

    record["kind"] = "image-only"
    record["pages"] = pages
    record["images"] = [str(p.resolve()).replace("\\", "/") for p in written]
    record["pagesRendered"] = len(written)
    record["note"] = f"text extraction failed ({note}) — the rendered page(s) are what there is to read"
    if options.scans == "first" and pages > 1:
        record["note"] += f"; page 1 of {pages} rendered — re-run with --scans all for the rest"
    return record


def extract(path, root, out_dir, options):
    record = {
        "path": str(path).replace("\\", "/"),
        "relativePath": "/".join(path.relative_to(root).parts) if root else path.name,
        "kind": None,
        "textFile": None,
        "images": [],
        "chars": 0,
        "letters": 0,
        "pages": None,
        "pagesRendered": 0,
        "note": None,
    }
    slug = slug_for(path)
    suffix = path.suffix.lower()
    signature = sniff(path)

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
        record["note"] = f"MarkItDown does not convert {suffix} — ask the user to re-save it"
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

    record["chars"] = len(text.strip())
    record["letters"] = len(LETTER.findall(text))
    record["textFile"] = str(text_file.resolve()).replace("\\", "/")

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

    if record["kind"] == "text" or options.scans == "none":
        if record["kind"] != "text":
            note_that(record, "no text layer — nothing rendered, --scans was none")
        return record

    wanted = [1] if options.scans == "first" else list(range(1, min(pages, options.max_pages) + 1))
    try:
        written = render_pages(
            path, out_dir / slug, options.scale, wanted, options.enhance, options.max_px, options.force
        )
    except Exception as error:
        note_that(record, f"could not render pages: {type(error).__name__}: {error}")
        return record

    record["images"] = [str(p.resolve()).replace("\\", "/") for p in written]
    record["pagesRendered"] = len(written)
    if options.scans == "all" and pages > options.max_pages:
        note_that(record, f"rendered {options.max_pages} of {pages} pages — raise --max-pages for the rest")
    elif options.scans == "first" and pages > 1:
        note_that(record, f"page 1 of {pages} rendered — re-run with --scans all to see the rest")
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
    parser.add_argument("--scans", choices=["first", "all", "none"], default="first",
                        help="pages to render for a PDF with no text layer (default: first)")
    parser.add_argument("--scale", type=float, default=2.0, help="render scale, 1.0 is 72 dpi (default: 2.0)")
    parser.add_argument("--max-pages", type=int, default=40, help="page cap for --scans all (default: 40)")
    parser.add_argument("--max-px", type=int, default=2000, help="longest side of a rendered page (default: 2000)")
    parser.add_argument("--enhance", action="store_true", help="grayscale, raise contrast and sharpen each render")
    parser.add_argument("--jobs", type=int, default=4, help="files converted at once (default: 4)")
    parser.add_argument("--force", action="store_true", help="re-convert files already extracted")
    options = parser.parse_args()

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

    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, options.jobs)) as pool:
        futures = {pool.submit(extract, p, root, extracted_dir, options): p for p in paths}
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
                    "images": [],
                    "chars": 0,
                    "letters": 0,
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
            "images": [],
            "chars": 0,
            "letters": 0,
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
