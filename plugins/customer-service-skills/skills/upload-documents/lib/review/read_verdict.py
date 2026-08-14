"""Turn what the person pasted back into data the run can act on.

Usage:
    python3 read_verdict.py <session_dir> <pasted_file>

Reads `REVIEW.json` and a file holding what the page copied; writes `REVIEW_RESULT.json`.

The page copies prose for the person and a fenced ```form-review block for this script. Parsing the prose
would mean guessing, and a guess here silently changes which documents get read again — so the fence is
required, and a paste without one is refused rather than interpreted.

The failure rate is computed only from the **random** block. The suspect block is chosen to look wrong,
so counting it would make a good form look bad and a better choosing algorithm look worse.
"""

import argparse
import json
import re
import sys
from pathlib import Path

FENCE = re.compile(r"```form-review\s*(.+?)```", re.DOTALL)
VERDICTS = {"grouping": {"ok", "mixed"}, "naming": {"ok", "wrong"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("pasted", type=Path, help="a file holding what the page copied")
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    manifest = session_dir / "REVIEW.json"
    if not manifest.is_file():
        raise SystemExit(f"missing REVIEW.json in {session_dir} — build_review.py has not run")
    if not options.pasted.is_file():
        raise SystemExit(f"no such file: {options.pasted}")

    found = FENCE.search(options.pasted.read_text(encoding="utf-8", errors="replace"))
    if not found:
        raise SystemExit(
            "that paste holds no ```form-review block. The page copies one at the end of what it puts "
            "on the clipboard — paste all of it, not just the readable part.")
    try:
        answered = json.loads(found.group(1)).get("forms") or []
    except json.JSONDecodeError as error:
        raise SystemExit(f"the form-review block is not readable JSON: {error}")

    review = json.loads(manifest.read_text(encoding="utf-8"))
    shown = {form["formId"]: form for form in review["forms"]}
    names = {form["formId"]: {s["name"]: s for s in form["samples"]} for form in review["forms"]}

    unknown = [f.get("formId") for f in answered if f.get("formId") not in shown]
    if unknown:
        raise SystemExit(
            "the review names form(s) nobody was shown: " + ", ".join(str(u) for u in unknown) +
            ". That paste belongs to a different run.")

    out, missing = [], []
    for form_id, form in shown.items():
        answer = next((a for a in answered if a.get("formId") == form_id), None)
        if answer is None:
            missing.append(form_id)
            answer = {}
        marked = [name for name in (answer.get("marked") or []) if name in names[form_id]]
        strays = [name for name in (answer.get("marked") or []) if name not in names[form_id]]
        fair = [name for name in marked if names[form_id][name]["block"] == "random"]
        rate = len(fair) / form["randomShown"] if form["randomShown"] else 0.0
        out.append({
            "formId": form_id,
            "documents": form["documents"],
            "grouping": answer.get("grouping") if answer.get("grouping") in VERDICTS["grouping"] else "ok",
            "naming": answer.get("naming") if answer.get("naming") in VERDICTS["naming"] else "ok",
            "randomShown": form["randomShown"],
            "randomMarked": len(fair),
            # Only the fair sample is a rate. The rest is a list of documents to take out.
            "failureRate": round(rate, 3),
            "marked": marked,
            "markedShas": [names[form_id][name]["sha"] for name in marked],
            "notShown": strays,
        })

    (session_dir / "REVIEW_RESULT.json").write_text(
        json.dumps({"forms": out, "unanswered": missing}, indent=2), encoding="utf-8")

    print(f"{len(out) - len(missing)}/{len(out)} form(s) reviewed, "
          f"{sum(len(f['marked']) for f in out)} document(s) marked")
    for form in out:
        if form["marked"] or form["grouping"] != "ok" or form["naming"] != "ok":
            print(f"  {form['formId']}  grouping {form['grouping']}, name {form['naming']}, "
                  f"{form['randomMarked']}/{form['randomShown']} of the fair sample marked")
    if missing:
        print(f"\nNOT REVIEWED ({len(missing)}): {', '.join(missing)} — taken as holding.")
    print(f"\n-> {session_dir / 'REVIEW_RESULT.json'}")


if __name__ == "__main__":
    main()
