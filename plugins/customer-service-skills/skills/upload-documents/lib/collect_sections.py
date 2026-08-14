"""Take the section answer back, check every pair was answered, and say which sections are new.

Usage:
    python3 collect_sections.py <session_dir>

Reads `SECTION_PLAN.json` and the answer it names; writes `SECTIONS.json` — one entry per (document
template, item template) pair with its section, a derived id, and whether the app already had it.

A section id is derived here rather than copied, because the export carries none. It is the one id in
this whole run that is not the app's own, and `DOCUMENT_WORKBOOK_FORMAT.md` names it as the deliberate
exception. The derivation is stable: the same label on the same item template gives the same id twice.

Where the answer moves a pair the app already arranges, the app wins and the move is reported. Somebody
rearranging an existing Documents tab is a bigger decision than this step is allowed to take on its own.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SAMPLE = 14
PUNCTUATION = re.compile(r"[^a-z0-9]+")


def load(session_dir, name):
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def key_for(label):
    return PUNCTUATION.sub("_", (label or "").casefold()).strip("_")


def section_id(item_template, label):
    """Stable across runs, and distinct per item template — two tabs with a `Safety` section are two.

    The derivation is `DOCUMENT_WORKBOOK_FORMAT.md`'s, to the character: two places computing one id
    differently is a workbook whose sheets do not join to each other.
    """
    stem = hashlib.sha256(f"{item_template}:{key_for(label)}".encode("utf-8")).hexdigest()[:12]
    return f"ds_{stem}"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    plan = load(session_dir, "SECTION_PLAN.json")
    task = json.loads(Path(plan["input"]).read_text(encoding="utf-8"))
    output = Path(plan["output"])
    if not output.is_file():
        raise SystemExit(f"no answer at {output} — the section agent has not run")
    try:
        answered = json.loads(output.read_text(encoding="utf-8")).get("pairs") or []
    except json.JSONDecodeError as error:
        raise SystemExit(f"the section answer is not readable JSON: {error}")

    by_pair = {(a.get("documentTemplateId"), a.get("itemTemplate")): a for a in answered}
    known = {name: {s["label"] for s in sections}
             for name, sections in (task.get("itemTemplates") or {}).items()}

    settled, missing, moved = [], [], []
    for pair in task["pairs"]:
        answer = by_pair.get((pair["documentTemplateId"], pair["itemTemplate"]))
        label = " ".join((answer or {}).get("section", "").split())
        if not label:
            missing.append(f"{pair['documentTemplate']} on {pair['itemTemplate']}")
            continue
        # The app's own arrangement stands. Rearranging a Documents tab somebody already set up is not
        # this step's decision, and a silent move is the kind that gets noticed after the migration.
        if pair["alreadyIn"] and label != pair["alreadyIn"]:
            moved.append(f"{pair['documentTemplate']} on {pair['itemTemplate']}: "
                         f"{pair['alreadyIn']!r} kept, {label!r} not used")
            label = pair["alreadyIn"]
        is_new = label not in known.get(pair["itemTemplate"], set())
        settled.append({
            **{k: pair[k] for k in ("documentTemplateId", "documentTemplate", "itemTemplate",
                                    "table", "documents")},
            "section": label,
            "sectionKey": key_for(label),
            "sectionId": section_id(pair["itemTemplate"], label),
            "isNew": is_new,
            "why": " ".join((answer or {}).get("why", "").split()) or None,
        })

    new_sections = sorted({(s["itemTemplate"], s["section"]) for s in settled if s["isNew"]})
    written = {"pairs": settled, "missing": missing, "kept": moved,
               "newSections": [{"itemTemplate": t, "section": s} for t, s in new_sections]}
    (session_dir / "SECTIONS.json").write_text(json.dumps(written, indent=2), encoding="utf-8")

    print(f"{len(settled)}/{len(task['pairs'])} pair(s) arranged, "
          f"{len(new_sections)} new section(s) across "
          f"{len({t for t, _ in new_sections})} item template(s)")
    for entry in settled[:SAMPLE]:
        mark = "NEW" if entry["isNew"] else "   "
        print(f"  {mark}  {entry['documents']:5d}  {(entry['documentTemplate'] or '?')[:32]:32s} "
              f"on {entry['itemTemplate'][:20]:20s} -> {entry['section']}")
    if len(settled) > SAMPLE:
        print(f"  ... and {len(settled) - SAMPLE} more in SECTIONS.json")
    if moved:
        print(f"\nTHE APP'S OWN ARRANGEMENT KEPT ({len(moved)}):")
        for line in moved[:SAMPLE]:
            print(f"  {line}")
    if missing:
        print(f"\nNOT ANSWERED ({len(missing)}) — these reach the workbook with no section:")
        for line in missing[:SAMPLE]:
            print(f"  {line}")
    print(f"\n-> {session_dir / 'SECTIONS.json'}")


if __name__ == "__main__":
    main()
