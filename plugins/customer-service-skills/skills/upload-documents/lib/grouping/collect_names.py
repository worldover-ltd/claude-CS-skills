"""Take the naming answers back, count who answered, and hold them to their limits.

Usage:
    python3 collect_names.py <session_dir> [--title 120] [--description 600]

Reads `NAMING.json` and the answer files it names; writes `NAMED.json` — one entry per form with its
title and description — and prints the roll call.

The roll call is counted against `NAMING.json`, never against what an agent reported doing. On the run
this work came out of, six batches of twenty said they had answered nineteen and every one of them was
complete; the count on disk was right and the agent's own account of it was not.

An answer naming a form that was not sent is dropped rather than carried, the same way the classifier's
collector drops a row for a document that was not in the batch.
"""

import argparse
import json
import sys
from pathlib import Path

SAMPLE = 10
TITLE = 120
DESCRIPTION = 600


def trim(text, limit):
    """(text, whether it had to be cut) — cut on a word boundary where there is one nearby."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit * 0.6 else cut).rstrip(" .,;:-"), True


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--title", type=int, default=TITLE, help=f"longest title kept (default: {TITLE})")
    parser.add_argument("--description", type=int, default=DESCRIPTION,
                        help=f"longest description kept (default: {DESCRIPTION})")
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    planned = session_dir / "NAMING.json"
    if not planned.is_file():
        raise SystemExit(f"missing NAMING.json in {session_dir} — the naming step has not been planned")
    tasks = json.loads(planned.read_text(encoding="utf-8")).get("tasks") or []

    named, missing, unreadable, trimmed, unasked = [], [], [], [], []
    for task in tasks:
        output = Path(task["output"])
        if not output.is_file():
            missing.append(task["formId"])
            continue
        try:
            answer = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            unreadable.append(f"{task['formId']} — {error}")
            missing.append(task["formId"])
            continue
        # An answer that names some other form is not an answer to this task. Keeping it would let one
        # agent's mistake overwrite a form it was never shown.
        if answer.get("formId") not in (None, task["formId"]):
            unasked.append(f"{answer.get('formId')!r} answered for {task['formId']}")
            missing.append(task["formId"])
            continue
        title, title_cut = trim(answer.get("title"), options.title)
        description, description_cut = trim(answer.get("description"), options.description)
        if title_cut or description_cut:
            trimmed.append(task["formId"])
        if not title:
            missing.append(task["formId"])
            continue
        named.append({"formId": task["formId"], "documents": task["documents"],
                      "title": title, "description": description})

    written = {"forms": named, "missing": sorted(set(missing)), "trimmed": sorted(set(trimmed)),
               "unreadable": unreadable, "answeredForSomeoneElse": unasked}
    (session_dir / "NAMED.json").write_text(json.dumps(written, indent=2), encoding="utf-8")

    print(f"{len(named)}/{len(tasks)} form(s) named")
    for form in named[:SAMPLE]:
        print(f"  {form['formId']}  {form['documents']:5d} documents  {form['title']}")
    if len(named) > SAMPLE:
        print(f"  ... and {len(named) - SAMPLE} more in NAMED.json")
    if trimmed:
        print(f"\nTRIMMED to the limits ({len(set(trimmed))}): {', '.join(sorted(set(trimmed)))}")
    for heading, rows in (("SEND THESE AGAIN", sorted(set(missing))),
                          ("UNREADABLE ANSWER", unreadable),
                          ("ANSWERED FOR A FORM IT WAS NOT SHOWN", unasked)):
        if rows:
            print(f"\n{heading} ({len(rows)}): {', '.join(rows)}")

    print(f"\n-> {session_dir / 'NAMED.json'}")


if __name__ == "__main__":
    main()
