"""Group the folder's documents by the form each one is printed on, before anybody names a single one.

Usage:
    python3 group_documents.py <session_dir> [--floor-fraction 0.025] [--threshold 0.45]
                               [--min-corpus 40] [--header-lines 8] [--sweep]

Reads `DOCUMENTS.json` for the sha of every file and `EXTRACTED.json` for what can be read of it, and
writes `FORMS.json`: one entry per form, naming the documents printed on it, how strongly each one joined,
and the wording they share.

Nothing is read by a model here and nothing is named. A form is a claim about stationery — that these
documents carry the same title, the same field labels and the same column headings — and the number
behind that claim is written down beside it so it can be argued with later.

`SPLIT_RULES.json`, where it exists, is read and applied. It is written by the repair path after somebody
has looked at the forms and said which documents do not belong. Feedback lands there as **data**: this
script is the same script on every folder, so a form stays reproducible and explainable.

The defaults come from one real folder of 1,887 scanned documents, measured against the types a person
later confirmed: a floor of 2.5% and a threshold of 0.55 put 98.4% of documents in a form whose members
all turned out to be the same type. Raising the threshold buys almost no purity and doubles the forms
somebody has to look at; lowering it merges two supplier-form revisions that a person could tell apart.
They are a starting point for the next folder, not a constant — `--sweep` shows what the alternatives do.
"""

import argparse
import json
import sys
from pathlib import Path

import mask_text

SAMPLE = 8
# Below this many documents there is no such thing as a word "most documents share", so grouping would
# invent forms out of noise. Saying so beats returning a folder of singletons that looks like an answer.
MIN_CORPUS = 40
SWEEP_FLOORS = (0.01, 0.02, 0.025, 0.05, 0.1)
SWEEP_THRESHOLDS = (0.35, 0.45, 0.55, 0.65)


def load(session_dir, name):
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def readable_text(record):
    """What can be read of one file. OCR and a text layer are both text; the longer one says more."""
    best = ""
    for field in ("textFile", "ocrTextFile"):
        path = record.get(field)
        if not path:
            continue
        try:
            body = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(body) > len(best):
            best = body
    return best


def texts_by_sha(session_dir):
    """({sha: text}, files seen) — one text per document, because copies are one document. See ADR-0001."""
    documents = load(session_dir, "DOCUMENTS.json")
    extracted = {r["path"]: r for r in (load(session_dir, "EXTRACTED.json").get("documents") or [])}
    texts, files = {}, 0
    for document in documents:
        files += 1
        record = extracted.get(document["path"])
        if record is None:
            continue
        body = readable_text(record)
        # The longest reading of any copy stands for the content: one copy converting badly should not
        # take the others' evidence with it.
        if body and len(body) > len(texts.get(document["sha"], "")):
            texts[document["sha"]] = body
    return texts, files


def overlap(left, right):
    return len(left & right) / len(left | right) if left | right else 0.0


def cluster(signatures, threshold):
    """Documents gathered around the fullest copy of each form.

    Largest signature first, so a form takes shape around a complete copy of itself rather than around a
    torn one, and the walk is deterministic — a tie in size is settled by the sha so two runs over one
    folder produce the same forms in the same order.
    """
    forms = []
    for sha in sorted(signatures, key=lambda s: (-len(signatures[s]), s)):
        signature = signatures[sha]
        best, score = None, 0.0
        for form in forms:
            value = overlap(signature, form["seed"])
            if value > score:
                best, score = form, value
        if best is not None and score >= threshold and signature:
            best["members"].append(sha)
            best["fit"][sha] = round(score, 3)
        else:
            forms.append({"seed": signature, "members": [sha], "fit": {sha: 1.0}})
    return forms


def _parts_of(form, wording, texts):
    """One form's members split by whether they all carry the given wording."""
    held, apart = [], []
    for sha in form["members"]:
        body = texts.get(sha, "").upper()
        (held if all(word in body for word in wording) else apart).append(sha)
    return [(held, list(wording)), (apart, [f"not {word}" for word in wording])]


def apply_rules(forms, rules, texts, signatures):
    """Split forms the repair path has been told to split, and say on what.

    A rule is the shape a person's marks take once they have been turned into something the script can
    apply to every member rather than only to the ones that were looked at. Two kinds, because two things
    can be wrong: wording, when the members differ in what they say, and a raised threshold, when they
    differ only in degree and the first pass was too generous.
    """
    out = []
    for form in forms:
        rule = next((r for r in rules if r.get("form") == form["id"]), None)
        wording = [w.upper() for w in (rule or {}).get("wording") or []]
        threshold = (rule or {}).get("threshold")

        if rule and wording:
            parts = _parts_of(form, wording, texts)
        elif rule and threshold:
            # Re-run the same clustering over this form's members alone, held to a stricter bar.
            parts = [(tighter["members"], [f"threshold {threshold}"])
                     for tighter in cluster({s: signatures[s] for s in form["members"]}, threshold)]
        else:
            out.append(form)
            continue

        for members, why in parts:
            if not members:
                continue
            out.append({
                "seed": frozenset.intersection(*(signatures[s] for s in members)),
                "members": members,
                "fit": {s: form["fit"].get(s, 1.0) for s in members},
                "splitBy": why,
            })
    return out


def sweep(texts, counted, options):
    """What the folder looks like at other settings, since the right ones are folder-specific.

    There is no ground truth in a real run — nobody knows which documents share a form until somebody
    looks — so this reports shape rather than accuracy: how many forms each setting finds and how much
    of the folder the largest one holds. The review step is what turns that into a judgement.
    """
    print("what the folder looks like at other settings:\n")
    print(f"{'floor':>8s} {'words':>7s} {'threshold':>10s} {'forms':>7s} {'largest':>8s} {'alone':>7s}")
    for fraction in SWEEP_FLOORS:
        floor = max(2, round(fraction * len(texts)))
        signatures = {sha: mask_text.signature(text, counted, floor, options.vocabulary)
                      for sha, text in texts.items()}
        typical = sorted(len(s) for s in signatures.values())[len(signatures) // 2]
        for threshold in SWEEP_THRESHOLDS:
            forms = cluster(signatures, threshold)
            largest = max((len(f["members"]) for f in forms), default=0)
            alone = sum(1 for f in forms if len(f["members"]) == 1)
            print(f"{fraction:8.3f} {typical:7d} {threshold:10.2f} {len(forms):7d} "
                  f"{largest:8d} {alone:7d}")
    print("\nNothing was written. Pick a setting, run without --sweep, and let the review settle it.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--floor-fraction", type=float, default=0.025,
                        help="a word must appear on this share of the folder to count as printed on the "
                             "form rather than typed into it (default: 0.025)")
    parser.add_argument("--threshold", type=float, default=0.55,
                        help="how much of their form wording two documents must share to be one form "
                             "(default: 0.55)")
    parser.add_argument("--min-corpus", type=int, default=MIN_CORPUS,
                        help=f"below this many documents, grouping is skipped and said so "
                             f"(default: {MIN_CORPUS})")
    parser.add_argument("--header-lines", type=int, default=8,
                        help="lines at the top of a document never blanked in the structure view "
                             "(default: 8)")
    parser.add_argument("--sweep", action="store_true",
                        help="report what other settings would do and write nothing")
    options = parser.parse_args()

    # Windows consoles default to a codepage that cannot print customer file names.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    texts, files = texts_by_sha(session_dir)
    written = {"floor": None, "threshold": options.threshold, "floorFraction": options.floor_fraction,
               "documents": len(texts), "files": files, "headerLines": options.header_lines,
               "forms": [], "skipped": None}

    if len(texts) < options.min_corpus:
        written["skipped"] = (f"too small to group: {len(texts)} document(s), and grouping needs at "
                              f"least {options.min_corpus} before 'a word most documents share' means "
                              f"anything. Read them one at a time.")
        (session_dir / "FORMS.json").write_text(json.dumps(written, indent=2), encoding="utf-8")
        print(written["skipped"])
        print(f"\n-> {session_dir / 'FORMS.json'}")
        return

    counted = mask_text.frequency(list(texts.values()))
    options.vocabulary = mask_text.vocabulary(list(texts.values()))
    floor = max(2, round(options.floor_fraction * len(texts)))

    if options.sweep:
        sweep(texts, counted, options)
        return

    signatures = {sha: mask_text.signature(text, counted, floor, options.vocabulary)
                  for sha, text in texts.items()}
    forms = cluster(signatures, options.threshold)
    forms.sort(key=lambda f: -len(f["members"]))
    for number, form in enumerate(forms, 1):
        form["id"] = f"f{number:02d}"

    rules = (json.loads((session_dir / "SPLIT_RULES.json").read_text(encoding="utf-8")).get("rules")
             if (session_dir / "SPLIT_RULES.json").is_file() else None)
    if rules:
        forms = apply_rules(forms, rules, texts, signatures)
        forms.sort(key=lambda f: -len(f["members"]))
        for number, form in enumerate(forms, 1):
            form["id"] = f"f{number:02d}"
        print(f"{len(rules)} split rule(s) applied\n")

    written["floor"] = floor
    written["forms"] = [{
        "id": form["id"],
        "members": sorted(form["members"]),
        "fit": {sha: form["fit"][sha] for sha in sorted(form["members"])},
        "wording": sorted(form["seed"]),
        **({"splitBy": form["splitBy"]} if form.get("splitBy") else {}),
    } for form in forms]
    (session_dir / "FORMS.json").write_text(json.dumps(written, indent=2), encoding="utf-8")

    print(f"{len(texts)} document(s) in {files} file(s) fall into {len(forms)} form(s), "
          f"at a floor of {floor} document(s) and a threshold of {options.threshold:.2f}\n")
    print(f"{'form':>6s} {'documents':>10s} {'fit':>6s}  shared wording")
    for form in forms[:SAMPLE]:
        fit = sum(form["fit"].values()) / len(form["fit"])
        print(f"{form['id']:>6s} {len(form['members']):10d} {fit:6.0%}  "
              f"{' '.join(sorted(form['seed'])[:8])[:60]}")
    if len(forms) > SAMPLE:
        alone = sum(1 for f in forms[SAMPLE:] if len(f["members"]) == 1)
        print(f"  ... and {len(forms) - SAMPLE} more form(s), {alone} of them holding one document")
    print(f"\n-> {session_dir / 'FORMS.json'}")


if __name__ == "__main__":
    main()
