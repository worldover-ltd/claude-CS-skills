"""Join the classifiers' answers back onto the batched documents, and run the roll call in code.

Usage:
    python3 collect_classifications.py <session_dir> [--floor 0.7]

Reads <session_dir>/BATCHES.json — the authority on which documents were sent — every
<session_dir>/classified/batch_NNN.json a sub agent wrote, and WORKFLOW.json for what the app allows.

Writes <session_dir>/CLASSIFICATIONS.json: one entry per batched document, carrying its item, sha,
document template with the app's own id, section, confidence and evidence. Prints the roll call, the
confidence spread, and every document a person still has to settle.

An answer naming a template the app does not have, or one the app does not allow on that table, is
rejected here rather than carried into the workbook.
"""

import argparse
import json
import sys
from pathlib import Path

import item_index

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

    try:
        app = item_index.load(session_dir / "WORKFLOW.json", session_dir / "ITEMS.csv")
    except item_index.ExportError as error:
        raise SystemExit(f"the export cannot be used: {error}")

    allowed_by_table = {table: {t["id"] for t in app.templates_for(table)} for table in app.tables}
    sections_by_item_template = {
        name: [s["label"] for s in entry["sections"]] for name, entry in app.item_templates.items()
    }
    # Which templates each section actually holds. A table allows a template; a section renders it, and
    # the two are not the same list — a template can be allowed on the table and arranged on no section
    # of the item template an item happens to be on.
    section_holds = {
        (name, s["label"]): set(s["documentTemplates"])
        for name, entry in app.item_templates.items()
        for s in entry["sections"]
    }
    arranged_on = {
        name: {i for s in entry["sections"] for i in s["documentTemplates"]}
        for name, entry in app.item_templates.items()
    }

    answers, silent = read_answers(session_dir, entries)

    results, unanswered, no_template, low, rejected, bad_section, unarranged = [], [], [], [], [], [], []
    proposed_templates, proposed_sections = {}, {}
    listed_paths = set()
    for document in documents:
        answer = answers.get(document["path"])
        entry = {
            **{
                k: document[k]
                for k in (
                    "path", "relativePath", "name", "sha",
                    "table", "identifier", "itemId", "itemName", "itemTemplate",
                )
            },
            "documentTemplate": None,
            "documentTemplateId": None,
            "proposedTemplate": None,
            "section": None,
            "proposedSection": None,
            "confidence": None,
            "evidence": None,
            "review": None,
        }

        if answer is None:
            entry["review"] = "unread — no classifier answered for this document"
            listed_paths.add(document["relativePath"])
            unanswered.append(document["relativePath"])
            results.append(entry)
            continue

        entry["evidence"] = (answer.get("evidence") or "").strip() or None
        entry["confidence"] = confidence_of(answer.get("confidence"))

        template_id = item_index.normalise(answer.get("documentTemplateId"))
        proposed_template = item_index.normalise(answer.get("proposedTemplate"))
        known = app.document_templates.get(template_id)
        allowed = allowed_by_table.get(document["table"], set())
        if template_id and not known:
            entry["review"] = f"template id {template_id!r} is not in the app's list"
            listed_paths.add(document["relativePath"])
            rejected.append(f"{document['relativePath']} — proposed id {template_id!r}")
        elif template_id and template_id not in allowed:
            entry["review"] = f"template {known['name']!r} is not allowed on {document['table']}"
            listed_paths.add(document["relativePath"])
            rejected.append(f"{document['relativePath']} — {known['name']!r} is not for {document['table']}")
        elif template_id:
            entry["documentTemplateId"] = template_id
            entry["documentTemplate"] = known["name"]
        elif proposed_template:
            # A read the app has no word for yet. The reading is kept and the name goes to the user,
            # since creating the template is the action that makes this document attachable.
            entry["proposedTemplate"] = proposed_template
            entry["review"] = f"proposes a template the app does not have: {proposed_template!r}"
            listed_paths.add(document["relativePath"])
            proposed_templates.setdefault(proposed_template, []).append(document["relativePath"])
        else:
            entry["review"] = "no template fitted what the classifier read"
            listed_paths.add(document["relativePath"])
            no_template.append(f"{document['relativePath']} — {entry['evidence'] or 'no evidence given'}")

        section = item_index.normalise(answer.get("section"))
        blueprint = document["itemTemplate"] or ""
        where = blueprint or "no item template"
        on_template = sections_by_item_template.get(blueprint, [])
        chosen = entry["documentTemplateId"]
        if section and section not in on_template:
            note = f"section {section!r} is not on {where}"
            entry["review"] = f"{entry['review']} | {note}" if entry["review"] else note
            listed_paths.add(document["relativePath"])
            bad_section.append(f"{document['relativePath']} — {section!r} is not a section on {where}")
        elif section and chosen and chosen not in section_holds.get((blueprint, section), set()):
            # The app allows this template on the table but renders it nowhere on this blueprint, so the
            # attachment lands with no home on the item's page until somebody arranges one.
            if chosen not in arranged_on.get(blueprint, set()):
                note = f"{entry['documentTemplate']!r} sits in no section on {where}"
            else:
                note = f"section {section!r} on {where} does not hold {entry['documentTemplate']!r}"
            entry["section"] = section
            entry["review"] = f"{entry['review']} | {note}" if entry["review"] else note
            listed_paths.add(document["relativePath"])
            unarranged.append(f"{document['relativePath']} — {note}")
        elif section:
            entry["section"] = section

        proposed_section = item_index.normalise(answer.get("proposedSection"))
        if not entry["section"] and proposed_section:
            entry["proposedSection"] = proposed_section
            note = f"proposes a section {where} does not have: {proposed_section!r}"
            entry["review"] = f"{entry['review']} | {note}" if entry["review"] else note
            listed_paths.add(document["relativePath"])
            proposed_sections.setdefault((blueprint, proposed_section), []).append(document["relativePath"])

        if entry["documentTemplate"] and (entry["confidence"] is None or entry["confidence"] < options.floor):
            shown = "unscored" if entry["confidence"] is None else f"{entry['confidence']:.2f}"
            entry["review"] = entry["review"] or f"confidence {shown}, below the {options.floor:.2f} floor"
            listed_paths.add(document["relativePath"])
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
            "proposedTemplates": {n: len(p) for n, p in sorted(proposed_templates.items())},
            "proposedSections": {f"{b}:{l}": len(p) for (b, l), p in sorted(proposed_sections.items())},
            "sectionsByItemTemplate": sections_by_item_template,
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
    report("TEMPLATE THE APP CANNOT TAKE — wrong id, or not allowed on that table", rejected)
    report("SECTION NOT ON THAT ITEM TEMPLATE — pick one the item template lists", bad_section)
    report("NO SECTION RENDERS IT — the app allows the template but arranges it nowhere here", unarranged)
    report(
        "TEMPLATES TO CREATE — proposed because nothing in the app fitted",
        [f"{name!r} — {len(paths)} document(s), e.g. {paths[0]}" for name, paths in sorted(proposed_templates.items())],
    )
    report(
        "SECTIONS TO CREATE — proposed because nothing on that item template fitted",
        [f"{label!r} on {bp or 'no item template'} — {len(paths)} document(s)" for (bp, label), paths in sorted(proposed_sections.items())],
    )
    report(f"BELOW THE {options.floor:.2f} FLOOR — classified on thin evidence, worth spot-checking", low)

    # Every document is either usable or listed above — a gap here means a review reason nothing
    # reports. Counted over distinct documents, since one can fail on its template and its section both.
    needing = {r["relativePath"] for r in results if r["review"]}
    silent_failures = sorted(needing - listed_paths)
    if silent_failures:
        print(
            f"\nACCOUNTING GAP: {len(silent_failures)} document(s) carry a review reason nothing above "
            f"reports — read `review` in CLASSIFICATIONS.json: {', '.join(silent_failures[:SAMPLE])}"
        )

    print(f"\n-> {session_dir / 'CLASSIFICATIONS.json'}")


if __name__ == "__main__":
    main()
