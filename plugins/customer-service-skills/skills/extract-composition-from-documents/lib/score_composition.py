"""Which of a customer's files could be a composition, and for which raw material.

Usage:
    python3 score_composition.py <session_dir> [--shortlist 6] [--floor 3]

Reads from <session_dir>: BRANCHES.json, WORKFLOW.json and ITEMS.csv (the folder-to-item machinery
`upload-documents` already built), DOCUMENTS.json and EXTRACTED.json.

Writes <session_dir>/CANDIDATES.json: per material, the files that look like they state a composition,
best first, each with what it scored on and every date it prints.

Nothing here decides anything. It culls, because a folder of three thousand files cannot go in front of
a sub agent and a composition is a handful of them - on the folder this came from, 148 files across 26
materials held a composition between them. What survives the cull is judged by an agent, which is the
only thing that can tell a composition from a hazard band that resembles one.

The cull is deliberately loose. A file wrongly shortlisted costs an agent a few hundred tokens; a file
wrongly culled is a composition nobody ever sees, and the run reports that material as having none.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "upload-documents" / "lib"))

import codes
import dates as dates_module
import item_index

# The headings suppliers print over a composition. Worth more than any other signal: a document that
# says "Composition / information on ingredients" is telling you what the table under it is.
HEADING = re.compile(
    r"composition\s*[/:]?\s*information|information on ingredients|composition breakdown|"
    r"product composition|ingredient declaration|inci breakdown|components \(inci|"
    r"\bsection\s*3\b|\bcomposition\b", re.I)
PERCENT = re.compile(r"\d+(?:[.,]\d+)?\s*(?:[-\u2013]\s*\d+(?:[.,]\d+)?\s*)?%")
BALANCE = re.compile(r"\bbalance\b|\bto\s*100\s*%|\bq\.?s\.?\s*(?:to|ad)\b|\bad\s*100\b", re.I)
INCI = re.compile(r"\bINCI\b", re.I)


def read_text(record):
    """What the extraction got out of this file, whichever way it got it."""
    for key in ("textFile", "ocrTextFile"):
        path = record.get(key)
        if path and Path(path).is_file():
            text = Path(path).read_text(encoding="utf-8")
            if text.strip():
                return text
    return ""


def score(text):
    """How much this file looks like it states a composition, and what it scored on."""
    signals, points = [], 0
    if HEADING.search(text):
        signals.append("composition heading")
        points += 4
    percentages = PERCENT.findall(text)
    if len(percentages) >= 2:
        signals.append(f"{len(percentages)} percentages")
        points += 2
    elif percentages:
        signals.append("one percentage")
        points += 1
    found = codes.find(text, "cas")
    if found:
        signals.append(f"{len(found)} CAS number(s)")
        points += 2 if len(found) > 1 else 1
    if INCI.search(text):
        signals.append("names INCI")
        points += 1
    if BALANCE.search(text):
        signals.append("a balance line")
        points += 1
    return points, signals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--shortlist", type=int, default=6, help="most candidates kept per material")
    parser.add_argument("--floor", type=int, default=3, help="lowest score a candidate may have")
    args = parser.parse_args()
    session = args.session_dir

    load = lambda name: json.loads((session / name).read_text(encoding="utf-8"))
    branches = load("BRANCHES.json")["branches"]
    app = item_index.load(session / "WORKFLOW.json", session / "ITEMS.csv")
    documents = load("DOCUMENTS.json")
    extracted = {record["path"]: record for record in load("EXTRACTED.json")["documents"]}

    by_material, unplaced, unreadable = {}, [], []
    for document in documents:
        relative = document["relativePath"]
        branch = item_index.branch_for(relative, branches)
        if not branch:
            unplaced.append(relative)
            continue
        value, _ = item_index.identifier_for(relative, branch.get("identifier") or {})
        item, _, _ = app.resolve(branch["table"], value) if value else (None, None, None)
        if item is None:
            unplaced.append(relative)
            continue
        text = read_text(extracted.get(document["path"], {}))
        if not text:
            unreadable.append(relative)
            continue
        points, signals = score(text)
        if points < args.floor:
            continue
        entry = by_material.setdefault(item["identifier"], {
            "identifier": item["identifier"], "itemId": item["id"], "itemName": item["name"],
            "table": item["table"], "candidates": []})
        entry["candidates"].append({
            "sha": document["sha"], "fileName": document["name"], "relativePath": relative,
            "folder": document.get("folder", ""), "score": points, "signals": signals,
            "dates": dates_module.find(text, limit=12), "chars": len(text),
        })

    # One reading per content: the same certificate filed under two supplier folders is one document and
    # must not become two candidates an agent could answer differently.
    for entry in by_material.values():
        seen, unique = set(), []
        for candidate in sorted(entry["candidates"], key=lambda c: (-c["score"], c["fileName"])):
            if candidate["sha"] in seen:
                continue
            seen.add(candidate["sha"])
            unique.append(candidate)
        entry["candidates"] = unique[:args.shortlist]
        entry["folders"] = sorted({c["folder"] for c in unique if c["folder"]})

    out = {"materials": [by_material[key] for key in sorted(by_material)],
           "unplacedFiles": sorted(unplaced), "unreadableFiles": sorted(unreadable),
           "shortlist": args.shortlist, "floor": args.floor}
    (session / "CANDIDATES.json").write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                             encoding="utf-8")

    total = sum(len(m["candidates"]) for m in out["materials"])
    print(f"{len(out['materials'])} material(s) with a candidate, {total} candidate(s) shortlisted")
    empty = [m["identifier"] for m in out["materials"] if not m["candidates"]]
    if empty:
        print(f"  {len(empty)} material(s) shortlisted nothing: {', '.join(empty[:8])}")
    if unplaced:
        print(f"  {len(unplaced)} file(s) reach no live item - the branch rules, not this pass")
    if unreadable:
        print(f"  {len(unreadable)} file(s) had no text to score")
    print(f"\n-> {session / 'CANDIDATES.json'}")


if __name__ == "__main__":
    main()
