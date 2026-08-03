"""Join every document in a folder to its upload manifest entry, by SHA-256.

Usage:
    python3 join_manifest.py <folder> <manifest.json> <out_dir>

<manifest.json> is the app's upload manifest: {"documents": [{"fileName", "storageKey", "sha"}]}.

Writes:
  <out_dir>/DOCUMENTS.json      one entry per file in the folder, with its sha and, where the manifest
                                has it, the storage path it was uploaded to
  <out_dir>/DOCUMENT_FILES.json the same files in the shape `assign-documents` reads

Matching is on sha, not file name, so two documents sharing a name in different item folders each
resolve to their own upload.
"""

import hashlib
import json
import sys
from pathlib import Path

SAMPLE = 20
CHUNK = 1 << 20


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("documents") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise SystemExit(f'{path} has no "documents" list')

    by_sha = {}
    for entry in entries:
        sha = str(entry.get("sha", "")).strip().lower()
        if sha:
            by_sha[sha] = entry
    if not by_sha:
        raise SystemExit(f"{path} holds no entries with a sha")
    return by_sha


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)

    root, manifest_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    if not root.is_dir():
        raise SystemExit(f"not a folder: {root}")

    by_sha = load_manifest(manifest_path)
    documents = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = "/".join(path.relative_to(root).parts)
        sha = sha256(path)
        entry = by_sha.get(sha)
        documents.append(
            {
                "path": str(path).replace("\\", "/"),
                "relativePath": relative,
                "folder": "/".join(relative.split("/")[:-1]),
                "name": path.name,
                "sha": sha,
                "fileName": entry.get("fileName") if entry else None,
                "storagePath": entry.get("storageKey") if entry else None,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "DOCUMENTS.json").write_text(
        json.dumps(documents, indent=2), encoding="utf-8"
    )
    (out_dir / "DOCUMENT_FILES.json").write_text(
        json.dumps(
            {"document_files": [{"SHA": d["sha"], "path": d["path"]} for d in documents]},
            indent=2,
        ),
        encoding="utf-8",
    )

    matched = [d for d in documents if d["storagePath"]]
    unmatched = [d for d in documents if not d["storagePath"]]
    renamed = [
        d for d in matched if d["fileName"] and d["fileName"] != d["name"]
    ]
    used = {d["sha"] for d in matched}

    print(f"{len(documents)} files, {len(matched)} matched to an upload, {len(unmatched)} not")
    if unmatched:
        print(
            f"\nNOT UPLOADED - no manifest entry has these files' sha ({len(unmatched)}):"
        )
        for d in unmatched[:SAMPLE]:
            print(f"  {d['relativePath']}")
        if len(unmatched) > SAMPLE:
            print(f"  ... and {len(unmatched) - SAMPLE} more")
    if renamed:
        print(f"\nNAME DIFFERS from the manifest, same file ({len(renamed)}):")
        for d in renamed[:SAMPLE]:
            print(f"  {d['relativePath']} -> {d['fileName']}")
    spare = len(by_sha) - len(used)
    if spare > 0:
        print(f"\n{spare} manifest entry/entries match no file in this folder.")

    print(f"\n-> {out_dir / 'DOCUMENTS.json'}, {out_dir / 'DOCUMENT_FILES.json'}")


if __name__ == "__main__":
    main()
