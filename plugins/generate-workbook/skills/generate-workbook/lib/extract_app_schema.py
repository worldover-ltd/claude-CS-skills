"""Extract tables, columns and foreign keys from a Worldmaker app's database schema.

Usage:
    python3 extract_app_schema.py <repo-or-file> <out_dir>

<repo-or-file> is either a WorldoverProd repo name (`mondial-app`), fetched with `gh`, or the path
to an already-downloaded `database.types.ts`.

Writes <out_dir>/APP_SCHEMA.json and prints one summary line per table. Runs the same on macOS,
Linux and Windows: no shell pipeline, no redirect, no platform-specific tools beyond `gh`.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

TYPES_PATH = "src/types/database.types.ts"

TABLE_RE = re.compile(r"^      (\w+): \{$")
BLOCK_RE = re.compile(r"^        (Row|Insert|Update|Relationships): (\{|\[)$")
COLUMN_RE = re.compile(r"^          (\w+)(\?)?: (.+?)$")
END_RE = re.compile(r"^        (\}|\])$")
TABLE_END_RE = re.compile(r"^      \}$")


def fetch(repo):
    """Read database.types.ts out of a WorldoverProd repo via the GitHub API."""
    if "/" not in repo:
        repo = f"WorldoverProd/{repo}"

    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/contents/{TYPES_PATH}",
                "-H",
                "Accept: application/vnd.github.raw",
            ],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        raise SystemExit("`gh` is not installed or not on PATH")
    except subprocess.CalledProcessError as error:
        message = error.stderr.decode("utf-8", "replace").strip()
        raise SystemExit(f"could not read {TYPES_PATH} from {repo}:\n{message}")

    return result.stdout.decode("utf-8")


def parse(text):
    lines = text.splitlines()

    start = next((i for i, line in enumerate(lines) if line.strip() == "Tables: {"), None)
    if start is None:
        raise SystemExit("no `Tables: {` block found — is this a Supabase types file?")

    tables = {}
    table = None
    block = None

    for line in lines[start + 1 :]:
        if table is None:
            match = TABLE_RE.match(line)
            if match:
                table = match.group(1)
                tables[table] = {"columns": {}, "required": [], "relationships": []}
            elif line.strip() in ("Views: {", "Functions: {", "Enums: {"):
                break
            continue

        if block is None:
            match = BLOCK_RE.match(line)
            if match:
                block = match.group(1)
            elif TABLE_END_RE.match(line):
                table = None
            continue

        if END_RE.match(line):
            block = None
            continue

        if block == "Row":
            match = COLUMN_RE.match(line)
            if match:
                name, _, type_text = match.groups()
                type_text = type_text.rstrip()
                tables[table]["columns"][name] = {
                    "type": type_text.replace(" | null", ""),
                    "nullable": "null" in type_text,
                }
        elif block == "Insert":
            match = COLUMN_RE.match(line)
            if match and match.group(2) is None:
                tables[table]["required"].append(match.group(1))
        elif block == "Relationships":
            stripped = line.strip()
            if stripped.startswith("columns:"):
                tables[table]["relationships"].append(
                    {"columns": json.loads(stripped.split(": ", 1)[1].rstrip(","))}
                )
            elif stripped.startswith("isOneToOne:"):
                tables[table]["relationships"][-1]["one_to_one"] = "true" in stripped
            elif stripped.startswith("referencedRelation:"):
                tables[table]["relationships"][-1]["references"] = stripped.split('"')[1]
            elif stripped.startswith("referencedColumns:"):
                tables[table]["relationships"][-1]["referenced_columns"] = json.loads(
                    stripped.split(": ", 1)[1].rstrip(",")
                )

    return tables


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)

    source, out_dir = sys.argv[1], Path(sys.argv[2])
    local = Path(source)
    text = local.read_text(encoding="utf-8") if local.is_file() else fetch(source)

    tables = parse(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "APP_SCHEMA.json").write_text(
        json.dumps(tables, indent=2), encoding="utf-8"
    )

    print(f"{len(tables)} tables -> {out_dir / 'APP_SCHEMA.json'}\n")
    print(f"{'table':<40} {'cols':>5} {'fks':>5}  references")
    for name, table in sorted(tables.items()):
        refs = sorted({r.get("references", "?") for r in table["relationships"]})
        print(
            f"{name:<40} {len(table['columns']):>5} {len(table['relationships']):>5}"
            f"  {', '.join(refs)}"
        )


if __name__ == "__main__":
    main()
