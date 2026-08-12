"""Cut the extracted documents into batches a classifier can read, one input file per batch.

Usage:
    python3 plan_batches.py <session_dir> [--batch-size 20] [--out-name batches]

Reads from <session_dir>: APP_TEMPLATES.json (the vocabulary), BRANCHES.json (entity and identifier rule
per branch), DOCUMENTS.json (every file with its sha), EXTRACTED.json (what can be read for each).

Writes <session_dir>/batches/batch_NNN.json, one per batch, and <session_dir>/BATCHES.json naming them.
Reports the documents it could not batch — no branch, no identifier value, or nothing readable — rather
than dropping them.

Resolves identifiers in code: an identifier read off a folder name by eye is a document filed against the
wrong item.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

SAMPLE = 10

# EXTRACTED.json's `kind` decides what a classifier should open for that document.
READ_FROM = {
    "text": ("textFile",),
    "sparse-text": ("textFile", "images"),
    "image-only": ("images",),
    "image": ("path",),
}


def load(session_dir, name):
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def key_for(path):
    """Compare paths the way the filesystem does, so the three input files join reliably."""
    return os.path.normcase(os.path.normpath(str(path).replace("\\", "/")))


def branch_for(relative_path, branches):
    """The branch with the longest matching prefix — a root-level branch uses an empty prefix."""
    matches = [b for b in branches if relative_path.startswith(b.get("pathPrefix", ""))]
    return max(matches, key=lambda b: len(b.get("pathPrefix", ""))) if matches else None


def identifier_for(relative_path, rule):
    """(value, why-not) — the identifier this document's branch rule yields, or why it yielded nothing."""
    parts = relative_path.split("/")
    folders, name = parts[:-1], parts[-1]
    kind = rule.get("type")

    if kind == "folderLevel":
        level = rule.get("level")
        if not isinstance(level, int) or level < 1:
            return None, f"folderLevel needs a level of 1 or more, got {level!r}"
        if level > len(folders):
            return None, f"only {len(folders)} folder level(s) above this file, rule wants level {level}"
        return folders[level - 1].strip(), None

    if kind == "fileName":
        pattern = rule.get("pattern")
        if not pattern:
            return None, "fileName rule carries no pattern"
        found = re.search(pattern, name)
        if not found:
            return None, f"pattern {pattern!r} does not match {name!r}"
        return (found.group(1) if found.groups() else found.group(0)).strip(), None

    return None, f"unknown identifier rule type {kind!r}"


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


def vocabulary_from(templates):
    entities = templates.get("entityTemplates") or []
    return {
        "documentTemplates": templates.get("documentTemplates") or [],
        "sections": {e["name"]: e.get("sections") or [] for e in entities if e.get("name")},
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
    templates = load(session_dir, "APP_TEMPLATES.json")
    branches = load(session_dir, "BRANCHES.json").get("branches") or []
    documents = load(session_dir, "DOCUMENTS.json")
    extracted = load(session_dir, "EXTRACTED.json").get("documents") or []

    if not branches:
        raise SystemExit("BRANCHES.json holds no branches — the legibility gate has not been settled")

    known_entities = {e.get("name") for e in templates.get("entityTemplates") or []}
    unknown = sorted({b.get("entity") for b in branches} - known_entities)
    if unknown:
        raise SystemExit(
            "these branch entities are not in APP_TEMPLATES.json: "
            + ", ".join(repr(name) for name in unknown)
        )

    by_path = {key_for(record["path"]): record for record in extracted}
    vocabulary = vocabulary_from(templates)

    ready, unbranched, unidentified, unreadable = [], [], [], []
    for document in documents:
        relative_path = document["relativePath"]
        branch = branch_for(relative_path, branches)
        if branch is None:
            unbranched.append((relative_path, "no branch prefix covers it"))
            continue

        value, why = identifier_for(relative_path, branch.get("identifier") or {})
        if not value:
            unidentified.append((relative_path, why))
            continue

        paths, why = read_from_for(by_path.get(key_for(document["path"])))
        if not paths:
            unreadable.append((relative_path, why))
            continue

        hint_level = branch.get("hintLevel")
        folders = relative_path.split("/")[:-1]
        ready.append({
            "path": document["path"],
            "relativePath": relative_path,
            "sha": document["sha"],
            "name": document["name"],
            "entity": branch["entity"],
            "identifier": value,
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
        # The classifier is given only what it must read, so its context goes on documents.
        payload = {
            "batch": number,
            "vocabulary": vocabulary,
            "documents": [
                {k: d[k] for k in ("path", "entity", "folderHint", "readFrom")} for d in chunk
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

    manifest = {
        "batchSize": size,
        "counts": {
            "batched": len(ready),
            "batches": len(entries),
            "unbranched": len(unbranched),
            "unidentified": len(unidentified),
            "unreadable": len(unreadable),
        },
        "documents": ready,
        "batches": entries,
        "exceptions": {
            "unbranched": [{"relativePath": p, "why": w} for p, w in unbranched],
            "unidentified": [{"relativePath": p, "why": w} for p, w in unidentified],
            "unreadable": [{"relativePath": p, "why": w} for p, w in unreadable],
        },
    }
    (session_dir / "BATCHES.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"{len(ready)} of {len(documents)} documents in {len(entries)} batch(es) of {size}")
    report("NO BRANCH — the tree mapping does not cover these", unbranched)
    report("NO IDENTIFIER — the branch rule yielded nothing, so the item is unknown", unidentified)
    report("NOTHING TO READ — these cannot be classified, so ask the user what they hold", unreadable)
    print(f"\n-> {session_dir / 'BATCHES.json'}")


if __name__ == "__main__":
    main()
