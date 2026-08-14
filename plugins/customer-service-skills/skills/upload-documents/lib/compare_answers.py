"""Set the answers that were read one at a time against each other, and report what contradicts.

Usage:
    python3 compare_answers.py <session_dir> [--min-quote 12]

Reads `CLASSIFICATIONS.json`; writes `CONTRADICTIONS.json` and prints what a person has to settle.

Every other check in this skill looks at one answer alone, which is why a line quoted from four hundred
documents resolving to three different templates was invisible. This one looks across them. Two
comparisons, because two things can be wrong:

- **one quote, several templates** — the same line was read off documents the run then filed differently.
  On the run this came from, 1,632 answers turned on eight quotations.
- **one evidence line, several documents** — one sentence written for a batch means one answer stood in
  for many. Weaker than it sounds, and deliberately reported apart from the first: measured against the
  grouping, identical evidence tracked documents that genuinely *were* the same form. Only reuse across
  **different forms** is worth a person's attention, and that was 110 answers where the raw count was 792.

Answers a *form* settled are skipped. There is one of those per form by construction, so they cannot
contradict each other, and a form's members all sharing an answer is the design rather than a defect.
What is left is what gets read one document at a time — split forms, dissolved forms, singletons, and
folders too small to group at all.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

WHITESPACE = re.compile(r"\s+")
QUOTE_FLOOR = 12
SAMPLE = 12


def folded(text):
    return WHITESPACE.sub(" ", (text or "").casefold()).strip()


def load(session_dir, name):
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def read_one_at_a_time(rows):
    """One entry per reading that an agent answered on its own, keyed by readingId.

    Copies are collapsed here for the same reason they are collapsed everywhere else: forty files
    sharing one content share one answer, and counting them forty times would make one disagreement
    look like forty.
    """
    seen = {}
    for row in rows:
        if row.get("viaForm") or not row.get("readingId"):
            continue
        if row.get("documentTemplate") is None and not row.get("proposedTemplate"):
            continue
        seen.setdefault(row["readingId"], row)
    return seen


def quote_collisions(readings, floor):
    """[(quote, {template: count}, [readingIds])] where one quotation resolved more than one way."""
    by_quote = defaultdict(lambda: defaultdict(list))
    for reading_id, row in readings.items():
        quote = folded(row.get("quote"))
        if len(quote) < floor:
            continue
        called = row.get("documentTemplate") or f"proposed: {row.get('proposedTemplate')}"
        by_quote[quote][called].append(reading_id)
    out = []
    for quote, by_template in by_quote.items():
        if len(by_template) > 1:
            out.append((quote, {name: len(ids) for name, ids in by_template.items()},
                        sorted(i for ids in by_template.values() for i in ids)))
    out.sort(key=lambda row: -sum(row[1].values()))
    return out


def evidence_reuse(readings, form_of):
    """[(evidence, [forms], [readingIds])] where one line was written for documents in different forms."""
    by_evidence = defaultdict(list)
    for reading_id, row in readings.items():
        line = folded(row.get("evidence"))
        if len(line) < QUOTE_FLOOR:
            continue
        by_evidence[line].append(reading_id)
    out = []
    for line, ids in by_evidence.items():
        forms = {form_of.get(i) for i in ids} - {None}
        if len(forms) > 1:
            out.append((line, sorted(forms), sorted(ids)))
    out.sort(key=lambda row: -len(row[2]))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--min-quote", type=int, default=QUOTE_FLOOR,
                        help=f"shortest quotation worth comparing (default: {QUOTE_FLOOR})")
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    rows = load(session_dir, "CLASSIFICATIONS.json").get("results") or []
    readings = read_one_at_a_time(rows)

    form_of = {}
    if (session_dir / "FORMS.json").is_file():
        forms = json.loads((session_dir / "FORMS.json").read_text(encoding="utf-8"))
        sha_to_form = {sha: form["id"] for form in forms.get("forms") or [] for sha in form["members"]}
        for reading_id, row in readings.items():
            form_of[reading_id] = sha_to_form.get(row.get("sha"))

    quotes = quote_collisions(readings, options.min_quote)
    reused = evidence_reuse(readings, form_of)

    written = {
        "readingsCompared": len(readings),
        "quoteCollisions": [
            {"quote": q, "templates": t, "readingIds": ids, "answers": sum(t.values())}
            for q, t, ids in quotes
        ],
        "evidenceReusedAcrossForms": [
            {"evidence": e, "forms": f, "readingIds": ids} for e, f, ids in reused
        ],
    }
    (session_dir / "CONTRADICTIONS.json").write_text(json.dumps(written, indent=2), encoding="utf-8")

    touched = sum(sum(t.values()) for _, t, _ in quotes)
    print(f"{len(readings)} reading(s) were answered one at a time and can be compared\n")
    if quotes:
        print(f"ONE QUOTATION, SEVERAL TEMPLATES ({len(quotes)} quotation(s), {touched} answer(s)):")
        for quote, templates, _ in quotes[:SAMPLE]:
            spread = " | ".join(f"{name} x{n}" for name, n in
                                sorted(templates.items(), key=lambda pair: -pair[1]))
            print(f"  {sum(templates.values()):5d}  {quote[:66]}")
            print(f"         {spread}")
        if len(quotes) > SAMPLE:
            print(f"  ... and {len(quotes) - SAMPLE} more in CONTRADICTIONS.json")
        print("  the same line was read off documents this run then filed differently — one of the two")
        print("  is wrong, and which one is a person's call\n")
    else:
        print("no quotation resolved to more than one template\n")

    if reused:
        print(f"ONE EVIDENCE LINE, DOCUMENTS IN DIFFERENT FORMS ({len(reused)}):")
        for line, forms, ids in reused[:SAMPLE]:
            print(f"  {len(ids):5d} reading(s) across {', '.join(forms)}  {line[:60]}")
        print("  one sentence written for documents printed on different stationery, which means one")
        print("  answer stood in for more than it saw")
    else:
        print("no evidence line was reused across forms")

    print(f"\n-> {session_dir / 'CONTRADICTIONS.json'}")


if __name__ == "__main__":
    main()
