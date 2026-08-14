"""Ask what the app calls each form — once per form, not once per document.

Usage:
    python3 plan_form_classification.py <session_dir> [--samples 5] [--seed 0]

Reads `FORMS.json`, `NAMED.json`, `WORKFLOW.json`, `ITEMS.csv`, `BRANCHES.json`, `DOCUMENTS.json` and
`EXTRACTED.json`; writes one input file per form under `form_templates/` and `FORM_CLASSIFICATION.json`.

Every document printed on one form is the same kind of document, so asking per document buys nothing and
costs everything: on the folder this came from it is sixteen questions instead of 1,819. See docs/adr/0005.

A form a person marked **split by value** is not planned here. Its members are the same stationery and the
app still calls them different things, because what separates them was typed in — so those go back to
`plan_batches.py` and are read one at a time, which is the one place that price is worth paying.

The task carries the form's own title and description, which the naming step wrote **without the app's
list in view**. That ordering is the whole reason the gate before this step can mean anything: a title
written after seeing `Questionnaire` would have said `Questionnaire`.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import group_documents
import mask_text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import item_index  # noqa: E402

SAMPLES = 5
INSIDE = 0.4
FALLBACK_TEMPLATES = Path(__file__).resolve().parent.parent.parent / "references/DOCUMENT_TYPES.txt"


def split_by_value(session_dir):
    """The forms a person said hold more than one kind of document. Read one at a time, not here."""
    path = session_dir / "SPLIT_RULES.json"
    if not path.is_file():
        return {}
    body = json.loads(path.read_text(encoding="utf-8"))
    return {entry["form"]: entry.get("splitsInto") for entry in body.get("splitByValue") or []}


def tables_by_sha(session_dir):
    """{sha: {tables}} — which app table each document sits on, resolved once for the whole folder.

    Once, because the branch rules are the same for every form and re-walking every path per form is
    the folder read seventeen times over.
    """
    if not (session_dir / "BRANCHES.json").is_file():
        return {}
    branches = json.loads((session_dir / "BRANCHES.json").read_text(encoding="utf-8")).get("branches")
    if not branches:
        return {}
    tables = {}
    for document in group_documents.load(session_dir, "DOCUMENTS.json"):
        branch = item_index.branch_for(document["relativePath"], branches)
        if branch and branch.get("table"):
            tables.setdefault(document["sha"], set()).add(branch["table"])
    return tables


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--samples", type=int, default=SAMPLES,
                        help=f"members shown per form (default: {SAMPLES})")
    parser.add_argument("--seed", type=int, default=0, help="makes the sample the same twice")
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    forms = group_documents.load(session_dir, "FORMS.json")
    if forms.get("skipped"):
        raise SystemExit(f"nothing to classify by form: {forms['skipped']}")

    named = {f["formId"]: f for f in (group_documents.load(session_dir, "NAMED.json").get("forms") or [])}
    try:
        app = item_index.load(session_dir / "WORKFLOW.json", session_dir / "ITEMS.csv")
    except item_index.ExportError as error:
        raise SystemExit(f"the export cannot be used: {error}")

    texts, _ = group_documents.texts_by_sha(session_dir)
    names = {d["sha"]: d["name"] for d in group_documents.load(session_dir, "DOCUMENTS.json")}
    header_lines = forms.get("headerLines", 8)
    vocabulary = mask_text.vocabulary(list(texts.values()))
    splits = split_by_value(session_dir)
    tables_of = tables_by_sha(session_dir)

    task_dir = session_dir / "form_templates"
    task_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "form_classified").mkdir(parents=True, exist_ok=True)

    chooser = random.Random(options.seed)
    tasks, skipped = [], []
    for form in forms["forms"]:
        if form["id"] in splits:
            skipped.append((form["id"], "split by value — read one document at a time"))
            continue
        entry = named.get(form["id"])
        if not entry or not entry.get("title"):
            skipped.append((form["id"], "no title — the naming step has not settled it"))
            continue
        members = [sha for sha in form["members"] if sha in texts]
        if not members:
            skipped.append((form["id"], "nothing readable in any member"))
            continue

        tables = sorted({table for sha in members for table in tables_of.get(sha, ())})
        if not tables:
            skipped.append((form["id"], "no branch covers any of its documents"))
            continue

        chosen = sorted(chooser.sample(members, min(options.samples, len(members))))
        inside = mask_text.frequency([texts[sha] for sha in members])
        wanted = max(1, round(INSIDE * len(members)))
        keep = {word for word, count in inside.items() if count >= wanted}

        payload = {
            "formId": form["id"],
            "documents": len(form["members"]),
            "title": entry["title"],
            "description": entry.get("description") or "",
            "fallbackTemplates": str(FALLBACK_TEMPLATES).replace("\\", "/"),
            "vocabulary": {"documentTemplates": {t: app.templates_for(t) for t in tables}},
            "samples": [{
                "name": names.get(sha, sha),
                "structure": mask_text.structure_view(texts[sha], keep, header_lines, vocabulary),
            } for sha in chosen],
        }
        input_path = task_dir / f"{form['id']}.json"
        input_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tasks.append({
            "formId": form["id"],
            "documents": len(form["members"]),
            "tables": tables,
            "input": str(input_path.resolve()).replace("\\", "/"),
            "output": str((session_dir / "form_classified" / f"{form['id']}.json")
                          .resolve()).replace("\\", "/"),
        })

    (session_dir / "FORM_CLASSIFICATION.json").write_text(
        json.dumps({"samples": options.samples, "seed": options.seed,
                    "tasks": tasks, "skipped": [{"formId": f, "why": w} for f, w in skipped]}, indent=2),
        encoding="utf-8")

    covered = sum(t["documents"] for t in tasks)
    print(f"{len(tasks)} form(s) to classify, standing for {covered} document(s)")
    if skipped:
        print(f"\nNOT ASKED HERE ({len(skipped)}):")
        for form_id, why in skipped:
            print(f"  {form_id} — {why}")
        print("  these reach plan_batches.py and are read one document at a time")
    print(f"\n-> {session_dir / 'FORM_CLASSIFICATION.json'}")


if __name__ == "__main__":
    main()
