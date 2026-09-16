"""Whether the text an extraction produced still holds the facts the page printed.

A label is what a person read off the document — an ingredient and the figure beside it — never the
Markdown some converter happened to write. Converters differ in whitespace, heading depth and order, and
all of those differences are fine; a label that pinned them would fail on changes that are correct and
teach nobody anything.

So the question asked here is *recoverability*: can this pair still be found, and found together. The
failure being hunted is misalignment — 45.0 landing beside the wrong ingredient when a column collapses —
so nearness is the whole test. A value that appears somewhere on the page is not evidence; a value that
appears within `window` characters of its own ingredient is.

Nothing here calls a model. The same text scores the same way every time, which is what makes a number
from two different runs worth comparing.
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path

WINDOW = 200
SEPARATOR_ROW = re.compile(r"^\|(?: *-+ *\|)+$")
FIGURE = re.compile(r"\d|balance|q\.s\.|to 100", re.I)


def flatten(text):
    """One spelling of a piece of text, so two renderings of one fact compare equal.

    Case, accents, and every run of punctuation or space become one space. A converter that writes
    `Aqua/Water` where another writes `Aqua / water` has not lost anything, and neither spelling is
    more correct than the other.
    """
    return flatten_with_map(text)[0]


def flatten_with_map(text):
    """The flattened text, and for each of its characters the offset it came from in the original.

    The map exists so distance can be measured where it means something. Flattening collapses runs of
    punctuation, and a Markdown table is mostly punctuation: `Titanium Dioxide` and `98.6` separated by
    380 characters of pipes flatten to 21 apart. Measuring the gap on the flattened text would call that
    adjacent, and tables are exactly what this harness was built to judge.
    """
    folded = unicodedata.normalize("NFKD", str(text or ""))
    flat, origins, gap = [], [], False
    raw = 0
    for character in folded:
        if unicodedata.combining(character):
            raw += 1
            continue
        lowered = character.casefold()
        if re.match(r"[a-z0-9.%]", lowered):
            flat.append(lowered)
            origins.append(raw)
            gap = False
        elif not gap:
            flat.append(" ")
            origins.append(raw)
            gap = True
        raw += 1
    while flat and flat[-1] == " ":
        flat.pop()
        origins.pop()
    start = 0
    while start < len(flat) and flat[start] == " ":
        start += 1
    return "".join(flat[start:]), origins[start:]


def positions(haystack, needle, origins=None):
    """Every place a flattened needle sits in a flattened haystack, as offsets in the original text.

    A match may not be part of a longer token: `1.0` inside `21.05` is a different number, and counting
    it would let a harness report a row recovered off text that never stated it.
    """
    if not needle:
        return []
    found = []
    for match in re.finditer(re.escape(needle), haystack):
        before = haystack[match.start() - 1] if match.start() else " "
        after = haystack[match.end()] if match.end() < len(haystack) else " "
        if re.match(r"[a-z0-9.%]", before) or re.match(r"[a-z0-9.%]", after):
            continue
        found.append(origins[match.start()] if origins else match.start())
    return found


def found_together(text, left, right, window=WINDOW):
    """Whether these two appear within `window` characters of each other in the original text.

    Both present but far apart is the misalignment case, and it reads as a miss on purpose.
    """
    flat, origins = flatten_with_map(text)
    lefts = positions(flat, flatten(left), origins)
    rights = positions(flat, flatten(right), origins)
    if not lefts or not rights:
        return False
    return any(abs(a - b) <= window for a in lefts for b in rights)


def score(text, label, window=WINDOW):
    """One document's rows against the text, as three counts and the rows that failed.

    `recovered` is both halves, near each other. `misaligned` is both halves present but apart — the
    quiet failure, and the one worth counting separately, because a reader will happily quote it.
    `missing` is a half that is not there at all.
    """
    recovered, misaligned, missing = [], [], []
    flat, origins = flatten_with_map(text)
    for row in label.get("rows", []):
        name, value = row.get("ingredient", ""), row.get("value", "")
        has_name = positions(flat, flatten(name), origins)
        has_value = positions(flat, flatten(value), origins)
        if not has_name or not has_value:
            missing.append(row)
        elif any(abs(a - b) <= window for a in has_name for b in has_value):
            recovered.append(row)
        else:
            misaligned.append(row)
    return {
        "document": label.get("document"),
        "rows": len(label.get("rows", [])),
        "recovered": len(recovered),
        "misaligned": len(misaligned),
        "missing": len(missing),
        "failures": misaligned + missing,
    }


def load(folder):
    """Every label in a folder, confirmed ones first and unconfirmed ones flagged.

    A label nobody has checked is a guess about a document, and a score computed over guesses is a
    number that looks like evidence. They are kept, and counted apart.
    """
    confirmed, draft = [], []
    for path in sorted(Path(folder).glob("*.json")):
        label = json.loads(path.read_text(encoding="utf-8"))
        label.setdefault("document", path.stem)
        (confirmed if label.get("confirmed") else draft).append(label)
    return confirmed, draft


def summarise(scores):
    """The one number a run is compared on, with the counts it was made from."""
    rows = sum(s["rows"] for s in scores)
    recovered = sum(s["recovered"] for s in scores)
    misaligned = sum(s["misaligned"] for s in scores)
    return {
        "documents": len(scores),
        "rows": rows,
        "recovered": recovered,
        "misaligned": misaligned,
        "missing": sum(s["missing"] for s in scores),
        "recall": (recovered / rows) if rows else 0.0,
        "misalignmentRate": (misaligned / rows) if rows else 0.0,
    }


def propose(record, text):
    """Draft rows for a document from the tables already read out of it, for a person to check.

    A blank page is a gold set nobody starts. These are guesses off the same extraction they will be
    used to judge, which is circular — so every one is written `confirmed: false`, and `load` keeps
    them out of any number until somebody has read the document and said they are right.
    """
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or SEPARATOR_ROW.match(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        name, value = cells[0], cells[-1]
        if name and value and FIGURE.search(value) and len(name) > 2:
            rows.append({"ingredient": name, "value": value})
    return {
        "document": Path(record.get("path", "")).name,
        "sha": record.get("sha"),
        "confirmed": False,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("labels", help="folder of label files")
    parser.add_argument("--extracted", help="an EXTRACTED.json to score against, or to draft labels from")
    parser.add_argument("--propose", action="store_true", help="write draft labels from documents that have tables")
    parser.add_argument("--window", type=int, default=WINDOW)
    parser.add_argument("--history", default="", help="append the summary here as one JSON line")
    parser.add_argument("--label", default="", help="a name for this measurement")
    args = parser.parse_args()

    folder = Path(args.labels)
    folder.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path(args.extracted).read_text(encoding="utf-8")) if args.extracted else {}
    records = {Path(r["path"]).name: r for r in manifest.get("documents", [])}

    if args.propose:
        written, kept = 0, 0
        for name, record in records.items():
            if not record.get("tablesFound"):
                continue
            text = Path(record["tablesFile"]).read_text(encoding="utf-8")
            draft = propose(record, text)
            if not draft["rows"]:
                continue
            out = folder / f"{Path(name).stem}.json"
            if out.is_file():
                existing = json.loads(out.read_text(encoding="utf-8"))
                if existing.get("confirmed"):
                    kept += 1
                    continue
            out.write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")
            written += 1
        print(f"{written} draft label(s) in {folder}"
              + (f"; {kept} confirmed label(s) left alone" if kept else ""))
        print("Every one says confirmed: false. Read the document, fix the rows, set it true.")
        return

    confirmed, draft = load(folder)
    if not confirmed:
        print(f"No confirmed labels in {folder}. "
              f"{len(draft)} draft(s) are waiting for somebody to check them.")
        return

    scores = []
    for label in confirmed:
        record = records.get(label["document"]) or records.get(f"{label['document']}.pdf")
        if not record:
            print(f"  skipped {label['document']} — not in this extraction")
            continue
        import signals

        scores.append(score(signals.read_text(record), label, args.window))

    summary = summarise(scores)
    summary["label"] = args.label
    summary["skipped"] = len(confirmed) - len(scores)
    print(f"{summary['documents']} document(s), {summary['rows']} row(s)")
    print(f"  recovered   {summary['recovered']:>5}   recall {summary['recall']:.1%}")
    print(f"  misaligned  {summary['misaligned']:>5}   {summary['misalignmentRate']:.1%}")
    print(f"  missing     {summary['missing']:>5}")
    if summary["skipped"]:
        print(f"  {summary['skipped']} label(s) had no record in this extraction and were not counted")
    if draft:
        print(f"  {len(draft)} draft label(s) not counted — nobody has checked them")
    for one in scores:
        if one["failures"]:
            print(f"\n  {one['document']}: {len(one['failures'])} row(s) not recovered")
            for row in one["failures"][:3]:
                print(f"    {row.get('ingredient', '')[:44]:<44} {row.get('value', '')}")
    if args.history:
        with open(args.history, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary) + "\n")
        print(f"\nappended to {args.history}")


if __name__ == "__main__":
    main()
