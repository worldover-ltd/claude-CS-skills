"""Join the classifiers' answers back onto the batched documents, and run the roll call in code.

Usage:
    python3 collect_classifications.py <session_dir> [--floor 0.7]

Reads <session_dir>/BATCHES.json — the authority on which documents were sent — and every
<session_dir>/classified/batch_NNN.json a sub agent wrote.

Writes <session_dir>/CLASSIFICATIONS.json: one entry per batched document, carrying its identifier, sha,
document template, section, confidence and evidence. Prints the roll call, the confidence spread, and every
document a person still has to settle.

An answer naming a template or section outside the vocabulary is rejected here rather than carried into the
workbook, because the migration can only land on names the app already has.
"""

import argparse
import json
import sys
from pathlib import Path

SAMPLE = 10
BUCKETS = ((0.9, "0.9-1.0  named itself"), (0.7, "0.7-0.9  clear from contents"), (0.5, "0.5-0.7  inferred"))


def load(path, what):
    if not path.is_file():
        raise SystemExit(f"missing {what}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_answers(session_dir, entries):
    """(answers keyed by path, batch numbers that did not answer)."""
    answers, silent = {}, []
    for entry in entries:
        output = Path(entry["output"])
        if not output.is_file():
            silent.append(entry["batch"])
            continue
        try:
            results = json.loads(output.read_text(encoding="utf-8")).get("results") or []
        except json.JSONDecodeError as error:
            print(f"  batch {entry['batch']}: unreadable output ({error})")
            silent.append(entry["batch"])
            continue
        wanted = set(entry["paths"])
        kept = [r for r in results if isinstance(r, dict) and r.get("path") in wanted]
        for result in kept:
            answers.setdefault(result["path"], result)
        if len(kept) < len(wanted):
            silent.append(entry["batch"])
    return answers, silent


def confidence_of(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def report(heading, rows):
    if not rows:
        return
    print(f"\n{heading} ({len(rows)}):")
    for row in rows[:SAMPLE]:
        print(f"  {row}")
    if len(rows) > SAMPLE:
        print(f"  ... and {len(rows) - SAMPLE} more in CLASSIFICATIONS.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--floor", type=float, default=0.7, help="confidence below this needs review (default: 0.7)")
    options = parser.parse_args()

    # Windows consoles default to a codepage that cannot print this summary's punctuation.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    manifest = load(session_dir / "BATCHES.json", "BATCHES.json")
    documents = manifest.get("documents") or []
    entries = manifest.get("batches") or []
    vocabulary = load(session_dir / "APP_TEMPLATES.json", "APP_TEMPLATES.json")
    known_templates = set(vocabulary.get("documentTemplates") or [])
    sections_by_entity = {
        e["name"]: [s.get("label") for s in e.get("sections") or []]
        for e in vocabulary.get("entityTemplates") or []
        if e.get("name")
    }

    answers, silent = read_answers(session_dir, entries)

    results, unanswered, no_template, low, rejected, bad_section = [], [], [], [], [], []
    for document in documents:
        answer = answers.get(document["path"])
        entry = {
            **{k: document[k] for k in ("path", "relativePath", "name", "sha", "entity", "identifier")},
            "documentTemplate": None,
            "section": None,
            "confidence": None,
            "evidence": None,
            "review": None,
        }

        if answer is None:
            entry["review"] = "unread — no classifier answered for this document"
            unanswered.append(document["relativePath"])
            results.append(entry)
            continue

        entry["evidence"] = (answer.get("evidence") or "").strip() or None
        entry["confidence"] = confidence_of(answer.get("confidence"))

        template = answer.get("documentTemplate")
        if template and template not in known_templates:
            entry["review"] = f"template {template!r} is not in the app's list"
            rejected.append(f"{document['relativePath']} — proposed {template!r}")
        elif template:
            entry["documentTemplate"] = template
        else:
            entry["review"] = "no template fitted what the classifier read"
            no_template.append(f"{document['relativePath']} — {entry['evidence'] or 'no evidence given'}")

        section = answer.get("section")
        allowed = set(sections_by_entity.get(document["entity"]) or [])
        if section and section in allowed:
            entry["section"] = section
        elif section:
            note = f"section {section!r} is not on {document['entity']}"
            entry["review"] = f"{entry['review']} | {note}" if entry["review"] else note
            bad_section.append(f"{document['relativePath']} — {section!r} is not a section on {document['entity']}")

        if entry["documentTemplate"] and (entry["confidence"] is None or entry["confidence"] < options.floor):
            shown = "unscored" if entry["confidence"] is None else f"{entry['confidence']:.2f}"
            entry["review"] = entry["review"] or f"confidence {shown}, below the {options.floor:.2f} floor"
            low.append(f"{document['relativePath']} — {shown} — {entry['evidence'] or 'no evidence given'}")

        results.append(entry)

    usable = [r for r in results if r["documentTemplate"] and not r["review"]]
    (session_dir / "CLASSIFICATIONS.json").write_text(
        json.dumps({
            "floor": options.floor,
            "counts": {
                "expected": len(documents),
                "answered": len(documents) - len(unanswered),
                "usable": len(usable),
                "needsReview": len(results) - len(usable),
            },
            "silentBatches": silent,
            "sectionsByEntity": sections_by_entity,
            "results": results,
        }, indent=2),
        encoding="utf-8",
    )

    print(f"{len(documents) - len(unanswered)}/{len(documents)} documents answered, {len(usable)} usable as-is")
    if silent:
        print(f"\nSEND THESE BATCHES AGAIN ({len(silent)}): " + ", ".join(str(b) for b in sorted(set(silent))))

    scored = [r["confidence"] for r in results if r["confidence"] is not None]
    if scored:
        print("\nconfidence:")
        remaining = sorted(scored, reverse=True)
        for edge, label in BUCKETS:
            count = len([c for c in remaining if c >= edge])
            print(f"  {label}: {count}")
            remaining = [c for c in remaining if c < edge]
        print(f"  below 0.5 a guess:      {len(remaining)}")

    report("UNREAD — no classifier answered, so these are not classified", unanswered)
    report("NO TEMPLATE — nothing in the app's list fitted", no_template)
    report("TEMPLATE NOT IN THE APP — somebody has to create it first", rejected)
    report("SECTION NOT ON THAT ENTITY — pick one the entity template lists", bad_section)
    report(f"BELOW THE {options.floor:.2f} FLOOR — classified on thin evidence, worth spot-checking", low)

    # Every document is either usable or listed above — a gap here means a review reason nothing reports.
    listed = len(unanswered) + len(no_template) + len(rejected) + len(bad_section) + len(low)
    if len(usable) + listed != len(documents):
        print(
            f"\nACCOUNTING GAP: {len(documents)} documents, {len(usable)} usable, {listed} listed — "
            "read the `review` field in CLASSIFICATIONS.json for the rest"
        )

    print(f"\n-> {session_dir / 'CLASSIFICATIONS.json'}")


if __name__ == "__main__":
    main()
