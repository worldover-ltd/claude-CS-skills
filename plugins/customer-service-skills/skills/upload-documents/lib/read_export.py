"""Take the two files the customer's app agent exported, check them, and copy them into the session.

Usage:
    python3 read_export.py <workflow.json> <items.csv> <session_dir>

Writes <session_dir>/WORKFLOW.json and <session_dir>/ITEMS.csv — the names every later step reads —
and prints what the app actually holds: the tables documents can attach to, the identifier column each
one keys on, how many items each has, and every identifier held by more than one item.

Checks the two files against each other rather than trusting either alone: a template id a section
names has to exist, a table an item names has to be in the workflow, and one table cannot key on two
different identifier columns.
"""

import argparse
import shutil
import sys
from pathlib import Path

import item_index

SAMPLE = 10


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("workflow", type=Path, help="the exported *_DOCUMENT_UPLOAD_WORKFLOW_*.json")
    parser.add_argument("items", type=Path, help="the exported *_DOCUMENT_UPLOAD_ITEMS_*.csv")
    parser.add_argument("session_dir", type=Path)
    options = parser.parse_args()

    # Windows consoles default to a codepage that cannot print this summary's punctuation.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        app = item_index.load(options.workflow, options.items)
    except item_index.ExportError as error:
        raise SystemExit(f"the export cannot be used: {error}")

    if not app.items:
        raise SystemExit("the items file holds no rows the workflow recognises — check the pair match")

    # A uuid is stamped on both file names at export, so a stale pairing is visible before anything runs.
    workflow_tag = options.workflow.stem.rsplit("_", 1)[-1]
    items_tag = options.items.stem.rsplit("_", 1)[-1]
    if workflow_tag != items_tag:
        print(
            f"WARNING: these two files were exported separately — the workflow ends {workflow_tag!r} "
            f"and the items end {items_tag!r}. Ask for a matching pair before going on.\n"
        )

    session_dir = options.session_dir
    session_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(options.workflow, session_dir / "WORKFLOW.json")
    shutil.copyfile(options.items, session_dir / "ITEMS.csv")

    print(f"{len(app.document_templates)} document template(s), {len(app.item_templates)} item template(s)\n")

    for table, summary in app.counts().items():
        print(f"{table} — keyed on `{summary['identifierColumn']}`")
        print(f"  {summary['items']} item(s), {summary['distinctIdentifiers']} distinct identifier(s)")
        print(f"  item templates: {', '.join(summary['itemTemplates'])}")
        allowed = [t["name"] for t in app.templates_for(table)]
        print(f"  document templates: {', '.join(allowed) if allowed else '(none)'}")
        if summary["archived"]:
            print(f"  {summary['archived']} archived — documents for these go to the exception pile")
        if summary["blankIdentifier"]:
            print(f"  {summary['blankIdentifier']} with no identifier — no folder can match them")
        if summary["noTemplate"]:
            print(f"  {summary['noTemplate']} on no item template — their sections are unknown")
        if summary["collisions"]:
            shown = ", ".join(repr(v) for v in summary["collisions"][:SAMPLE])
            more = "" if len(summary["collisions"]) <= SAMPLE else f" ... and {len(summary['collisions']) - SAMPLE} more"
            print(f"  {len(summary['collisions'])} identifier(s) held by several items: {shown}{more}")
            print("    a folder named by one of these resolves to no item, so it needs the user's call")
        print()

    duplicates = app.duplicate_template_names()
    if duplicates:
        print(f"ONE NAME, SEVERAL TEMPLATES ({len(duplicates)}):")
        for name, ids in duplicates.items():
            print(f"  {name} — {len(ids)} records: {', '.join(ids)}")
        print("  the app holds these twice, so a classifier is offered the same name more than once and")
        print("  the two can sit in different sections. Merge them in the app, or say which one to use.\n")

    if app.problems:
        print(f"ROWS THE WORKFLOW DOES NOT EXPLAIN ({len(app.problems)}):")
        for problem in app.problems[:SAMPLE]:
            print(f"  {problem}")
        if len(app.problems) > SAMPLE:
            print(f"  ... and {len(app.problems) - SAMPLE} more")
        print()

    print(f"-> {session_dir / 'WORKFLOW.json'}")
    print(f"-> {session_dir / 'ITEMS.csv'}")


if __name__ == "__main__":
    main()
