"""Profile a spreadsheet, so a candidate identifier column is a count rather than an impression.

Usage:
    python3 profile_spreadsheet.py <file.xlsx|file.csv|file.tsv> [--max-rows 20000]

Per sheet, prints the row count, the header row it settled on, and per column the filled count against
the distinct count. A column whose distinct count equals the filled count and covers every row is a
candidate identifier.

Reads values only — the contents themselves come from the extraction step, not from here.
"""

import argparse
import csv
import sys
from pathlib import Path

SAMPLE_VALUES = 3


def cell_text(value):
    if value is None:
        return ""
    return str(value).strip()


def header_index(rows):
    """The first row with two or more filled cells is the header; nothing above it is data."""
    for index, row in enumerate(rows):
        if sum(1 for cell in row if cell) >= 2:
            return index
    return 0


def profile(name, rows, capped):
    if not rows:
        print(f"\n## {name}\n  empty")
        return

    start = header_index(rows)
    header = rows[start]
    body = rows[start + 1 :]
    width = max((len(row) for row in rows), default=0)
    names = [cell_text(header[i]) if i < len(header) else "" for i in range(width)]

    print(f"\n## {name}")
    print(f"  {len(body)} data rows, {width} columns, header on row {start + 1}" + (" (sampled)" if capped else ""))
    if start:
        print(f"  rows 1-{start} sit above the header — check what they are before ignoring them")

    for index in range(width):
        values = [cell_text(row[index]) if index < len(row) else "" for row in body]
        filled = [value for value in values if value]
        distinct = len(set(filled))
        label = names[index] or f"(column {index + 1})"
        marker = ""
        if filled and distinct == len(filled) and len(filled) == len(body):
            marker = "  <- candidate identifier"
        samples = ", ".join(filled[:SAMPLE_VALUES])
        print(f"  {label}: {len(filled)}/{len(body)} filled, {distinct} distinct{marker}")
        if samples:
            print(f"      e.g. {samples}")


def read_delimited(path, max_rows):
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        rows = []
        for row in reader:
            rows.append([cell_text(cell) for cell in row])
            if len(rows) >= max_rows:
                return [(path.name, rows, True)]
    return [(path.name, rows, False)]


def read_workbook(path, max_rows):
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("openpyxl is not installed in this interpreter — the preflight step settles which one has it")

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = []
    for sheet in workbook.worksheets:
        rows, capped = [], False
        for row in sheet.iter_rows(values_only=True):
            rows.append([cell_text(cell) for cell in row])
            if len(rows) >= max_rows:
                capped = True
                break
        while rows and not any(rows[-1]):
            rows.pop()
        sheets.append((sheet.title, rows, capped))
    workbook.close()
    return sheets


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path)
    parser.add_argument("--max-rows", type=int, default=20000, help="rows read per sheet (default: 20000)")
    options = parser.parse_args()

    # Windows consoles default to a codepage that cannot print this summary's punctuation.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    path = options.path
    if not path.is_file():
        raise SystemExit(f"no such file: {path}")

    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        sheets = read_delimited(path, options.max_rows)
    elif suffix in {".xlsx", ".xlsm"}:
        sheets = read_workbook(path, options.max_rows)
    elif suffix == ".xls":
        raise SystemExit(".xls is the legacy format — ask the user to re-save it as .xlsx, then profile that")
    else:
        raise SystemExit(f"not a spreadsheet this profiles: {suffix}")

    print(f"{path.name}: {len(sheets)} sheet(s)")
    for name, rows, capped in sheets:
        profile(name, rows, capped)
    print("\nEvery sheet above counts — a workbook's second tab often holds the link table.")


if __name__ == "__main__":
    main()
