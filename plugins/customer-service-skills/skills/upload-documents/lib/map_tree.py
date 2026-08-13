"""Map a folder of documents into levels, without opening any document.

Usage:
    python3 map_tree.py <folder> <out_dir>

Writes <out_dir>/TREE.json — every file with its depth and path parts — and prints the summary the
level roles are read off. Runs the same on macOS, Linux and Windows: paths are emitted with forward
slashes and text is written as UTF-8.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import item_index

SAMPLE = 12


def walk(root):
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(root).parts
        # A workbook a previous run handed over lives in this folder; it is this skill's output, not the
        # customer's document, and counting it would put it in the totals every later step reconciles.
        if item_index.is_our_own("/".join(parts)):
            continue
        files.append(
            {
                "path": "/".join(parts),
                "folders": list(parts[:-1]),
                "name": parts[-1],
                "ext": path.suffix.lower().lstrip("."),
                "depth": len(parts) - 1,
            }
        )
    return files


def levels(files):
    """Per folder depth: the distinct names at that depth and how often each repeats."""
    out = []
    depth = 0
    while any(len(f["folders"]) > depth for f in files):
        names = Counter(f["folders"][depth] for f in files if len(f["folders"]) > depth)
        out.append(
            {
                "depth": depth,
                "distinct": len(names),
                "files_under": sum(names.values()),
                "names": [name for name, _ in names.most_common()],
                "repeats": names.most_common(SAMPLE),
            }
        )
        depth += 1
    return out


def report(root, files, tree_levels):
    depths = Counter(f["depth"] for f in files)
    print(f"{len(files)} files under {root}")
    print(f"folder depths: {dict(sorted(depths.items()))}\n")

    for level in tree_levels:
        print(
            f"level {level['depth']}: {level['distinct']} distinct names, "
            f"{level['files_under']} files under it"
        )
        print(f"  sample: {', '.join(level['names'][:SAMPLE])}")
        repeated = [f"{name} x{n}" for name, n in level["repeats"] if n > 1]
        if repeated:
            print(f"  most repeated: {', '.join(repeated)}")
        exts = Counter(
            f["ext"] or "(none)" for f in files if len(f["folders"]) > level["depth"]
        )
        print(f"  extensions: {', '.join(f'{e} x{n}' for e, n in exts.most_common(8))}\n")

    if len(depths) > 1:
        print(
            "MIXED DEPTHS: files do not all sit at the same level, so one anchor level may not "
            f"cover them all. Depths present: {sorted(depths)}"
        )
    loose = [f["name"] for f in files if f["depth"] == 0]
    if loose:
        print(
            f"LOOSE AT ROOT: {len(loose)} file(s) have no folder above them "
            f"({', '.join(loose[:SAMPLE])}) - nothing names their item."
        )
    if not tree_levels:
        print("NO FOLDERS: the tree is a flat folder, so any anchor has to come from file names.")


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)

    # Windows consoles default to a codepage that cannot print a customer's folder names, and this
    # script prints them — the first accented name would end the run before anything has been read.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    root, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    if not root.is_dir():
        raise SystemExit(f"not a folder: {root}")

    files = walk(root)
    if not files:
        raise SystemExit(f"no files under {root}")

    tree_levels = levels(files)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "TREE.json").write_text(
        json.dumps(
            {"root": str(root).replace("\\", "/"), "files": files, "levels": tree_levels},
            indent=2,
        ),
        encoding="utf-8",
    )

    report(root, files, tree_levels)
    print(f"\n{len(files)} files -> {out_dir / 'TREE.json'}")


if __name__ == "__main__":
    main()
