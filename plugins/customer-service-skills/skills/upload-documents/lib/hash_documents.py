"""Hash every document in a folder, so each one can be carried into a workbook by its SHA-256.

Usage:
    python3 hash_documents.py <folder> <out_dir>

Writes <out_dir>/DOCUMENTS.json: one entry per file with its path, its folder, its name and its sha.

Skips whatever <out_dir>/EXCLUSIONS.json names, where the exclusion gate has run. That is what keeps a
run from paying to hash, convert and read an archive folder somebody has already said they do not want.

Reads bytes only — nothing here interprets a document's contents.
"""

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import item_index
import progress

SAMPLE = 20
CHUNK = 1 << 20


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)

    # Windows consoles default to a codepage that cannot print a customer's file names, and the
    # duplicate report prints them — the first accented name would end the run.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    root, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    if not root.is_dir():
        raise SystemExit(f"not a folder: {root}")

    excluded = item_index.excluded_paths(out_dir)

    found = sorted(p for p in root.rglob("*") if p.is_file())

    documents, skipped, ours = [], 0, 0
    checking = progress.Pass(len(found), "document files", "Checked")
    checking.start(f"Checking {len(found):,} document files in your folder.")
    for path in found:
        relative = "/".join(path.relative_to(root).parts)
        checking.advance()
        if item_index.is_our_own(relative):
            ours += 1
            continue
        if relative in excluded:
            skipped += 1
            continue
        documents.append(
            {
                "path": str(path).replace("\\", "/"),
                "relativePath": relative,
                "folder": "/".join(relative.split("/")[:-1]),
                "name": path.name,
                "sha": sha256(path),
            }
        )

    if not documents:
        raise SystemExit(f"no files under {root}" + (f" once {skipped} exclusion(s) are applied" if skipped else ""))
    if skipped:
        print(f"{skipped} file(s) left out by decision, per EXCLUSIONS.json")
    if ours:
        print(f"{ours} workbook(s) from an earlier run skipped — a run does not read its own output")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "DOCUMENTS.json").write_text(
        json.dumps(documents, indent=2), encoding="utf-8"
    )

    by_sha = defaultdict(list)
    for document in documents:
        by_sha[document["sha"]].append(document["relativePath"])
    copies = {sha: paths for sha, paths in by_sha.items() if len(paths) > 1}
    checking.close(
        f"Checked {len(found):,} document files in {checking.spent()} — "
        f"{len(by_sha):,} different documents."
    )

    print(f"{len(documents)} files, {len(by_sha)} distinct by content")
    if copies:
        print(
            f"\nSAME FILE IN MORE THAN ONE PLACE ({len(copies)}). The upload matches on sha, so each "
            "of these is one document that belongs to every item it was filed under:"
        )
        for paths in list(copies.values())[:SAMPLE]:
            print(f"  {' | '.join(paths)}")
        if len(copies) > SAMPLE:
            print(f"  ... and {len(copies) - SAMPLE} more")

    print(f"\n-> {out_dir / 'DOCUMENTS.json'}")


if __name__ == "__main__":
    progress.guard(main)
