"""Ask, once, where each kind of document belongs on each kind of item's Documents tab.

Usage:
    python3 plan_sections.py <session_dir>

Reads `CLASSIFICATIONS.json` and `WORKFLOW.json`; writes `sections/task.json` — one task, holding every
distinct **(document template, item template)** pair the run produced and the sections each item template
already has — and `SECTION_PLAN.json` naming it.

No file is opened and no extracted text is read. The whole question is answerable from the rows the run
has already written, which is why it runs last and costs almost nothing: on the folder this came from,
2,163 rows reduce to 58 pairs.

Do not mistake this for classification. The classifier is never asked about sections, not even to propose
one — see docs/adr/0002. This is a separate pass over data, and the reason it exists is that the answer
turned out to be mostly *new* sections rather than a lookup: on that same folder the app held five
sections across three item templates, and 68 of 82 template rows had no section at all. Arranging a
customer's Documents tab is a layout decision, so what comes back is marked `is_new` on the workbook's
own sheets and read there by the person whose app it is.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import item_index  # noqa: E402

SAMPLE = 12


def load(session_dir, name):
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def pairs_in(rows):
    """{(templateId, templateName, itemTemplate, table): documents} over what the run actually produced."""
    counted = Counter()
    for row in rows:
        template_id = row.get("documentTemplateId")
        item_template = row.get("itemTemplate")
        if not template_id or not item_template:
            continue
        counted[(template_id, row.get("documentTemplate"), item_template, row.get("table"))] += 1
    return counted


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    rows = load(session_dir, "CLASSIFICATIONS.json").get("results") or []
    try:
        app = item_index.load(session_dir / "WORKFLOW.json", session_dir / "ITEMS.csv")
    except item_index.ExportError as error:
        raise SystemExit(f"the export cannot be used: {error}")

    counted = pairs_in(rows)
    if not counted:
        raise SystemExit("no row carries both a document template and an item template — nothing to arrange")

    existing = {}
    for name, template in sorted(app.item_templates.items()):
        existing[name] = [{"label": section["label"], "sortOrder": section["sortOrder"],
                           "holdsTemplateIds": section["documentTemplates"]}
                          for section in template["sections"]]

    pairs = []
    for (template_id, template_name, item_template, table), documents in sorted(
            counted.items(), key=lambda pair: (-pair[1], pair[0][2], pair[0][1] or "")):
        holders = [s["label"] for s in existing.get(item_template, [])
                   if template_id in s["holdsTemplateIds"]]
        pairs.append({
            "documentTemplateId": template_id,
            "documentTemplate": template_name,
            "itemTemplate": item_template,
            "table": table,
            "documents": documents,
            # Where the app already arranges this template, the answer is a lookup and the agent should
            # say so rather than inventing a second home for it.
            "alreadyIn": holders[0] if holders else None,
        })

    task_dir = session_dir / "sections"
    task_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "sectioned").mkdir(parents=True, exist_ok=True)
    input_path = task_dir / "task.json"
    input_path.write_text(json.dumps(
        {"itemTemplates": existing, "pairs": pairs}, indent=2), encoding="utf-8")

    output_path = session_dir / "sectioned" / "task.json"
    (session_dir / "SECTION_PLAN.json").write_text(json.dumps({
        "pairs": len(pairs),
        "documents": sum(p["documents"] for p in pairs),
        "alreadyArranged": sum(1 for p in pairs if p["alreadyIn"]),
        "input": str(input_path.resolve()).replace("\\", "/"),
        "output": str(output_path.resolve()).replace("\\", "/"),
    }, indent=2), encoding="utf-8")

    arranged = sum(1 for p in pairs if p["alreadyIn"])
    print(f"{len(pairs)} pair(s) of document template and item template, "
          f"standing for {sum(p['documents'] for p in pairs)} document(s)")
    print(f"  {arranged} already have a section in the app; {len(pairs) - arranged} do not\n")
    for pair in pairs[:SAMPLE]:
        where = pair["alreadyIn"] or "-- no section holds it --"
        print(f"  {pair['documents']:5d}  {(pair['documentTemplate'] or '?')[:34]:34s} "
              f"on {pair['itemTemplate'][:22]:22s} {where}")
    if len(pairs) > SAMPLE:
        print(f"  ... and {len(pairs) - SAMPLE} more in sections/task.json")
    print(f"\n-> {session_dir / 'SECTION_PLAN.json'}")


if __name__ == "__main__":
    main()
