"""Gather the compositions the sub agents read, and hold every value against the document.

Usage:
    python3 collect_compositions.py <session_dir>

Reads <session_dir>/READINGS.json and each answer under read/, and writes COMPOSITIONS.json - the run's
state, which the review page and the workbook are both built from.

Four checks before a composition counts, and a material that fails any of them carries no rows at all:

  the file named is one of the candidates that material was shown
  every row's quoted line is really in that file, on the five tiers of verbatim.py
  every CAS and EC number passes its own check digit and appears in that file
  the date the agent reported is printed in that file

The checks exist because the answers are plausible either way. A model asked for the CAS of glycerin
answers 56-81-5 whether or not the page says so, and a percentage invented to make a table sum to 100
reads exactly like one that was transcribed. Holding each value against the text is what separates them.

Blocking the whole material rather than the offending row is deliberate: a composition with one row
quietly dropped still looks like a composition, and sums close enough to 100 that nobody asks.

That severity has a cost, and the cost is silence. A reader facing a row it cannot quite carry learns
the cheapest safe move is to leave it out, and an answer with rows missing is indistinguishable from a
complete one. So it can hand the row back instead, in `withheld`, which reaches no figure and blocks
nothing - none of the checks above is relaxed to make room for it. `docs/adr/0013` is the argument, and
records what was tried and cut: counting the rows a page appears to hold flagged all eight verified
compositions on the run it was measured against.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import codes
import dates as dates_module
import verbatim
from signals import file_key, read_text

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def number(value):
    """A percentage as written by the agent, or None where it is not a number.

    `Balance` and `to 100%` arrive here as words. They are a real thing a document says and a real thing
    a person needs to see, so they are carried as an absent figure rather than converted into one - the
    complement of the other rows is arithmetic this run did not read anywhere.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".").replace("%", "").replace("≥", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def date_is_printed(written, in_document, shapes):
    """Whether the date the agent reported is one this document prints.

    On the words first, then on the date they resolve to: an agent reading `2022-12-08` off the page and
    writing `8 December 2022` has reported the document's own date, and a check that compares strings
    calls that a fabrication and throws away the whole composition.
    """
    if verbatim.check(written, shapes) != "ABSENT":
        return True
    resolved = dates_module.as_iso(written)
    return bool(resolved) and resolved in {entry["iso"] for entry in in_document if entry["iso"]}


def withheld_from(answer, shapes):
    """The rows the reader saw and could not carry, each held against the document but never refused.

    A withheld row carries no value anywhere: not to the composition, not to the workbook's figures.
    So nothing it says can be wrong in the way a carried row can, and refusing one would only teach a
    reader to go back to saying nothing - which is the silence this exists to break.

    The line it names is still checked, and the answer recorded rather than acted on. A reader
    inventing rows it claims it could not carry should be exactly as visible as one inventing rows it
    did.
    """
    out = []
    said = answer.get("withheld")
    # A shape check, because this field is new and a reader will get it wrong. Every other malformed
    # answer costs one material; iterating a dict here would hand `raw.get` a string and take the whole
    # collection down with it.
    if not isinstance(said, list):
        return out
    for raw in said:
        if not isinstance(raw, dict):
            continue
        printed = (raw.get("asPrinted") or "").strip()
        out.append({
            "ingredient": (raw.get("ingredient") or "").strip(),
            "asPrinted": printed,
            "why": (raw.get("why") or "").strip(),
            "inDocument": bool(printed) and verbatim.check(printed, shapes) != "ABSENT",
        })
    return out


def verify(rows, shapes):
    """Every row the agent returned, tagged with how its quotation held up, and what went wrong."""
    checked, failures = [], []
    for raw in rows or []:
        name = (raw.get("ingredient") or "").strip()
        quote = (raw.get("quote") or "").strip()
        tier = verbatim.check(quote, shapes)
        cas = (raw.get("cas") or "").strip()
        ec = (raw.get("ec") or "").strip()
        if tier == "ABSENT":
            failures.append(f"{name!r}: the quoted line is not in the document")
        # Asked of every code in the cell rather than of the cell. A fragrance prints the isomers it
        # may contain against one name, so `5989-27-5; 138-86-3; 7705-14-8` is the document being
        # precise - and asking `cas_ok` of the whole string called it a mistyped number and blocked
        # the material over it. Each number still has to pass, and still has to be on the page.
        for kind, value in (("CAS", cas), ("EC", ec)):
            if not value:
                continue
            if not codes.cell_ok(value, kind.lower()):
                failures.append(f"{name!r}: {kind} {value} fails its check digit")
                continue
            # Every code in the cell, of either kind. A cell reading `5989-27-5 / EC 231-791-2` puts
            # two numbers on the sheet and the column's own kind answers for one of them.
            missing = [code for _, code in codes.everything_in(value)
                       if verbatim.check(code, shapes) == "ABSENT"]
            if missing:
                failures.append(f"{name!r}: {kind} {', '.join(missing)} is not printed in the document")
        checked.append({
            "ingredient": name, "cas": cas, "ec": ec,
            "min": number(raw.get("min")), "max": number(raw.get("max")),
            "quote": quote, "quoteTier": tier,
        })
    if not checked:
        failures.append("the answer carries no rows")
    return checked, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    args = parser.parse_args()
    session = args.session_dir

    manifest = load(session / "READINGS.json")
    candidates = {m["identifier"]: m for m in load(session / "CANDIDATES.json")["materials"]}
    extracted = {file_key(record["path"]): record
                 for record in load(session / "EXTRACTED.json")["documents"]}
    by_sha = {}
    for document in load(session / "DOCUMENTS.json"):
        by_sha.setdefault(document["sha"], document)

    materials, issues, unanswered = [], [], []
    # A material the shortlist pass found nothing for never gets a task, so it would otherwise reach
    # neither the page nor the workbook. ADR-0009 promises those are reported by name.
    for entry in manifest.get("noCandidates") or []:
        sheets = entry.get("sheetsOnly") or []
        if sheets:
            # Distinct from an empty folder, and the user acts on it differently: the supplier has
            # been asked for a sheet and never for a composition, so there is somebody to ask.
            why = (f"the only documents here are safety data sheets ({len(sheets)} of them), which "
                   "state hazards rather than the whole composition")
        else:
            why = ("no file under this material reads like a composition "
                   f"({entry.get('filesSeen', 0)} file(s) looked at)")
        issues.append({"identifier": entry["identifier"], "candidates": [],
                       "safetyDataSheets": sheets, "why": why})
    for task in manifest["tasks"]:
        identifier = task["identifier"]
        answer_path = Path(task["output"])
        shown = {c["sha"]: c for c in candidates.get(identifier, {}).get("candidates", [])}
        names = [c["fileName"] for c in shown.values()]
        # A recut can record that no file in the folder states this composition. That is a decision a
        # person made, and it reaches the issues in their words rather than as a missing answer.
        recut = (load(task["input"]) if Path(task["input"]).is_file() else {}).get("recut") or {}
        if recut.get("sourceFile", "") is None:
            issues.append({"identifier": identifier, "candidates": names,
                           "why": recut.get("why") or "recorded as having no composition document"})
            continue
        if not answer_path.is_file():
            unanswered.append(identifier)
            issues.append({"identifier": identifier, "why": "no sub agent answered for this material",
                           "candidates": names})
            continue
        try:
            answer = load(answer_path)
        except json.JSONDecodeError as error:
            issues.append({"identifier": identifier, "why": f"the answer is not readable JSON: {error}",
                           "candidates": names})
            continue

        said = (answer.get("identifier") or "").strip()
        if said and said != identifier:
            issues.append({"identifier": identifier, "candidates": names,
                           "why": f"the answer is filed under {said!r}, so it is another material's"})
            continue
        chosen = shown.get((answer.get("sourceSha") or "").strip())
        if not answer.get("sourceSha"):
            issues.append({"identifier": identifier, "candidates": names,
                           "why": (answer.get("why") or "").strip()
                                  or "no file in the shortlist states a composition"})
            continue
        if chosen is None:
            issues.append({"identifier": identifier, "candidates": names,
                           "why": "names a file that was not on its shortlist: "
                                  f"{answer.get('sourceFile') or answer['sourceSha']}"})
            continue

        text = read_text(extracted.get(file_key(by_sha.get(chosen["sha"], {}).get("path")), {}))
        shapes = verbatim.forms(text)
        rows, failures = verify(answer.get("rows"), shapes)
        withheld = withheld_from(answer, shapes)

        printed = answer.get("documentDate") or {}
        written = (printed.get("written") or "").strip()
        in_document = dates_module.find(text)
        if not written:
            # Plenty of composition statements carry no date at all. Demanding one of those threw away
            # a reading whose every figure and every quotation was right.
            if in_document:
                failures.append("the document prints a date and the answer reported none")
        elif not date_is_printed(written, in_document, shapes):
            failures.append(f"the date {written!r} is not printed in the document")

        if failures:
            issues.append({"identifier": identifier, "why": "; ".join(failures),
                           "sourceFile": chosen["fileName"], "candidates": names})
            continue

        rejected = {r.get("fileName"): (r.get("why") or "").strip()
                    for r in answer.get("rejected") or []}
        materials.append({
            "identifier": identifier, "itemId": candidates[identifier]["itemId"],
            "itemName": candidates[identifier]["itemName"], "table": candidates[identifier]["table"],
            "sourceFile": chosen["fileName"], "sourceSha": chosen["sha"],
            "sourcePath": chosen["relativePath"], "sourceFolder": chosen["folder"],
            "sourceFolders": candidates[identifier].get("folders", []),
            "documentDate": printed, "why": (answer.get("why") or "").strip(),
            # The sheets sit here too, though no agent ever weighed them. A person looking at this
            # material wants to know the folder held six documents and why four of them were never
            # in the running, and their absence would read as the run not having seen them.
            "considered": [{"fileName": c["fileName"], "sha": c["sha"], "folder": c["folder"],
                            "chosen": c["sha"] == chosen["sha"],
                            "why": rejected.get(c["fileName"], ""),
                            "dates": c.get("dates") or []}
                           for c in shown.values()]
                          + [{"fileName": s["fileName"], "sha": s["sha"], "folder": s["folder"],
                              "chosen": False,
                              "why": "a safety data sheet - states hazards, not the whole composition",
                              "dates": s.get("dates") or []}
                             for s in candidates[identifier].get("sheets") or []],
            "rows": rows,
            "withheld": withheld,
        })

    # One content cannot be two compositions. Materials are read one at a time, so the same document
    # chosen by two of them is the one way two answers can disagree about one page.
    seen, contradictions, blocked = {}, [], set()
    for material in materials:
        signature = tuple((r["ingredient"].casefold(), r["min"], r["max"]) for r in material["rows"])
        first = seen.setdefault(material["sourceSha"], (material["identifier"], signature))
        if first[1] != signature:
            contradictions.append({"sha": material["sourceSha"], "sourceFile": material["sourceFile"],
                                   "materials": [first[0], material["identifier"]]})
            blocked.update({first[0], material["identifier"]})
    for identifier in sorted(blocked):
        material = next(m for m in materials if m["identifier"] == identifier)
        others = sorted({m["identifier"] for m in materials
                         if m["sourceSha"] == material["sourceSha"]} - {identifier})
        issues.append({"identifier": identifier, "sourceFile": material["sourceFile"],
                       "candidates": [c["fileName"] for c in material["considered"]],
                       "why": f"{material['sourceFile']} was read differently for "
                              f"{', '.join(others)} - one document cannot be two compositions"})
    materials = [m for m in materials if m["identifier"] not in blocked]

    out = {"materials": materials, "issues": issues, "contradictions": contradictions,
           "unanswered": unanswered}
    (session / "COMPOSITIONS.json").write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                               encoding="utf-8")

    tiers = Counter(r["quoteTier"] for m in materials for r in m["rows"])
    print(f"{len(materials)} material(s) with a verified composition, "
          f"{sum(len(m['rows']) for m in materials)} row(s)")
    print("  quoted lines: " + ", ".join(f"{tiers.get(t, 0)} {t}" for t in verbatim.TIERS))
    if issues:
        never = sum(1 for i in issues if not i.get("candidates"))
        print(f"  {len(issues)} material(s) carry no composition - {never} had no candidate file at "
              f"all, {len(issues) - never} were read and did not survive:")
        for issue in issues[:10]:
            if issue.get("candidates"):
                print(f"    {issue['identifier']}: {issue['why'][:110]}")
    if contradictions:
        print(f"  {len(contradictions)} document(s) read two different ways by two materials")
    print(f"\n-> {session / 'COMPOSITIONS.json'}")


if __name__ == "__main__":
    main()
