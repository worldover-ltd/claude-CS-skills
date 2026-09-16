"""Find an extraction of this folder somebody has already paid for, and say how much of it it covers.

Usage:
    python3 reuse_extraction.py <session_dir> <documents_folder> [--adopt <EXTRACTED.json>]

With no --adopt this writes nothing. It walks `.workflow/active/*/` beside the user's working directory,
opens every EXTRACTED.json it finds, and reports what fraction of the files under <documents_folder>
each one already holds text for.

Reading a folder of three thousand documents takes about half an hour, and on a machine where
`upload-documents` has run against the same folder that half hour is already spent. This is what finds
it - and, as importantly, what measures it: a session covering three quarters of the folder is worse
than no session at all if the quarter it misses is silently read as materials with no composition.

--adopt copies the named manifest in as this session's EXTRACTED.json and writes STILL_TO_EXTRACT.json,
a list of paths the extraction step takes as its input. --merge then folds what that run produced back
in, because the extractor writes a whole EXTRACTED.json of its own and would otherwise replace the
adopted one with only the leftovers - turning a reuse of three quarters of the folder into a run that
has read a quarter of it.

The join is on the resolved absolute path. A manifest's own `relativePath` is the bare file name where
the extractor was handed a list of files rather than a folder, so joining on that silently matches two
documents of the same name under different materials.
"""

import argparse
import json
from pathlib import Path


def key(path):
    """One spelling of a path, so two manifests written from differently-spelled roots still join."""
    try:
        return str(Path(path).resolve()).casefold()
    except (OSError, TypeError):
        return str(path).casefold()


def _cap(manifest_path):
    """The per-document character cap an earlier run used, where it used one."""
    try:
        return json.loads(Path(manifest_path).read_text(encoding="utf-8")).get("maxChars") or 0
    except (OSError, json.JSONDecodeError):
        return 0


def skill_version():
    """The plugin's own version, so a manifest can be held against the skill reading it."""
    plugin = Path(__file__).resolve().parents[3] / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(plugin.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None


def provenance(manifest, running, want=None):
    """What to say out loud about an extraction before anybody adopts it, or "" when there is nothing.

    Warns, never refuses. Not every version bump changes what a run writes, and re-reading three
    thousand documents over a patch release is worse than the thing it guards against. The person
    adopting knows what changed between two versions; this pass only knows the numbers differ.
    """
    stamp = manifest.get("producedBy")
    if not stamp:
        return (f"That extraction carries no version — it was made before extractions recorded one, "
                f"so it is older than {running}.")

    said = []
    was = stamp.get("skillVersion")
    if was != running:
        said.append(f"That extraction was read by version {was}. You are on {running}.")
    for name, wanted in (want or {}).items():
        had = (stamp.get("flags") or {}).get(name)
        if had != wanted:
            said.append(f"It was read with {name}={had!r}; this run wants {wanted!r}.")
    return " ".join(said)


def covered(manifest_path, wanted):
    """Which of the wanted paths this manifest already holds usable text for."""
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(), 0
    hits, records = set(), 0
    for record in manifest.get("documents") or []:
        records += 1
        source = record.get("textFile") or record.get("ocrTextFile")
        if not source or not Path(source).is_file():
            continue
        if "path" not in record:
            continue
        resolved = key(record["path"])
        if resolved in wanted:
            hits.add(resolved)
    return hits, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("documents_folder", type=Path)
    parser.add_argument("--adopt", type=Path, default=None)
    parser.add_argument("--merge", type=Path, default=None,
                        help="fold a second EXTRACTED.json into this session's, newest record winning")
    parser.add_argument("--workflow-root", type=Path, default=Path(".workflow/active"))
    args = parser.parse_args()

    folder = args.documents_folder.resolve()
    wanted = {key(path) for path in folder.rglob("*") if path.is_file()}
    if not wanted:
        raise SystemExit(f"no files under {folder}")

    if args.merge:
        into = args.session_dir / "EXTRACTED.json"
        held = json.loads(into.read_text(encoding="utf-8")) if into.is_file() else {"documents": []}
        records = {key(r["path"]): r for r in held.get("documents") or [] if "path" in r}
        added = json.loads(Path(args.merge).read_text(encoding="utf-8"))
        before = len(records)
        for record in added.get("documents") or []:
            if "path" in record:
                records[key(record["path"])] = record
        held["documents"] = [records[k] for k in sorted(records)]
        into.write_text(json.dumps(held, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{len(records)} file(s) in this session's extraction "
              f"({before} held, {len(records) - before} new)")
        missing = len(wanted - set(records))
        print(f"  {len(wanted) - missing} of {len(wanted)} file(s) in the folder now have a record")
        return

    if args.adopt:
        hits, _ = covered(args.adopt, wanted)
        args.session_dir.mkdir(parents=True, exist_ok=True)
        (args.session_dir / "EXTRACTED.json").write_text(
            Path(args.adopt).read_text(encoding="utf-8"), encoding="utf-8")
        by_key = {key(path): path for path in folder.rglob("*") if path.is_file()}
        missing = sorted(str(by_key[k]) for k in wanted - hits)
        listing = args.session_dir / "STILL_TO_EXTRACT.json"
        listing.write_text(json.dumps(missing, indent=1), encoding="utf-8")
        print(f"adopted {args.adopt}")
        print(f"  {len(hits)} of {len(wanted)} file(s) already have text")
        print(f"  {len(missing)} still to read -> {listing}")
        return

    found = sorted(Path(args.workflow_root).glob("*/EXTRACTED.json"))
    if not found:
        print(f"no earlier extraction under {args.workflow_root} - this folder has not been read here")
        return
    print(f"{len(found)} earlier extraction(s), against {len(wanted)} file(s) in this folder:\n")
    for manifest_path in found:
        hits, records = covered(manifest_path, wanted)
        share = 100.0 * len(hits) / len(wanted)
        print(f"  {share:5.1f}%  {len(hits)} of {len(wanted)} covered   "
              f"({records} record(s) in it)   {manifest_path}")
        # A run made for classifying documents caps the text it keeps. The whole conversion is still on
        # disk under `fullTextFile` and this skill reads that, so the cap is survivable - but a manifest
        # without the uncapped files beside it is not, and that is worth knowing before adopting it.
        cap = _cap(manifest_path)
        if cap:
            print(f"         capped at {cap} characters a document; the uncapped text is read where "
                  f"the extraction left it beside the manifest")
        try:
            manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {}
        said = provenance(manifest, skill_version())
        if said:
            print(f"         {said}")
    print("\nAdopt one with --adopt <path>, which also lists what it does not cover.")


if __name__ == "__main__":
    main()
