"""Turn what a person marked into a rule the unchanged script can apply, or give the form up.

Usage:
    python3 apply_marks.py <session_dir> [--fail 0.25] [--present 0.8] [--absent 0.2]

Reads `REVIEW_RESULT.json`, `FORMS.json` and the extracted text; writes `SPLIT_RULES.json`.

A person marking documents inside one form has labelled that form: these belong, those do not. That is
enough to look for the wording which separates them — and wording is something a customer can be shown,
argued with, and told is wrong. So feedback becomes **data** the same script reads on every folder, never
a change to the script itself. A pipeline that rewrites its own code per customer is how the run this work
came out of ended up with 484 documents carrying an answer written for a different document.

Where no wording separates the marks, the form **dissolves**: its documents go back to being read one at
a time, exactly as this skill behaved before grouping existed. That is the loop's exit, and it always
terminates. It is also the right answer more often than it sounds — on the folder this came from, the one
genuinely contested form had no separating wording at all, because the disagreement was about what to
*call* it rather than about which documents belonged.
"""

import argparse
import json
import sys
from pathlib import Path

import group_documents
import mask_text

# A form is worth repairing when this share of its fairly-chosen sample was marked. Below it, the marked
# documents are simply taken out and the form stands.
FAIL = 0.25
# Wording separates the marks when nearly every marked document has it and nearly none of the rest does.
PRESENT, ABSENT = 0.8, 0.2
SAMPLE = 6


def separating_wording(marked, held, texts):
    """Words that nearly every marked document has and nearly no other, or an empty list.

    Both directions are tried, because "these are the ones with REMOVAL" and "these are the ones missing
    it" are the same rule seen from either side, and the caller only needs one of them.
    """
    if not marked or not held:
        return []
    marked_words = [set(mask_text.words(texts.get(sha, ""))) for sha in marked]
    held_words = [set(mask_text.words(texts.get(sha, ""))) for sha in held]
    candidates = set().union(*marked_words) | set().union(*held_words)

    found = []
    for word in sorted(candidates):
        in_marked = sum(1 for bag in marked_words if word in bag) / len(marked_words)
        in_held = sum(1 for bag in held_words if word in bag) / len(held_words)
        if in_marked >= PRESENT and in_held <= ABSENT:
            found.append((in_marked - in_held, word))
        elif in_held >= PRESENT and in_marked <= ABSENT:
            found.append((in_held - in_marked, word))
    found.sort(reverse=True)
    return [word for _, word in found[:3]]


def separating_threshold(marked, held, session_dir, texts):
    """The lowest stricter bar that stops putting the marked documents with the rest, or None.

    Some forms are not wrong about *what* their members say, only about how much they had to share to be
    counted as one. There is no wording to name in that case, and a number is still something a person can
    be shown and argue with — which a change to the clustering code would not be.
    """
    if not marked or not held:
        return None
    written = group_documents.load(session_dir, "FORMS.json")
    counted = mask_text.frequency(list(texts.values()))
    known = mask_text.vocabulary(list(texts.values()))
    floor = written.get("floor") or 2
    members = list(marked) + list(held)
    signatures = {sha: mask_text.signature(texts.get(sha, ""), counted, floor, known) for sha in members}

    for bar in (0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9):
        where = {}
        for number, form in enumerate(group_documents.cluster(signatures, bar)):
            for sha in form["members"]:
                where[sha] = number
        if not ({where[sha] for sha in marked} & {where[sha] for sha in held}):
            return bar
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--fail", type=float, default=FAIL,
                        help=f"share of the fair sample that must be marked before a form is repaired "
                             f"rather than trimmed (default: {FAIL})")
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    result = group_documents.load(session_dir, "REVIEW_RESULT.json")
    forms = {form["id"]: form for form in group_documents.load(session_dir, "FORMS.json")["forms"]}
    texts, _ = group_documents.texts_by_sha(session_dir)

    rules, dissolved, alone, renamed = [], [], [], []
    for reviewed in result["forms"]:
        form = forms.get(reviewed["formId"])
        if form is None:
            continue
        if reviewed["naming"] == "wrong":
            renamed.append(reviewed["formId"])

        marked = [sha for sha in reviewed["markedShas"] if sha in form["members"]]
        failing = reviewed["grouping"] == "mixed" or reviewed["failureRate"] >= options.fail

        if not failing:
            # The form holds; whoever was marked simply is not on it.
            alone.extend(marked)
            continue

        held = [sha for sha in form["members"] if sha not in marked]
        wording = separating_wording(marked, held, texts)
        tighter = None if wording else separating_threshold(marked, held, session_dir, texts)
        if wording:
            rules.append({"form": reviewed["formId"], "wording": wording,
                          "from": {"marked": len(marked), "held": len(held)}})
        elif tighter:
            rules.append({"form": reviewed["formId"], "threshold": tighter,
                          "from": {"marked": len(marked), "held": len(held)}})
        else:
            dissolved.append(reviewed["formId"])
            alone.extend(form["members"])

    written = {"rules": rules, "dissolved": dissolved,
               "readOneAtATime": sorted(set(alone)), "renameThese": renamed}
    (session_dir / "SPLIT_RULES.json").write_text(json.dumps(written, indent=2), encoding="utf-8")

    print(f"{len(rules)} rule(s), {len(dissolved)} form(s) dissolved, "
          f"{len(written['readOneAtATime'])} document(s) to read one at a time")
    for rule in rules[:SAMPLE]:
        print(f"  {rule['form']} splits on {', '.join(rule['wording'])}")
    if dissolved:
        print(f"\nDISSOLVED — nothing in the wording separated what was marked: {', '.join(dissolved)}")
    if renamed:
        print(f"\nNAME REJECTED — these need naming again: {', '.join(renamed)}")
    if rules:
        print("\nRun group_documents.py again to apply the rules, then name and review the new forms.")
    print(f"\n-> {session_dir / 'SPLIT_RULES.json'}")


if __name__ == "__main__":
    main()
