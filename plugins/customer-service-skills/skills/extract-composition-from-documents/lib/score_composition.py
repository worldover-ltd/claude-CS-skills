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

A safety data sheet is the one exception, and it is culled hard. Its section 3 is a hazard disclosure:
under CLP it names the substances classified above their cut-off, so a sheet can be complete and
correct and still omit the water and every other ingredient that carries no classification. The scoring
above cannot tell that from a composition - `\\bsection\\s*3\\b` and `information on ingredients` are
literally the sheet's own headings, so it scores highest of anything in the folder. On this customer's
files there are 4,342 sheets against 680 composition statements, and 2,010 of 2,962 materials have a
sheet and no statement, so the shortlist fills with them and the answers look complete.

Left out as a source, kept as a register: the sheets are recorded per material and their CAS and EC
numbers travel to the reader as reference, because the regulation makes a sheet print an identifier
against every substance it names.
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
from signals import BALANCE, HEADING, INCI, PERCENT, file_key, looks_like_sds, read_text

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
    extracted = {file_key(record["path"]): record for record in load("EXTRACTED.json")["documents"]}

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
        entry = by_material.setdefault(item["identifier"], {
            "identifier": item["identifier"], "itemId": item["id"], "itemName": item["name"],
            "table": item["table"], "candidates": [], "sheets": [], "filesSeen": 0})
        entry["filesSeen"] += 1
        text = read_text(extracted.get(file_key(document["path"]), {}))
        if not text:
            unreadable.append(relative)
            continue
        if looks_like_sds(text, document["name"]):
            # Never a candidate, never dropped either. Its codes go to the reader as reference, and a
            # material whose folder holds nothing else is owed that reason by name rather than the
            # bare "no file reads like a composition" every other empty folder gets.
            entry["sheets"].append({
                "sha": document["sha"], "fileName": document["name"], "relativePath": relative,
                "folder": document.get("folder", ""), "dates": dates_module.find(text, limit=12),
            })
            continue
        points, signals = score(text)
        if points < args.floor:
            continue
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
        seen, sheets = set(), []
        for sheet in sorted(entry["sheets"], key=lambda s: s["fileName"]):
            if sheet["sha"] not in seen:
                seen.add(sheet["sha"])
                sheets.append(sheet)
        entry["sheets"] = sheets
        entry["folders"] = sorted({c["folder"] for c in unique + sheets if c["folder"]})

    out = {"materials": [by_material[key] for key in sorted(by_material)],
           "unplacedFiles": sorted(unplaced), "unreadableFiles": sorted(unreadable),
           "shortlist": args.shortlist, "floor": args.floor}
    (session / "CANDIDATES.json").write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                             encoding="utf-8")

    total = sum(len(m["candidates"]) for m in out["materials"])
    print(f"{len(out['materials'])} material(s) with a candidate, {total} candidate(s) shortlisted")
    empty = [m["identifier"] for m in out["materials"] if not m["candidates"]]
    if empty:
        print(f"  {len(empty)} material(s) have files but none reads like a composition: "
              f"{', '.join(empty[:8])}{' ...' if len(empty) > 8 else ''}")
    sheets = sum(len(m["sheets"]) for m in out["materials"])
    sheet_only = [m["identifier"] for m in out["materials"] if m["sheets"] and not m["candidates"]]
    if sheets:
        print(f"  {sheets} safety data sheet(s) left out as a source, their codes kept as reference")
    if sheet_only:
        print(f"  {len(sheet_only)} material(s) have nothing but safety data sheets: "
              f"{', '.join(sheet_only[:8])}{' ...' if len(sheet_only) > 8 else ''}")
    if unplaced:
        print(f"  {len(unplaced)} file(s) reach no live item - the branch rules, not this pass")
    if unreadable:
        print(f"  {len(unreadable)} file(s) had no text to score")
    print(f"\n-> {session / 'CANDIDATES.json'}")


if __name__ == "__main__":
    main()
