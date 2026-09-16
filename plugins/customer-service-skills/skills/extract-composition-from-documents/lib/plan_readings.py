"""Cut the shortlist into one task per raw material, with the text a sub agent needs inlined.

Usage:
    python3 plan_readings.py <session_dir> [--window 3500]

Reads <session_dir>/CANDIDATES.json and writes one <session_dir>/readings/<code>.json per material,
plus <session_dir>/READINGS.json naming them.

Each task carries, per candidate file: the slice of its text the composition lives in, every date the
file prints with the label in front of it, and every CAS and EC number in it that passes its check
digit. The agent opens nothing - reading a file inside an agent costs about ninety times what inlining
the extracted text costs, and this run has already paid to extract every one of them.

The slice is a window around the composition heading rather than the head of the document: a statement
prints its table pages in, and a head-and-tail cap reaches the cover page and the footer instead. Where
no heading scores, the window follows the numbers rather than giving up on the middle of the document.

A task also carries the safety data sheets under that material, which `score_composition.py` refused as
sources. Only their CAS and EC numbers, under the name of the file they came from - a register the
reader can check a name against, never a text it may quote.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import codes
from signals import CODE_OR_PERCENT, HEADING, body_and_tables, file_key, join, read_text


def densest(text, size):
    """Where the CAS numbers and percentages are thickest, for a document that titles nothing.

    Stepped over the text rather than solved exactly: a composition is one dense patch in a document
    that is otherwise prose, and the step only has to land inside it.
    """
    step = max(size // 4, 1)
    best, weight = 0, -1
    for start in range(0, max(len(text) - size, 0) + step, step):
        found = len(CODE_OR_PERCENT.findall(text[start:start + size]))
        if found > weight:
            best, weight = start, found
    return best if weight > 0 else None


def window(text, size):
    """The part of the document a composition sits in.

    Every heading is tried rather than the first one. These sheets carry the words `Section 3 of SDS` in
    a summary block on page one and print the table itself pages later, so the first match is regularly
    a cross-reference. What separates them is what follows: the table has the CAS numbers and the
    percentages under it, and the cross-reference has prose.

    Where no heading scores, the densest run of CAS numbers and percentages is taken instead. That case
    is not rare - on 678 long documents carrying composition words, 130 of them named no heading the
    scoring recognised - and the head-and-tail slice this used to fall back to is the one cut that
    cannot contain a table in the middle of a document. A scanned statement whose heading OCR mangled
    still has its numbers.
    """
    if len(text) <= size:
        return text
    best, weight = None, 0
    for match in HEADING.finditer(text):
        start = max(0, match.start() - size // 6)
        found = len(CODE_OR_PERCENT.findall(text[start:start + size]))
        if found > weight:
            best, weight = start, found
    if best is None:
        best = densest(text, size)
    if best is not None:
        return text[best:best + size]
    return text[: size * 3 // 4] + "\n\n[...]\n\n" + text[-(size // 4):]


def reference_codes(text):
    """The CAS and EC numbers in a file that is not allowed to be a source.

    A safety data sheet still prints an identifier against every substance it names, which makes it the
    best register in the folder even where its percentages cannot be trusted. These reach the reader
    under the name of the file they came from, so a number it recognises never arrives looking like a
    row it may transcribe.
    """
    return {"cas": codes.find(text, "cas"), "ec": codes.find(text, "ec")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--window", type=int, default=3500, help="characters inlined per candidate")
    args = parser.parse_args()
    session = args.session_dir

    candidates = json.loads((session / "CANDIDATES.json").read_text(encoding="utf-8"))
    extracted = {file_key(record["path"]): record for record in
                 json.loads((session / "EXTRACTED.json").read_text(encoding="utf-8"))["documents"]}
    by_path = {document["relativePath"]: document
               for document in json.loads((session / "DOCUMENTS.json").read_text(encoding="utf-8"))}

    tasks_dir = session / "readings"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    manifest, without = [], []
    for material in candidates["materials"]:
        if not material["candidates"]:
            # Carried rather than skipped: a material whose folder holds nothing composition-shaped is
            # an answer the run owes the user by name, and the collector turns this into an issue.
            without.append({"identifier": material["identifier"], "itemName": material["itemName"],
                            "filesSeen": material.get("filesSeen", 0),
                            "sheetsOnly": [s["fileName"] for s in material.get("sheets") or []]})
            continue
        files = []
        for candidate in material["candidates"]:
            document = by_path.get(candidate["relativePath"], {})
            body, tables = body_and_tables(extracted.get(file_key(document.get("path")), {}))
            text = join(body, tables)
            files.append({
                "sha": candidate["sha"], "fileName": candidate["fileName"],
                "sourceFolder": candidate["folder"], "signals": candidate["signals"],
                "datesPrinted": candidate["dates"],
                "casNumbers": codes.find(text, "cas"), "ecNumbers": codes.find(text, "ec"),
                "text": join(window(body, args.window), tables),
            })
        reference = []
        for sheet in material.get("sheets") or []:
            document = by_path.get(sheet["relativePath"], {})
            found = reference_codes(read_text(extracted.get(file_key(document.get("path")), {})))
            if found["cas"] or found["ec"]:
                reference.append({"fileName": sheet["fileName"], **found})

        code = re.sub(r"[^A-Za-z0-9_.-]", "_", material["identifier"])
        task = {
            "identifier": material["identifier"], "itemName": material["itemName"],
            "table": material["table"], "sourceFolders": material["folders"], "files": files,
            "safetyDataSheets": reference,
        }
        path = tasks_dir / f"{code}.json"
        path.write_text(json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest.append({
            "identifier": material["identifier"], "input": str(path).replace("\\", "/"),
            "output": str(session / "read" / f"{code}.json").replace("\\", "/"),
            "fileCount": len(files),
        })

    (session / "read").mkdir(parents=True, exist_ok=True)
    (session / "READINGS.json").write_text(
        json.dumps({"tasks": manifest, "noCandidates": without, "window": args.window},
                   indent=2, ensure_ascii=False),
        encoding="utf-8")

    print(f"{len(manifest)} task(s), "
          f"{sum(t['fileCount'] for t in manifest)} candidate file(s) between them")
    if without:
        print(f"  {len(without)} material(s) have no candidate at all and go straight to the issues")
    print(f"\n-> {session / 'READINGS.json'}")


if __name__ == "__main__":
    main()
