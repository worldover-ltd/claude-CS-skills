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
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import codes
import verbatim
from score_composition import read_text


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


def verify(rows, text, shapes):
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
        if cas and not codes.cas_ok(cas):
            failures.append(f"{name!r}: CAS {cas} fails its check digit")
        elif cas and cas not in text:
            failures.append(f"{name!r}: CAS {cas} is not printed in the document")
        if ec and not codes.ec_ok(ec):
            failures.append(f"{name!r}: EC {ec} fails its check digit")
        elif ec and ec not in text:
            failures.append(f"{name!r}: EC {ec} is not printed in the document")
        checked.append({
            "ingredient": name, "cas": cas, "ec": ec,
            "min": number(raw.get("min")), "max": number(raw.get("max")),
            "statedAs": (raw.get("statedAs") or "").strip(), "quote": quote, "quoteTier": tier,
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
    extracted = {record["path"]: record for record in load(session / "EXTRACTED.json")["documents"]}
    by_sha = {}
    for document in load(session / "DOCUMENTS.json"):
        by_sha.setdefault(document["sha"], document)

    materials, issues, unanswered = [], [], []
    for task in manifest["tasks"]:
        identifier = task["identifier"]
        answer_path = Path(task["output"])
        shown = {c["sha"]: c for c in candidates.get(identifier, {}).get("candidates", [])}
        names = [c["fileName"] for c in shown.values()]
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

        text = read_text(extracted.get(by_sha.get(chosen["sha"], {}).get("path"), {}))
        rows, failures = verify(answer.get("rows"), text, verbatim.forms(text))

        printed = answer.get("documentDate") or {}
        written = (printed.get("written") or "").strip()
        if written and written not in text:
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
            "considered": [{"fileName": c["fileName"], "sha": c["sha"], "folder": c["folder"],
                            "chosen": c["sha"] == chosen["sha"],
                            "why": rejected.get(c["fileName"], "")}
                           for c in shown.values()],
            "rows": rows,
        })

    # One content cannot be two compositions. Materials are read one at a time, so the same document
    # chosen by two of them is the one way two answers can disagree about one page.
    seen, contradictions = {}, []
    for material in materials:
        signature = tuple((r["ingredient"].casefold(), r["min"], r["max"]) for r in material["rows"])
        first = seen.setdefault(material["sourceSha"], (material["identifier"], signature))
        if first[1] != signature:
            contradictions.append({"sha": material["sourceSha"], "sourceFile": material["sourceFile"],
                                   "materials": [first[0], material["identifier"]]})

    out = {"materials": materials, "issues": issues, "contradictions": contradictions,
           "unanswered": unanswered}
    (session / "COMPOSITIONS.json").write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                               encoding="utf-8")

    tiers = Counter(r["quoteTier"] for m in materials for r in m["rows"])
    print(f"{len(materials)} material(s) with a verified composition, "
          f"{sum(len(m['rows']) for m in materials)} row(s)")
    print("  quoted lines: " + ", ".join(f"{tiers.get(t, 0)} {t}" for t in verbatim.TIERS))
    if issues:
        print(f"  {len(issues)} material(s) carry no composition:")
        for issue in issues[:10]:
            print(f"    {issue['identifier']}: {issue['why'][:110]}")
    if contradictions:
        print(f"  {len(contradictions)} document(s) read two different ways by two materials")
    print(f"\n-> {session / 'COMPOSITIONS.json'}")


if __name__ == "__main__":
    main()
