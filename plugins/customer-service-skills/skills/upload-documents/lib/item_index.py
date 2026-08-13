"""The app's own data, as the customer's app agent exported it.

Loads the two files `worldover-export-data-for-document-upload` produced — the workflow JSON and the
items CSV — and answers the question every later step asks of them: which item does this folder name
name?

Imported by read_export.py, check_branches.py and plan_batches.py, so the gate and the batching agree
on every match. A document filed against the wrong item is the failure this module exists to prevent,
so a name that matches two items resolves to neither.
"""

import csv
import json
import re
from pathlib import Path

TRUE = {"true", "t", "yes", "y", "1"}
ITEM_COLUMNS = ("table", "id", "identifier", "name", "template", "archived")


class ExportError(Exception):
    """The exported files cannot carry a run — the message says what to fix and where."""


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise ExportError(f"no file at {path}")
    except json.JSONDecodeError as error:
        raise ExportError(f"{Path(path).name} is not valid JSON: {error}")


def normalise(value):
    return " ".join(str(value or "").split())


class App:
    """The workflow and the items, joined and checked."""

    def __init__(self, workflow, items):
        self.document_templates = {}
        self.item_templates = {}
        self.tables = {}
        self.items = []
        self._exact = {}
        self._folded = {}
        self.problems = []
        self._load_workflow(workflow)
        self._load_items(items)

    # ---- the workflow -------------------------------------------------

    def _load_workflow(self, workflow):
        templates = workflow.get("documentTemplates")
        item_templates = workflow.get("itemTemplates")
        if not isinstance(templates, list) or not templates:
            raise ExportError("the workflow file carries no `documentTemplates`")
        if not isinstance(item_templates, list) or not item_templates:
            raise ExportError("the workflow file carries no `itemTemplates`")

        for entry in templates:
            identifier = normalise(entry.get("id"))
            name = normalise(entry.get("name"))
            if not identifier or not name:
                raise ExportError(f"a documentTemplates entry is missing an id or a name: {entry!r}")
            tables = {normalise(t) for t in entry.get("for_tables") or [] if normalise(t)}
            known = self.document_templates.setdefault(
                identifier, {"id": identifier, "name": name, "tables": set()}
            )
            known["tables"] |= tables

        for entry in item_templates:
            name = normalise(entry.get("name"))
            table = normalise(entry.get("table"))
            column = normalise(entry.get("identifierColumn"))
            if not name or not table or not column:
                raise ExportError(
                    f"an itemTemplates entry needs a name, a table and an identifierColumn: {entry!r}"
                )
            sections = []
            for order, section in enumerate(entry.get("documentSections") or []):
                label = normalise(section.get("label"))
                ids = [normalise(i) for i in section.get("documentTemplates") or []]
                missing = [i for i in ids if i and i not in self.document_templates]
                if missing:
                    raise ExportError(
                        f"section {label!r} on {name!r} names document template id(s) the workflow "
                        f"does not list: {', '.join(missing)}"
                    )
                sections.append({"label": label, "documentTemplates": ids, "sortOrder": order})
            self.item_templates[name] = {
                "name": name,
                "table": table,
                "identifierColumn": column,
                "sections": sections,
            }

            # The identifier column belongs to the item_kind's table, so every item_template on that
            # table has to name the same one or the sheet has no single identifier to key on.
            held = self.tables.setdefault(
                table, {"table": table, "identifierColumn": column, "itemTemplates": []}
            )
            if held["identifierColumn"] != column:
                raise ExportError(
                    f"table {table!r} is given two identifier columns — {held['identifierColumn']!r} "
                    f"and {column!r}. One column per table, or the workbook cannot key on it."
                )
            held["itemTemplates"].append(name)

    # ---- the items ----------------------------------------------------

    def _load_items(self, rows):
        for number, row in enumerate(rows, 2):
            table = normalise(row.get("table"))
            identifier = normalise(row.get("identifier"))
            template = normalise(row.get("template"))
            if not table:
                self.problems.append(f"items row {number} carries no table")
                continue
            if table not in self.tables:
                self.problems.append(f"items row {number}: table {table!r} is not in the workflow")
                continue
            if template and template not in self.item_templates:
                self.problems.append(
                    f"items row {number}: template {template!r} is not in the workflow"
                )
            item = {
                "table": table,
                "id": normalise(row.get("id")),
                "identifier": identifier,
                "name": normalise(row.get("name")),
                "template": template or None,
                "archived": normalise(row.get("archived")).lower() in TRUE,
            }
            self.items.append(item)
            if identifier:
                self._exact.setdefault((table, identifier), []).append(item)
                self._folded.setdefault((table, identifier.casefold()), []).append(item)

    # ---- what the run asks --------------------------------------------

    def templates_for(self, table):
        """The document templates the app allows on this table, as the classifier's closed list."""
        return [
            {"id": t["id"], "name": t["name"]}
            for t in sorted(self.document_templates.values(), key=lambda t: t["name"])
            if not t["tables"] or table in t["tables"]
        ]

    def sections_for(self, table):
        """Every item_template on this table with its sections, keyed by item_template name."""
        return {
            name: self.item_templates[name]["sections"]
            for name in self.tables.get(table, {}).get("itemTemplates", [])
        }

    def resolve(self, table, value):
        """(item, matched-how, (kind, why)) for one identifier value read off the tree.

        The kind is what the exception pile files it under, so a folder naming an archived item reads
        differently from one naming nothing at all.
        """
        value = normalise(value)
        if not value:
            return None, None, ("unidentified", "the branch rule yielded nothing")
        if table not in self.tables:
            return None, None, ("unmatched", f"table {table!r} is not in the workflow")

        found = self._exact.get((table, value))
        how = "exact"
        if not found:
            found = self._folded.get((table, value.casefold()))
            how = "case-insensitive"
        if not found:
            return None, None, ("unmatched", f"no {table} item has the identifier {value!r}")
        if len(found) > 1:
            names = ", ".join(f"{i['id']} ({i['name']})" for i in found[:3])
            return None, None, (
                "ambiguous",
                f"{len(found)} {table} items share the identifier {value!r}: {names}",
            )
        if found[0]["archived"]:
            return None, None, (
                "archived",
                f"the {table} item {value!r} ({found[0]['name']}) is archived",
            )
        return found[0], how, None

    def counts(self):
        """Per table: items, archived, distinct identifiers, and the identifiers held by several items."""
        summary = {}
        for table, held in sorted(self.tables.items()):
            rows = [i for i in self.items if i["table"] == table]
            collisions = sorted(
                {i["identifier"] for i in rows if len(self._exact.get((table, i["identifier"]), [])) > 1}
            )
            summary[table] = {
                "identifierColumn": held["identifierColumn"],
                "itemTemplates": held["itemTemplates"],
                "items": len(rows),
                "archived": len([i for i in rows if i["archived"]]),
                "blankIdentifier": len([i for i in rows if not i["identifier"]]),
                "noTemplate": len([i for i in rows if not i["template"]]),
                "distinctIdentifiers": len({i["identifier"] for i in rows if i["identifier"]}),
                "collisions": collisions,
            }
        return summary


def load(workflow_path, items_path):
    """Build an App from the two exported files."""
    workflow = _read_json(workflow_path)
    try:
        text = Path(items_path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ExportError(f"no file at {items_path}")

    reader = csv.DictReader(text.splitlines())
    missing = [c for c in ITEM_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ExportError(
            f"the items file is missing column(s): {', '.join(missing)}. "
            f"Its header must read: {','.join(ITEM_COLUMNS)}"
        )
    return App(workflow, list(reader))


# ---- reading identifiers off the tree ---------------------------------


def branch_for(relative_path, branches):
    """The branch with the longest matching prefix — a root-level branch uses an empty prefix."""
    matches = [b for b in branches if relative_path.startswith(b.get("pathPrefix", ""))]
    return max(matches, key=lambda b: len(b.get("pathPrefix", ""))) if matches else None


def identifier_for(relative_path, rule):
    """(value, why-not) — the identifier this document's branch rule yields, or why it yielded nothing."""
    parts = relative_path.split("/")
    folders, name = parts[:-1], parts[-1]
    kind = rule.get("type")

    if kind == "folderLevel":
        level = rule.get("level")
        if not isinstance(level, int) or level < 1:
            return None, f"folderLevel needs a level of 1 or more, got {level!r}"
        if level > len(folders):
            return None, f"only {len(folders)} folder level(s) above this file, rule wants level {level}"
        return folders[level - 1].strip(), None

    if kind == "fileName":
        pattern = rule.get("pattern")
        if not pattern:
            return None, "fileName rule carries no pattern"
        try:
            found = re.search(pattern, name)
        except re.error as error:
            return None, f"pattern {pattern!r} is not valid regex: {error}"
        if not found:
            return None, f"pattern {pattern!r} does not match {name!r}"
        return (found.group(1) if found.groups() else found.group(0)).strip(), None

    return None, f"unknown identifier rule type {kind!r}"


def excluded_paths(session_dir):
    """The relative paths the user decided not to migrate, or an empty set before the gate has run.

    One reader for EXCLUSIONS.json, because the two scripts that honour it — the legibility check and
    the hasher — otherwise each carry their own copy of its shape.
    """
    path = Path(session_dir) / "EXCLUSIONS.json"
    if not path.is_file():
        return set()
    listed = json.loads(path.read_text(encoding="utf-8")).get("files") or []
    return {row["relativePath"] for row in listed if row.get("relativePath")}
