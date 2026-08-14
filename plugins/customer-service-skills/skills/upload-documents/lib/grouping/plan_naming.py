"""Cut the forms into one naming task each, carrying a sample of what that form looks like blank.

Usage:
    python3 plan_naming.py <session_dir> [--samples 5] [--seed 0]

Reads `FORMS.json`, `DOCUMENTS.json` and `EXTRACTED.json`; writes one input file per form under
`naming/` and `NAMING.json` naming them.

Each task carries the **structure view** of up to five members: their own text with everything the form
does not repeat blanked out. The words kept are counted **inside the form**, not across the folder, so a
form used by sixty-eight documents keeps its own title instead of losing it to a folder dominated by
something else.

No document templates are in here. Naming a form is not choosing a type — the app's list belongs to the
classification step, and offering it here is what turned a form the app had no word for into nine hundred
Questionnaires.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import group_documents
import mask_text

# Enough copies to show what varies between them, few enough that one agent reads them all properly.
SAMPLES = 5
# A word this many of a form's own members share is printed on it rather than typed into one.
INSIDE = 0.4


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--samples", type=int, default=SAMPLES,
                        help=f"members shown per form, fewer where the form has fewer "
                             f"(default: {SAMPLES})")
    parser.add_argument("--seed", type=int, default=0,
                        help="the sample is random, and this makes it the same random twice (default: 0)")
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    forms = group_documents.load(session_dir, "FORMS.json")
    if forms.get("skipped"):
        raise SystemExit(f"nothing to name: {forms['skipped']}")

    texts, _ = group_documents.texts_by_sha(session_dir)
    names = {d["sha"]: d["name"] for d in group_documents.load(session_dir, "DOCUMENTS.json")}
    header_lines = forms.get("headerLines", 8)
    vocabulary = mask_text.vocabulary(list(texts.values()))

    task_dir = session_dir / "naming"
    task_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "named").mkdir(parents=True, exist_ok=True)

    chooser = random.Random(options.seed)
    tasks = []
    for form in forms["forms"]:
        members = [sha for sha in form["members"] if sha in texts]
        if not members:
            continue
        chosen = sorted(chooser.sample(members, min(options.samples, len(members))))

        # Counted inside this form, which is the whole reason naming happens after grouping.
        inside = mask_text.frequency([texts[sha] for sha in members])
        wanted = max(1, round(INSIDE * len(members)))
        keep = {word for word, count in inside.items() if count >= wanted}

        samples = [{
            "name": names.get(sha, sha),
            "structure": mask_text.structure_view(texts[sha], keep, header_lines, vocabulary),
        } for sha in chosen]

        payload = {"formId": form["id"], "documents": len(form["members"]), "samples": samples}
        input_path = task_dir / f"{form['id']}.json"
        input_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tasks.append({
            "formId": form["id"],
            "documents": len(form["members"]),
            "input": str(input_path.resolve()).replace("\\", "/"),
            "output": str((session_dir / "named" / f"{form['id']}.json").resolve()).replace("\\", "/"),
            "samples": [s["name"] for s in samples],
        })

    (session_dir / "NAMING.json").write_text(
        json.dumps({"samples": options.samples, "seed": options.seed, "tasks": tasks}, indent=2),
        encoding="utf-8")

    print(f"{len(tasks)} form(s) to name, {sum(len(t['samples']) for t in tasks)} sample(s) in total")
    print(f"\n-> {session_dir / 'NAMING.json'}")


if __name__ == "__main__":
    main()
