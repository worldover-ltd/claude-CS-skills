"""Cut the extracted documents into batches a classifier can read, one input file per batch.

Usage:
    python3 plan_batches.py <session_dir> [--batch-size 20] [--max-images 12] [--round 1]

Reads from <session_dir>: WORKFLOW.json and ITEMS.csv (what the app holds), BRANCHES.json (table and
identifier rule per branch), DOCUMENTS.json (every file with its sha), EXTRACTED.json (what can be read
for each).

Writes <session_dir>/batches/batch_NNN.json, one per batch, and <session_dir>/BATCHES.json naming them.
Reports the documents it could not batch — no branch, no identifier, no item of that name, several
items of that name, an archived item, or nothing readable — rather than dropping them.

The unit sent out is a *reading*: one sha per table, not one file. Copies of one document are read once
and the answer is fanned back out, so a folder holding the same certificate under forty items costs one
reading and cannot come back as forty different types. See docs/adr/0001.

Resolves every document to a real item in code: an identifier read off a folder name by eye is a
document filed against the wrong item.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import item_index

SAMPLE = 10

# EXTRACTED.json's `kind` decides what a classifier should open for that document.
READ_FROM = {
    "text": ("textFile",),
    "sparse-text": ("textFile", "images"),
    "image-only": ("images",),
    "image": ("path",),
}

EXCEPTIONS = ("unbranched", "unidentified", "unmatched", "ambiguous", "archived", "unreadable")

# The wider taxonomy a classifier proposes from when the app's own list holds nothing that fits. Passed
# as a path so it is read only by the batches that need it, rather than inlined into every one.
FALLBACK_TEMPLATES = Path(__file__).resolve().parent.parent / "references" / "DOCUMENT_TYPES.txt"

HEADINGS = {
    "unbranched": "NO BRANCH — the tree mapping does not cover these",
    "unidentified": "NO IDENTIFIER — the branch rule yielded nothing, so the item is unknown",
    "unmatched": "NO SUCH ITEM — the folder names an identifier the app does not have",
    "ambiguous": "SEVERAL ITEMS — the identifier is held by more than one item, so it names none",
    "archived": "ARCHIVED — the item exists but is archived, so it takes no documents",
    "unreadable": "NOTHING TO READ — these cannot be classified, so ask the user what they hold",
}


def load(session_dir, name):
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def key_for(path):
    """Compare paths the way the filesystem does, so the input files join reliably."""
    return os.path.normcase(os.path.normpath(str(path).replace("\\", "/")))


def read_from_for(record):
    """(paths, how many of them are pictures, why-not) — the files a classifier should open for this.

    Pictures are counted off the paths themselves rather than taken from `pagesRendered`, which counts
    rendered PDF pages and so is zero for a photograph the customer filed as a document. What the batch
    budget cares about is images arriving in a conversation, and a JPEG is one of those.
    """
    if record is None:
        return [], 0, "not in EXTRACTED.json — the extraction step did not see it"
    fields = READ_FROM.get(record.get("kind"))
    if not fields:
        note = record.get("note") or record.get("kind")
        return [], 0, f"nothing readable ({note})"
    paths = []
    for field in fields:
        value = record.get(field)
        paths.extend(value if isinstance(value, list) else [value] if value else [])
    if not paths:
        return [], 0, f"kind is {record.get('kind')!r} but it carries no file to read"
    return paths, sum(1 for p in paths if not str(p).lower().endswith(".md")), None


def reading_ids_for(keys):
    """{(sha, table): id} — eight hex characters of the sha, made unique where that is not enough.

    Short because the classifier copies it back by hand and a long opaque string is a thing models
    truncate. Eight hex characters collide often enough across tens of thousands of documents to be
    worth resolving rather than hoping about, and the same sha on two tables is two readings sharing a
    prefix by construction.
    """
    ids, taken = {}, {}
    for sha, table in sorted(keys):
        stem = sha[:8]
        seen = taken.get(stem, 0) + 1
        taken[stem] = seen
        ids[(sha, table)] = stem if seen == 1 else f"{stem}-{seen}"
    return ids


def group_into_readings(ready, ids):
    """One reading per (sha, table), carrying every folder its copies sat in.

    What to read comes from the first copy that has anything readable, so a copy whose conversion failed
    is carried by an identical twin that converted rather than reported as unreadable.
    """
    readings = {}
    for document in ready:
        key = (document["sha"], document["table"])
        reading = readings.get(key)
        if reading is None:
            reading = readings[key] = {
                "readingId": ids[key],
                "sha": document["sha"],
                "table": document["table"],
                "readFrom": [],
                "images": 0,
                "folderHints": [],
                "files": [],
            }
        reading["files"].append(document["relativePath"])
        if not reading["readFrom"] and document["readFrom"]:
            reading["readFrom"] = document["readFrom"]
            reading["images"] = document["images"]
        hint = document["folderHint"]
        if hint and hint not in reading["folderHints"]:
            reading["folderHints"].append(hint)
    return list(readings.values())


def cut_into_batches(readings, size, max_images):
    """Batches closed by whichever bites first: the reading count, or the images they carry.

    Images are the cap that matters, because an image is what the API drops out of a prompt mid-read,
    and an agent it happens to answers in full regardless — a short answer would at least be visible.
    """
    chunks, chunk, carried = [], [], 0
    for reading in readings:
        carries = reading["images"]
        # `carried and` lets a single reading over the whole budget through on its own rather than
        # closing an empty batch in front of it forever.
        if chunk and (len(chunk) >= size or (carried and carried + carries > max_images)):
            chunks.append(chunk)
            chunk, carried = [], 0
        chunk.append(reading)
        carried += carries
    if chunk:
        chunks.append(chunk)
    return chunks


def vocabulary_for(app, chunk):
    """The closed list of document templates per table, for one batch.

    Narrowed to the tables this batch's own readings sit on, since that is the only scoping the app has:
    a `Spec Sheet` the app permits only on products is never offered for a raw material. Sections are
    not here at all — the section a document lands in is looked up afterwards, per copy, from the item
    template each copy's item is on. See docs/adr/0002.
    """
    tables = {r["table"] for r in chunk}
    return {"documentTemplates": {table: app.templates_for(table) for table in sorted(tables)}}


def report(heading, rows):
    if not rows:
        return
    print(f"\n{heading} ({len(rows)}):")
    for relative_path, why in rows[:SAMPLE]:
        print(f"  {relative_path} — {why}")
    if len(rows) > SAMPLE:
        print(f"  ... and {len(rows) - SAMPLE} more in BATCHES.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--batch-size", type=int, default=20, help="readings per batch (default: 20)")
    parser.add_argument("--max-images", type=int, default=12,
                        help="images a batch may carry — rendered scan pages and photographs alike, "
                             "whichever cap bites first (default: 12)")
    parser.add_argument("--round", type=int, default=1,
                        help="1 plans every reading; 2 and up plan only what REREAD.json names (default: 1)")
    options = parser.parse_args()
    if options.round < 1:
        raise SystemExit("--round counts from 1")
    suffix = "" if options.round == 1 else f"_r{options.round}"
    options.out_name = f"batches{suffix}"
    options.answers_name = f"classified{suffix}"
    options.manifest_name = f"BATCHES{suffix}.json"

    # Windows consoles default to a codepage that cannot print this summary's punctuation.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    branches = load(session_dir, "BRANCHES.json").get("branches") or []
    documents = load(session_dir, "DOCUMENTS.json")
    extracted = load(session_dir, "EXTRACTED.json").get("documents") or []

    if not branches:
        raise SystemExit("BRANCHES.json holds no branches — the legibility gate has not been settled")

    try:
        app = item_index.load(session_dir / "WORKFLOW.json", session_dir / "ITEMS.csv")
    except item_index.ExportError as error:
        raise SystemExit(f"the export cannot be used: {error}")

    unknown = sorted({b.get("table") for b in branches} - set(app.tables))
    if unknown:
        raise SystemExit(
            "these branch tables are not in WORKFLOW.json: " + ", ".join(repr(t) for t in unknown)
        )

    by_path = {key_for(record["path"]): record for record in extracted}

    ready = []
    failed = {kind: [] for kind in EXCEPTIONS}
    for document in documents:
        relative_path = document["relativePath"]
        branch = item_index.branch_for(relative_path, branches)
        if branch is None:
            failed["unbranched"].append((relative_path, "no branch prefix covers it"))
            continue

        value, why = item_index.identifier_for(relative_path, branch.get("identifier") or {})
        if not value:
            failed["unidentified"].append((relative_path, why))
            continue

        item, _, problem = app.resolve(branch["table"], value)
        if item is None:
            failed[problem[0]].append((relative_path, problem[1]))
            continue

        hint_level = branch.get("hintLevel")
        folders = relative_path.split("/")[:-1]
        paths, images, why = read_from_for(by_path.get(key_for(document["path"])))
        ready.append({
            "path": document["path"],
            "relativePath": relative_path,
            "sha": document["sha"],
            "name": document["name"],
            "table": item["table"],
            "identifier": item["identifier"],
            "itemId": item["id"],
            "itemName": item["name"],
            "itemTemplate": item["template"],
            "folderHint": folders[hint_level - 1] if hint_level and hint_level <= len(folders) else None,
            "readFrom": paths,
            "images": images,
            "whyUnreadable": why,
        })

    ids = reading_ids_for({(d["sha"], d["table"]) for d in ready})
    readings = group_into_readings(ready, ids)

    # A reading with nothing to read takes its whole copy group out, and only after the group has been
    # formed: one readable copy is enough to classify content every copy shares.
    blank = {r["readingId"] for r in readings if not r["readFrom"]}
    readings = [r for r in readings if r["readingId"] not in blank]
    kept = []
    for document in ready:
        document["readingId"] = ids[(document["sha"], document["table"])]
        if document["readingId"] in blank:
            failed["unreadable"].append((document["relativePath"], document["whyUnreadable"]))
        else:
            kept.append(document)
        document.pop("whyUnreadable", None)
    ready = kept

    if not ready:
        # Printed here rather than left to the summary below, which this exit never reaches: a run that
        # batches nothing is exactly the run whose reasons the user needs.
        for kind in EXCEPTIONS:
            report(HEADINGS[kind], failed[kind])
        raise SystemExit("\nno document could be batched — every one is listed above")

    # A later round re-reads only what the collector could not settle, and re-derives the readings from
    # the same inputs rather than trusting a list of them: the ids have to mean the same thing in both
    # rounds for the two answers to be comparable at all.
    if options.round > 1:
        wanted = set(load(session_dir, "REREAD.json").get("readingIds") or [])
        if not wanted:
            raise SystemExit("REREAD.json names no readings — there is nothing to read again")
        readings = [r for r in readings if r["readingId"] in wanted]
        ready = [d for d in ready if d["readingId"] in wanted]
        if not readings:
            raise SystemExit("none of the readings REREAD.json names survived this run's exceptions")

    ready.sort(key=lambda d: d["relativePath"])
    readings.sort(key=lambda r: (r["table"], sorted(r["files"])[0]))
    chunks = cut_into_batches(readings, max(1, options.batch_size), max(1, options.max_images))

    batch_dir = session_dir / options.out_name
    batch_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / options.answers_name).mkdir(parents=True, exist_ok=True)

    entries = []
    for number, chunk in enumerate(chunks, 1):
        # The classifier is given only what it must read, so its context goes on documents. The
        # vocabulary is narrowed to this batch's tables for the same reason.
        payload = {
            "batch": number,
            "fallbackTemplates": str(FALLBACK_TEMPLATES).replace("\\", "/"),
            "vocabulary": vocabulary_for(app, chunk),
            "documents": [
                {k: r[k] for k in ("readingId", "table", "folderHints", "readFrom")} for r in chunk
            ],
        }
        input_path = batch_dir / f"batch_{number:03d}.json"
        input_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        entries.append({
            "batch": number,
            "input": str(input_path.resolve()).replace("\\", "/"),
            "output": str(
                (session_dir / options.answers_name / f"batch_{number:03d}.json").resolve()
            ).replace("\\", "/"),
            "readingIds": [r["readingId"] for r in chunk],
            "images": sum(r["images"] for r in chunk),
        })

    counts = {
        "files": len(ready),
        "readings": len(readings),
        "readingsSaved": len(ready) - len(readings),
        "batches": len(entries),
    }
    counts.update({kind: len(failed[kind]) for kind in EXCEPTIONS})
    manifest = {
        "round": options.round,
        "batchSize": max(1, options.batch_size),
        "maxImagesPerBatch": max(1, options.max_images),
        "counts": counts,
        "documents": ready,
        "readings": readings,
        "batches": entries,
        "exceptions": {
            kind: [{"relativePath": p, "why": w} for p, w in failed[kind]] for kind in EXCEPTIONS
        },
    }
    (session_dir / options.manifest_name).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        f"{len(ready)} of {len(documents)} documents, read as {len(readings)} reading(s) "
        f"in {len(entries)} batch(es)"
    )
    if counts["readingsSaved"]:
        print(f"  {counts['readingsSaved']} reading(s) saved by copies sharing content")
    if options.round == 1:
        for kind in EXCEPTIONS:
            report(HEADINGS[kind], failed[kind])
    print(f"\n-> {session_dir / options.manifest_name}")


if __name__ == "__main__":
    main()
