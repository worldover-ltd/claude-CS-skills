"""Cut the extracted documents into batches a classifier can read, one input file per batch.

Usage:
    python3 plan_batches.py <session_dir> [--batch-size 20] [--out-name batches]

Reads from <session_dir>: WORKFLOW.json and ITEMS.csv (what the app holds), BRANCHES.json (table and
identifier rule per branch), DOCUMENTS.json (every file with its sha), EXTRACTED.json (what can be read
for each).

Writes <session_dir>/batches/batch_NNN.json, one per batch, and <session_dir>/BATCHES.json naming them.
Reports the documents it could not batch — no branch, no identifier, no item of that name, several
items of that name, an archived item, or nothing readable — rather than dropping them.

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
    """(paths, why-not) — the files a classifier should open for this document."""
    if record is None:
        return [], "not in EXTRACTED.json — the extraction step did not see it"
    fields = READ_FROM.get(record.get("kind"))
    if not fields:
        note = record.get("note") or record.get("kind")
        return [], f"nothing readable ({note})"
    paths = []
    for field in fields:
        value = record.get(field)
        paths.extend(value if isinstance(value, list) else [value] if value else [])
    if not paths:
        return [], f"kind is {record.get('kind')!r} but it carries no file to read"
    return paths, None


def vocabulary_for(app, chunk):
    """The closed list per table, and the sections per item template, for one batch.

    Both are narrowed to what this batch's own documents can use: templates by the tables present, since
    that is the only scoping the app has, and sections by the item templates present. A classifier is
    never shown a template the app would refuse, nor a section belonging to an item template no document
    here sits on.
    """
    tables = {d["table"] for d in chunk}
    item_templates = {d["itemTemplate"] for d in chunk if d["itemTemplate"]}
    return {
        "documentTemplates": {table: app.templates_for(table) for table in sorted(tables)},
        "sections": {
            name: [
                {"label": s["label"], "documentTemplates": s["documentTemplates"]}
                for s in app.item_templates[name]["sections"]
            ]
            for name in sorted(item_templates)
            if name in app.item_templates
        },
    }


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
    parser.add_argument("--batch-size", type=int, default=20, help="documents per batch (default: 20)")
    parser.add_argument("--out-name", default="batches", help="folder for the batch input files")
    options = parser.parse_args()

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

        paths, why = read_from_for(by_path.get(key_for(document["path"])))
        if not paths:
            failed["unreadable"].append((relative_path, why))
            continue

        hint_level = branch.get("hintLevel")
        folders = relative_path.split("/")[:-1]
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
        })

    if not ready:
        raise SystemExit("no document could be batched — see the exceptions above")

    ready.sort(key=lambda d: d["relativePath"])
    size = max(1, options.batch_size)
    chunks = [ready[i : i + size] for i in range(0, len(ready), size)]

    batch_dir = session_dir / options.out_name
    batch_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "classified").mkdir(parents=True, exist_ok=True)

    entries = []
    for number, chunk in enumerate(chunks, 1):
        # The classifier is given only what it must read, so its context goes on documents. The
        # vocabulary is narrowed to this batch's tables for the same reason.
        payload = {
            "batch": number,
            "fallbackTemplates": str(FALLBACK_TEMPLATES).replace("\\", "/"),
            "vocabulary": vocabulary_for(app, chunk),
            "documents": [
                {k: d[k] for k in ("path", "table", "itemTemplate", "folderHint", "readFrom")}
                for d in chunk
            ],
        }
        input_path = batch_dir / f"batch_{number:03d}.json"
        input_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        entries.append({
            "batch": number,
            "input": str(input_path.resolve()).replace("\\", "/"),
            "output": str((session_dir / "classified" / f"batch_{number:03d}.json").resolve()).replace("\\", "/"),
            "paths": [d["path"] for d in chunk],
        })

    counts = {"batched": len(ready), "batches": len(entries)}
    counts.update({kind: len(failed[kind]) for kind in EXCEPTIONS})
    manifest = {
        "batchSize": size,
        "counts": counts,
        "documents": ready,
        "batches": entries,
        "exceptions": {
            kind: [{"relativePath": p, "why": w} for p, w in failed[kind]] for kind in EXCEPTIONS
        },
    }
    (session_dir / "BATCHES.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"{len(ready)} of {len(documents)} documents in {len(entries)} batch(es) of {size}")
    for kind in EXCEPTIONS:
        report(HEADINGS[kind], failed[kind])
    print(f"\n-> {session_dir / 'BATCHES.json'}")


if __name__ == "__main__":
    main()
