"""Record that the run picked the wrong document for a material, and set it up to read the right one.

Usage:
    python3 apply_recut.py <session_dir> <recut.json> [<recut.json> ...]

A recut names one material and the file its composition should have come from:

    {
      "identifier": "R373",
      "sourceFile": "R373- Elopers PM400 SDS NZ GHS 2023-05-18.pdf",
      "why": "the New Zealand sheet of 18 May 2023 supersedes the 2022 one the run picked"
    }

It rewrites that material's task to hold the named file alone and clears the old answer, so the next
wave re-reads it. The shortlist itself is left as it was, so the workbook can still show every file the
run considered for the material somebody disagreed about - which is the material whose record is worth
the most. The rows still come from a sub agent and are still held against the document, because
a row typed into a file by hand is a row nothing checks - which is the failure this whole run is built
to prevent.

`"sourceFile": null` records that no file in the folder states this material's composition, and the
material keeps no rows.

Recuts are files rather than edits so that a rebuild reproduces the decision. A run re-read from scratch
loses a correction made in a spreadsheet; it replays one made here.
"""

import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("recuts", nargs="+", type=Path)
    args = parser.parse_args()
    session = args.session_dir

    manifest = load(session / "READINGS.json")
    tasks = {task["identifier"]: task for task in manifest["tasks"]}
    applied, problems = [], []
    for recut_path in args.recuts:
        recut = load(recut_path)
        identifier = recut.get("identifier")
        task = tasks.get(identifier)
        if task is None:
            problems.append(f"{recut_path.name}: no task for {identifier!r}")
            continue
        wanted = recut.get("sourceFile")
        task_file = Path(task["input"])
        body = load(task_file)

        if wanted is None:
            body["files"] = []
            body["recut"] = {"sourceFile": None, "why": recut.get("why", "")}
            applied.append(f"{identifier}: recorded as having no composition document")
        else:
            match = [entry for entry in body["files"] if entry["fileName"] == wanted]
            if not match:
                names = ", ".join(entry["fileName"] for entry in body["files"])
                problems.append(f"{recut_path.name}: {wanted!r} is not a candidate for {identifier} "
                                f"- shortlisted are: {names}")
                continue
            body["files"] = match
            body["recut"] = {"sourceFile": wanted, "why": recut.get("why", "")}
            applied.append(f"{identifier}: {wanted}")

        task_file.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
        answer = Path(task["output"])
        if answer.is_file():
            answer.unlink()

    for line in applied:
        print(f"  {line}")
    for line in problems:
        print(f"  PROBLEM {line}")
    print(f"\n{len(applied)} recut(s) applied, {len(problems)} refused")
    if applied:
        print("send the wave again for those materials, then run collect_compositions.py")


if __name__ == "__main__":
    main()
