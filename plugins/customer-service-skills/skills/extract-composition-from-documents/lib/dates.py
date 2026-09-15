"""Every date a document prints, with the word the document put in front of it.

Usage:
    python3 dates.py <text file>

Imported by plan_readings.py, which puts this list in front of the sub agent, and by
collect_compositions.py, which holds the agent's answer against it.

A bare date decides nothing. One folder's safety data sheet carries `Issue Date: 29/11/2021` beside
`Print Date: 30/05/2023`, and another is stamped 2025 over a revision history reading
`Version: 02 Mandatory Review - no changes to SDS` against content last edited in 2020. Taking the
largest number on the page as the document's age picks the wrong document in both, so what is extracted
here is the date *and its label*, and which label matters is the agent's judgement rather than this
script's.
"""

import argparse
import re
from datetime import date
from pathlib import Path

MONTHS = {m: n for n, m in enumerate(
    ("january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"), 1)}
for _name, _number in list(MONTHS.items()):
    MONTHS[_name[:3]] = _number
MONTHS["sept"] = 9
# Longest first, so `june` is not matched as `jun` with a stray `e` left over.
MONTH_WORDS = "|".join(sorted(MONTHS, key=len, reverse=True))

# Bounded so a date cannot be read out of the middle of a longer number: the CAS number 51981-21-6
# ends in something shaped exactly like 1981-21-6, and these documents are full of them.
NUMERIC = (r"(?<![\d/.\-])(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})"
           r"(?![\d/.\-])")
# The month has to be a month. `[A-Za-z]{3,9}` between two numbers also matches `12 and 2023`, and a
# supplier document has plenty of those.
WORDED = (rf"\d{{1,2}}\s+(?:{MONTH_WORDS})\.?\s+\d{{4}}"
          rf"|(?:{MONTH_WORDS})\.?\s+\d{{1,2}},?\s+\d{{4}}")
DATE = re.compile(rf"({NUMERIC}|{WORDED})", re.I)
# The words that precede a date and say what kind of date it is. Ordered longest first so that
# "date of revision" is not read as the bare "date" sitting inside it, and matched nearest-first below:
# `Version No: 6.1  Issue Date: 29/11/2021` holds two labels, and the date belongs to the closer one.
LABEL = re.compile(
    r"(date of issue|date of revision|revision date|review date|issue date|print date|printing date|"
    r"version date|preparation date|prepared on|valid since|valid from|supersedes|superseded|"
    r"last rev\.?|last revised|revised|revision|edition|version|issued|effective|date)"
    r"(?=\s*[:\-]?\s*[^\n]{0,24}$)", re.I)

KINDS = (
    ("review", ("review date",)),
    ("print", ("print date", "printing date")),
    ("revision", ("revision", "revised", "last rev", "date of revision", "supersede")),
    ("issue", ("issue", "issued", "effective", "valid since", "valid from", "prepared", "preparation")),
    ("edition", ("edition", "version")),
)


def kind_of(label):
    lowered = (label or "").casefold()
    for kind, words in KINDS:
        if any(word in lowered for word in words):
            return kind
    return "unlabelled"


def as_iso(text):
    """A sortable date, or None where the text is a date this cannot resolve without guessing.

    Day-first is assumed for an ambiguous numeric date, because these are Australian and European
    supplier documents. An unresolvable one still reaches the agent as text - the agent can read
    `10/06/2022` in the context of the page, which this cannot.
    """
    text = text.strip()
    worded = re.match(r"^(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})$", text)
    if worded:
        month = MONTHS.get(worded.group(2).casefold())
        return _iso(int(worded.group(3)), month, int(worded.group(1)))
    worded = re.match(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})$", text)
    if worded:
        month = MONTHS.get(worded.group(1).casefold())
        return _iso(int(worded.group(3)), month, int(worded.group(2)))
    parts = re.split(r"[./-]", text)
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    if len(parts[0]) == 4:
        return _iso(int(parts[0]), int(parts[1]), int(parts[2]))
    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    if year < 100:
        year += 2000 if year < 70 else 1900
    if day > 12 and month <= 12:
        return _iso(year, month, day)
    if month > 12 and day <= 12:
        return _iso(year, day, month)
    return _iso(year, month, day)


def _iso(year, month, day):
    try:
        resolved = date(year, month, day)
    except (TypeError, ValueError):
        return None
    # A supplier document is not from the year 3040. Numbers shaped like dates are everywhere in these
    # files - batch codes, phone numbers, a row of measurements - and an impossible year is the cheapest
    # way to tell one of those from a date somebody wrote.
    if not (1980 <= resolved.year <= date.today().year + 5):
        return None
    return resolved.isoformat()


def find(text, limit=40):
    """Every date in the text, each with the label in front of it and the kind that label names."""
    out, seen = [], set()
    for match in DATE.finditer(text or ""):
        written = match.group(0).strip()
        before = text[max(0, match.start() - 60):match.start()]
        found = list(LABEL.finditer(before))
        label = found[-1].group(1).strip() if found else ""
        key = (written, label.casefold())
        if key in seen:
            continue
        seen.add(key)
        iso = as_iso(written)
        # A numeric run that resolves to no real date is not a date at all - a CAS number, a batch code,
        # a row of measurements. A worded one is kept even unresolved, because `Sept 2023` is a date a
        # person can read off the page and this cannot.
        if iso is None and not re.search(r"[A-Za-z]", written):
            continue
        out.append({"written": written, "label": label, "kind": kind_of(label), "iso": iso})
        if len(out) >= limit:
            break
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text_file", type=Path)
    args = parser.parse_args()
    for entry in find(args.text_file.read_text(encoding="utf-8")):
        print(f"  {entry['iso'] or '?':12} {entry['kind']:11} {entry['label'] or '(no label)':18} "
              f"{entry['written']}")


if __name__ == "__main__":
    main()
