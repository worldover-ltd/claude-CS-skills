"""Choose what a person should look at, and put it somewhere a published page can reach.

Usage:
    python3 build_review.py <session_dir> [--random 8] [--suspect 6] [--width 700] [--seed 0]

Reads `FORMS.json`, `NAMED.json`, `DOCUMENTS.json` and `EXTRACTED.json`; writes `REVIEW.json` — one entry
per form, carrying samples with a rendered page embedded where there is one and a few lines of text where
there is not.

Everything travels **inside** the file, because a published page can reach nothing on this machine.

Three blocks per form, and the difference between them is the point:

- **random** — a fair sample. The only block a failure rate may be counted from.
- **suspect** — the members that joined the form least convincingly. Good at finding mistakes, useless
  for measuring, because it is chosen to look wrong.
- **filled** — the two ends of how much was *typed into* the form, which is the one thing `fit` cannot
  see. Measured on the folder this came from: the form holding 45 specifications and 23 certificates of
  analysis scored 0.795 and 0.806 on `fit`, so choosing by fit — either end of it — hands a person the
  same mixture they would get at random. What separates those documents is a filled-in results column,
  and this block is what puts a blank one beside a filled one.

Mixing them is a real mistake and not an obvious one: a strip that puts the worst members first makes a
good form look bad, and the better the choosing gets the worse every form scores.
"""

import argparse
import base64
import io
import json
import re
import sys
from pathlib import Path

RANDOM, SUSPECT, FILLED = 8, 6, 4
WIDTH, QUALITY = 700, 66
LINES = 14
DIGITS = re.compile(r"\d")
# A published page has a hard ceiling, and scans are most of what fills it.
BUDGET_MB = 14.0


def load(session_dir, name):
    """One of the run's manifests. This folder reads the grouping step's output as data, never as code —
    the two talk through JSON like every other seam in this skill, so either can be lifted out alone."""
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def first_lines(record, count):
    """The head of whatever was read of one document, for a sample with no rendered page to show."""
    best = ""
    for field in ("textFile", "ocrTextFile"):
        source = record.get(field)
        if not source:
            continue
        try:
            body = Path(source).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(body) > len(best):
            best = body
    return [line for line in best.splitlines() if line.strip()][:count]


def thumbnail(path, width, quality):
    """One rendered page, small enough to travel. None where there is no picture or no encoder."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        image = Image.open(path).convert("RGB")
    except Exception:  # every decoder raises its own
        return None
    image.thumbnail((width, width * 2))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def how_filled(record):
    """How much of this document is digits, 0 to 1 — a stand-in for how much was typed into the form.

    Crude on purpose. A form's printed words are the same on every copy, so what varies between a blank
    sheet and a completed one is mostly numbers: results, lot numbers, dates, quantities. It does not
    need to be right about any one document, only to sort the extremes far enough apart that the two
    ends of the list are worth putting side by side.
    """
    best = ""
    for field in ("textFile", "ocrTextFile"):
        source = record.get(field)
        if not source:
            continue
        try:
            body = Path(source).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(body) > len(best):
            best = body
    return len(DIGITS.findall(best)) / len(best) if best else 0.0


def spread(rows, count):
    """An even walk through a list, so a sample crosses the whole form rather than its first corner."""
    if count <= 0 or not rows:
        return []
    if len(rows) <= count:
        return list(rows)
    step = len(rows) / count
    return [rows[int(n * step)] for n in range(count)]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--random", type=int, default=RANDOM,
                        help=f"fairly-chosen members shown per form — the only ones counted "
                             f"(default: {RANDOM})")
    parser.add_argument("--suspect", type=int, default=SUSPECT,
                        help=f"least-convincing members shown per form, never counted "
                             f"(default: {SUSPECT})")
    parser.add_argument("--filled", type=int, default=FILLED,
                        help=f"members shown from both ends of how much was typed into the form, never "
                             f"counted (default: {FILLED})")
    parser.add_argument("--width", type=int, default=WIDTH, help=f"thumbnail width (default: {WIDTH})")
    parser.add_argument("--seed", type=int, default=0, help="makes the random block the same twice")
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    import random as randomness
    session_dir = options.session_dir
    forms = load(session_dir, "FORMS.json")
    if forms.get("skipped"):
        raise SystemExit(f"nothing to review: {forms['skipped']}")

    named = {f["formId"]: f for f in (load(session_dir, "NAMED.json").get("forms") or [])} \
        if (session_dir / "NAMED.json").is_file() else {}
    documents = {d["sha"]: d for d in load(session_dir, "DOCUMENTS.json")}
    extracted = {r["path"]: r for r in (load(session_dir, "EXTRACTED.json").get("documents") or [])}

    chooser = randomness.Random(options.seed)
    out, embedded, drawn = [], 0, 0
    for form in forms["forms"]:
        members = list(form["members"])
        fit = form.get("fit") or {}
        fair = sorted(chooser.sample(members, min(options.random, len(members))))
        # Least convincing first: whatever joined on the thinnest overlap is where a wrong form hides.
        rest = [sha for sha in sorted(members, key=lambda s: fit.get(s, 1.0)) if sha not in fair]
        suspect = rest[:options.suspect]

        # Both ends of how much was typed in, halved between them, skipping anything already shown.
        taken = set(fair) | set(suspect)
        by_fill = sorted((sha for sha in members if sha not in taken),
                         key=lambda s: (how_filled(extracted.get((documents.get(s) or {}).get("path"))
                                                   or {}), s))
        half = max(1, options.filled // 2) if options.filled else 0
        filled = (by_fill[:half] + by_fill[-half:])[:options.filled] if by_fill else []

        samples = []
        for block, chosen in (("random", fair), ("suspect", suspect), ("filled", filled)):
            for sha in chosen:
                document = documents.get(sha) or {}
                record = extracted.get(document.get("path")) or {}
                images = record.get("images") or []
                picture = thumbnail(images[0], options.width, QUALITY) if images else None
                if picture:
                    embedded += 1
                samples.append({
                    "sha": sha, "block": block,
                    "name": document.get("name") or sha,
                    "path": (document.get("path") or "").replace("/", "\\"),
                    "fit": fit.get(sha, 1.0),
                    "filled": round(how_filled(record), 4),
                    "image": picture,
                    "lines": None if picture else first_lines(record, LINES),
                })
                drawn += 1

        entry = named.get(form["id"], {})
        out.append({
            "formId": form["id"],
            "title": entry.get("title") or f"Form {form['id']}",
            "description": entry.get("description") or "",
            "documents": len(members),
            "randomShown": len(fair),
            "suspectShown": len(suspect),
            "filledShown": len(filled),
            # Said rather than left to subtraction: a sample that bounds coverage has to admit by how much.
            "notShown": len(members) - len(fair) - len(suspect) - len(filled),
            "samples": samples,
        })

    payload = {"forms": out, "documents": forms.get("documents"), "shown": drawn}
    written = session_dir / "REVIEW.json"
    written.write_text(json.dumps(payload), encoding="utf-8")
    size = written.stat().st_size / 1024 / 1024

    print(f"{len(out)} form(s), {drawn} sample(s) to look at, {embedded} with a rendered page")
    hidden = sum(form["notShown"] for form in out)
    if hidden:
        print(f"  {hidden} document(s) are in a form but not shown — a sample bounds what anyone sees, "
              f"and the fair block is the only part a rate is counted from")
    if not embedded and any(s["lines"] for f in out for s in f["samples"]):
        print("  no rendered pages — samples carry their first lines of text instead")
    if size > BUDGET_MB:
        print(f"  WARNING: {size:.1f} MB is close to what a published page can hold. "
              f"Lower --random, --suspect or --width.")
    print(f"\n-> {written} ({size:.1f} MB)")


if __name__ == "__main__":
    main()
