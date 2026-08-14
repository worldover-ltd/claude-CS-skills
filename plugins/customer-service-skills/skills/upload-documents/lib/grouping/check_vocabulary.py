"""Hold each form's own name up against the list the app can offer, before anything is classified.

Usage:
    python3 check_vocabulary.py <session_dir> [--match 0.6]

Reads `NAMED.json`, `FORMS.json` and `WORKFLOW.json`; writes `VOCABULARY_GAP.json` and prints what the
app has no word for, with the number of documents behind each one.

This runs where it does — after naming, before classifying — because that is the only moment the run
knows both what the documents are and what the app can call them, and can still act on the difference.
On the folder this came from, three forms carrying 1,808 of 1,887 documents had no template in the app.
Every one of those documents was filed under the closest name on the list instead, and 1,016 of them
became `Questionnaire`. The same folder run against an app that *had* those templates produced none.

Nothing here decides anything. A near match is reported with its score rather than accepted, because the
cost of being wrong is a document filed against a template the customer means something else by, and the
person reading this owns that vocabulary.
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

SAMPLE = 12
# Below this, two names are not the same name. Chosen loose on purpose: a miss here is a form put in
# front of a person, which is cheap, and a false match is a silent filing error, which is not.
MATCH = 0.6
NOISE = re.compile(r"[^a-z0-9 ]+")
# Words that say nothing about which template a form is, so two names should not match on them alone.
COMMON = {"document", "documents", "form", "forms", "sheet", "sheets", "statement", "statements",
          "certificate", "certificates", "information", "product", "products", "raw", "material",
          "materials", "report", "reports", "the", "of", "and", "for", "a", "an"}


def load(session_dir, name):
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def words_in(text):
    return [w for w in NOISE.sub(" ", (text or "").casefold()).split() if w]


def closeness(title, name):
    """How much one form title and one template name are the same name, 0 to 1.

    Two measures, and the lower one wins. Sequence similarity alone calls `Product Specification` and
    `Product Information` close, because they share most of their letters; requiring a shared word that
    is not `product` is what separates them.
    """
    left, right = words_in(title), words_in(name)
    if not left or not right:
        return 0.0
    sequence = difflib.SequenceMatcher(None, " ".join(left), " ".join(right)).ratio()
    telling = (set(left) - COMMON) & (set(right) - COMMON)
    if not telling:
        # No word of substance in common. Only an almost-exact string can still be the same name.
        return sequence if sequence > 0.9 else min(sequence, 0.4)
    return sequence


def best_match(title, templates):
    scored = [(closeness(title, t["name"]), t) for t in templates]
    scored.sort(key=lambda pair: (-pair[0], pair[1]["name"]))
    return scored[0] if scored else (0.0, None)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--match", type=float, default=MATCH,
                        help=f"how alike two names must be to count as the same name (default: {MATCH})")
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    named = load(session_dir, "NAMED.json")
    workflow = load(session_dir, "WORKFLOW.json")
    templates = [t for t in workflow.get("documentTemplates") or [] if t.get("name")]

    matched, missing, unnamed = [], [], []
    for form in named.get("forms") or []:
        entry = {"formId": form["formId"], "documents": form.get("documents") or 0,
                 "title": form.get("title") or "", "description": form.get("description") or ""}
        if not entry["title"]:
            unnamed.append(entry)
            continue
        score, template = best_match(entry["title"], templates)
        if template is not None and score >= options.match:
            matched.append({**entry, "templateId": template["id"], "templateName": template["name"],
                            "score": round(score, 3)})
        else:
            nearest = [{"name": t["name"], "score": round(s, 3)}
                       for s, t in sorted(((closeness(entry["title"], t["name"]), t) for t in templates),
                                          key=lambda pair: -pair[0])[:3]]
            missing.append({**entry, "nearest": nearest})

    written = {
        "match": options.match,
        "templates": len(templates),
        "matched": matched,
        "missing": missing,
        "unnamed": unnamed,
        "documentsWithNoTemplate": sum(m["documents"] for m in missing),
    }
    (session_dir / "VOCABULARY_GAP.json").write_text(json.dumps(written, indent=2), encoding="utf-8")

    total = sum(f.get("documents") or 0 for f in named.get("forms") or [])
    print(f"{len(matched)} of {len(matched) + len(missing)} named form(s) match a document template "
          f"the app already has\n")
    for form in matched[:SAMPLE]:
        print(f"  {form['formId']}  {form['documents']:5d} documents  {form['title'][:44]:44s} "
              f"-> {form['templateName']} ({form['score']:.2f})")
    if unnamed:
        print(f"\n{len(unnamed)} form(s) came back with no title — name them again before this means "
              f"anything: {', '.join(f['formId'] for f in unnamed)}")

    if missing:
        print(f"\nTHE APP HAS NO TEMPLATE FOR THESE ({len(missing)} form(s), "
              f"{written['documentsWithNoTemplate']} of {total} document(s)):\n")
        for form in missing[:SAMPLE]:
            print(f"  {form['formId']}  {form['documents']:5d} documents  {form['title']}")
            if form["description"]:
                print(f"           {form['description'][:96]}")
            near = ", ".join(f"{n['name']} ({n['score']:.2f})" for n in form["nearest"])
            print(f"           nearest the app has: {near}")
        if len(missing) > SAMPLE:
            print(f"  ... and {len(missing) - SAMPLE} more in VOCABULARY_GAP.json")
        print("\n  Two roads, and the user picks:")
        print("   - create these template(s) in the app and re-export both files, then run this again.")
        print("     Every document above attaches on its own afterwards.")
        print("   - carry on, and these reach the workbook as placeholder rows nobody can attach until")
        print("     somebody creates the template anyway. Worth it for a form of two documents, not for")
        print("     a form of a thousand.")

    print(f"\n-> {session_dir / 'VOCABULARY_GAP.json'}")


if __name__ == "__main__":
    main()
