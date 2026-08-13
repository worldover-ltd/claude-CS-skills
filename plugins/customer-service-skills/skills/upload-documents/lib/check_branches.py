"""Test a tree mapping against the app's real items, before anything expensive runs.

Usage:
    python3 check_branches.py <session_dir> [--samples 10]

Reads <session_dir>: TREE.json (every file), BRANCHES.json (the mapping under test), WORKFLOW.json and
ITEMS.csv (what the app holds). Opens no document and writes nothing — it prints, per branch, how many
of its files reach exactly one live item, and names the ones that do not.

This is the legibility gate's evidence. A branch whose anchor is one level off, or whose folder names
are spelled differently from the app's identifiers, shows up here as a match rate rather than after the
whole folder has been hashed and read.
"""

import argparse
import difflib
import json
import sys
from collections import Counter
from pathlib import Path

import item_index


def load(session_dir, name):
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def near_misses(value, candidates):
    """Identifiers close enough to the folder name that a spelling difference is the likely cause."""
    return difflib.get_close_matches(value, candidates, n=3, cutoff=0.8)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--samples", type=int, default=10, help="examples to print per failure (default: 10)")
    options = parser.parse_args()

    # Windows consoles default to a codepage that cannot print this summary's punctuation.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    files = load(session_dir, "TREE.json").get("files") or []
    branches = load(session_dir, "BRANCHES.json").get("branches") or []

    # A file somebody has already decided not to migrate should not count against the match rate, or the
    # gate reads as unfixable when what is left over is only the folders being left out anyway.
    excluded = item_index.excluded_paths(session_dir)
    if excluded:
        before = len(files)
        files = [f for f in files if f["path"] not in excluded]
        if before != len(files):
            print(f"{before - len(files)} file(s) excluded by decision are not counted here\n")

    if not branches:
        raise SystemExit("BRANCHES.json holds no branches — nothing to check")

    try:
        app = item_index.load(session_dir / "WORKFLOW.json", session_dir / "ITEMS.csv")
    except item_index.ExportError as error:
        raise SystemExit(f"the export cannot be used: {error}")

    unknown = sorted({b.get("table") for b in branches} - set(app.tables))
    if unknown:
        raise SystemExit(
            "these branch tables are not in WORKFLOW.json: "
            + ", ".join(repr(t) for t in unknown)
            + f". The workflow holds: {', '.join(sorted(app.tables))}"
        )

    identifiers_by_table = {
        table: sorted({i["identifier"] for i in app.items if i["table"] == table and i["identifier"]})
        for table in app.tables
    }

    per_branch = {id(b): {"matched": [], "failed": [], "folded": 0, "items": set()} for b in branches}
    unbranched = []
    for record in files:
        relative_path = record["path"]
        branch = item_index.branch_for(relative_path, branches)
        if branch is None:
            unbranched.append(relative_path)
            continue

        tally = per_branch[id(branch)]
        value, why = item_index.identifier_for(relative_path, branch.get("identifier") or {})
        if not value:
            tally["failed"].append((relative_path, None, "unidentified", why))
            continue

        item, how, problem = app.resolve(branch["table"], value)
        if item is None:
            tally["failed"].append((relative_path, value, problem[0], problem[1]))
            continue
        if how != "exact":
            tally["folded"] += 1
        tally["matched"].append(relative_path)
        tally["items"].add(item["id"])

    total_matched = 0
    for branch in branches:
        tally = per_branch[id(branch)]
        covered = len(tally["matched"]) + len(tally["failed"])
        total_matched += len(tally["matched"])
        prefix = branch.get("pathPrefix") or "(the whole tree)"
        print(f"{prefix} -> {branch['table']}")

        if not covered:
            print("  no file matches this prefix — the branch is dead\n")
            continue

        rate = 100.0 * len(tally["matched"]) / covered
        in_app = len(identifiers_by_table[branch["table"]])
        print(
            f"  {len(tally['matched'])}/{covered} file(s) reach one live item ({rate:.0f}%), "
            f"across {len(tally['items'])} item(s) of {in_app} in the app"
        )
        if tally["folded"]:
            print(f"  {tally['folded']} matched only ignoring case — the app spells them differently")

        if tally["failed"]:
            reasons = Counter(kind for _, _, kind, _ in tally["failed"])
            print(f"  {len(tally['failed'])} file(s) reach none:")
            for path, value, kind, why in tally["failed"][: options.samples]:
                # Only a name that matched nothing can be a misspelling; the rest found their item.
                close = near_misses(value, identifiers_by_table[branch["table"]]) if kind == "unmatched" else []
                hint = f"  [did you mean {', '.join(close)}?]" if close else ""
                print(f"    {path} — {why}{hint}")
            if len(tally["failed"]) > options.samples:
                print(f"    ... and {len(tally['failed']) - options.samples} more")
            print("  by reason: " + ", ".join(f"{n} {kind}" for kind, n in reasons.most_common()))
        print()

    if unbranched:
        print(f"NO BRANCH COVERS THESE ({len(unbranched)}):")
        for path in unbranched[: options.samples]:
            print(f"  {path}")
        if len(unbranched) > options.samples:
            print(f"  ... and {len(unbranched) - options.samples} more")
        print()

    verdict = "LEGIBLE" if total_matched == len(files) else "NOT YET LEGIBLE"
    print(f"{verdict}: {total_matched}/{len(files)} file(s) reach exactly one live item")
    if total_matched != len(files):
        print("Fix the mapping and run this again, or take the unresolved folders to the user.")


if __name__ == "__main__":
    main()
