"""Decide which files the migration is not going to carry, before anything is read.

Usage:
    python3 plan_exclusions.py <session_dir>                       # what could be left out
    python3 plan_exclusions.py <session_dir> --folders Oud,Old --extensions msg,eml,db
    python3 plan_exclusions.py <session_dir> --none                # carry everything

Reads <session_dir>/TREE.json. With no rules it prints the candidates and writes nothing; with rules it
writes <session_dir>/EXCLUSIONS.json, which the hashing step reads and the workbook reports from.

An exclusion is not a failure. A file that fails is one the run could not read; a file that is excluded
is one somebody decided not to migrate, and the workbook says so in those words. Asking before the
hashing step is what makes the difference: an archive folder nobody wants costs nothing to leave out
here, and a full conversion and reading each if it is left in.

Nothing is excluded unless it is named. There is no default drop list: a blanket rule on names is what
silently dropped real documents the last time, since 132 of that customer's files genuinely ended
`.pdf.pdf`.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SAMPLE = 25

# Names that mean "somebody kept this but stopped using it". Bounded on letters and digits rather
# than on word boundaries, so `Gold` and `Bolder` are left alone while `_old` is caught: an underscore
# is a word character, and a word boundary does not fire between one and a letter.
#
# This list decides nothing. It changes the order the candidates are printed in and marks them; a file
# is still only left out once the user names the folder.
HINTS = re.compile(
    r"(?<![a-z0-9])(?:archiv\w*|archief|old|oud|oudste|previous|vorige|superseded|obsolete|"
    r"vervallen|verlopen|expired|backups?|back-ups?|kopie|alt|alte|veraltet|deprecated|"
    r"niet\s+meer\s+gebruiken|do\s+not\s+use|unused|temp|tmp|prullenbak|trash|"
    r"ancien\w*|historie|history|historisch\w*)(?![a-z0-9])", re.I)


def hinted(name):
    """Whether a folder's name says, on its own, that somebody stopped using what is in it."""
    return bool(HINTS.search(name or ""))


def load(session_dir, name):
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def folder_candidates(files):
    """[(name, parents it sits under, files beneath it, its name says so)], likeliest first.

    Two shapes, and repetition only finds one of them. A name somebody repeated under every item —
    `Oud`, `Offertes`, `Mail` — is a category, and ranking by how many different parents it sits under
    puts those first while an item's own folder sinks. But one `Archive` at the top of the tree sits
    under a single parent however many thousands of files it holds, so that ranking buries it below
    every item folder and out of the sample the user is shown.

    So a name that says what it is comes first regardless, marked, and the repetition ranking orders
    everything within each group. Nothing here excludes anything; this is the order of a list somebody
    is about to be asked about.
    """
    parents, beneath = defaultdict(set), Counter()
    for record in files:
        folders = record["folders"]
        for depth, name in enumerate(folders):
            key = name.casefold()
            parents[key].add("/".join(folders[:depth]))
            beneath[key] += 1
    rows = [(key, len(parents[key]), beneath[key], hinted(key)) for key in beneath]
    return sorted(rows, key=lambda row: (not row[3], -row[1], -row[2], row[0]))


def excluded_by(record, folders, extensions):
    """The rule that catches this file, or None."""
    for name in record["folders"]:
        if name.casefold() in folders:
            return f"in a folder named {name!r}"
    if (record["ext"] or "").casefold() in extensions:
        return f"a .{record['ext']} file"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--folders", default="", help="comma-separated folder names to leave out")
    parser.add_argument("--extensions", default="", help="comma-separated extensions to leave out, without dots")
    parser.add_argument("--none", action="store_true", help="record that everything is being carried")
    options = parser.parse_args()

    # Windows consoles default to a codepage that cannot print a customer's folder names.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    files = load(session_dir, "TREE.json").get("files") or []
    if not files:
        raise SystemExit("TREE.json holds no files")

    folders = {name.casefold() for name in as_list(options.folders)}
    extensions = {ext.casefold().lstrip(".") for ext in as_list(options.extensions)}

    if not folders and not extensions and not options.none:
        print(f"{len(files)} file(s) in the tree. Nothing is excluded until you name it.\n")

        def show(rows, heading):
            print(heading)
            for name, parent_count, count, _ in rows[:SAMPLE]:
                where = "one place" if parent_count == 1 else f"{parent_count} different places"
                print(f"  {name!r} — {count} file(s), in {where}")
            if len(rows) > SAMPLE:
                print(f"  ... and {len(rows) - SAMPLE} more")

        rows = folder_candidates(files)
        flagged = [row for row in rows if row[3]]
        if flagged:
            show(flagged, f"FOLDER NAMES THAT SAY THEY ARE PUT AWAY ({len(flagged)}) — ask about these first:")
            print()
        rest = [row for row in rows if not row[3]]
        show(rest, f"EVERY OTHER FOLDER NAME ({len(rest)}), the ones that repeat across the tree first:")

        exts = Counter((f["ext"] or "(none)").casefold() for f in files)
        print(f"\nEXTENSIONS ({len(exts)}):")
        for ext, count in exts.most_common(SAMPLE):
            print(f"  .{ext} — {count} file(s)")
        if len(exts) > SAMPLE:
            print(f"  ... and {len(exts) - SAMPLE} more")

        print(
            "\nPut these to the user, then run this again with --folders and --extensions, or --none "
            "to carry everything. Whatever is excluded is counted and named on the workbook, never "
            "dropped in silence."
        )
        return

    excluded, kept = [], 0
    for record in files:
        why = excluded_by(record, folders, extensions)
        if why:
            excluded.append({"relativePath": record["path"], "why": why})
        else:
            kept += 1

    reasons = Counter(row["why"] for row in excluded)
    (session_dir / "EXCLUSIONS.json").write_text(
        json.dumps({
            "rules": {"folders": sorted(folders), "extensions": sorted(extensions)},
            "counts": {"excluded": len(excluded), "carried": kept, "inTree": len(files)},
            "byRule": dict(reasons.most_common()),
            "files": excluded,
        }, indent=2),
        encoding="utf-8",
    )

    print(f"{kept} of {len(files)} file(s) carried, {len(excluded)} left out by decision")
    for why, count in reasons.most_common():
        print(f"  {count} — {why}")
    if not excluded and (folders or extensions):
        print("  no file matched these rules — check the spelling against the candidates above")
    print(f"\n-> {session_dir / 'EXCLUSIONS.json'}")


if __name__ == "__main__":
    main()
