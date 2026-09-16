"""CAS and EC numbers: are they well formed, and are they in the document?

Usage:
    python3 codes.py <text file>          list every CAS and EC number the text holds

Imported by collect_compositions.py, which asks two questions of every code a sub agent returns. Both
formats carry a check digit, so a mistyped digit is caught arithmetically rather than by eye - and this
folder's documents disagree with each other often enough that a code needs proof it came from the page:
one supplier's sheet gave Glyceryl Oleate as 91744-09-1 and a newer one as 25496-72-4, and only one of
those is in the document the row claims to come from.

A well-formed code that is not in the document is the failure this catches. Models know these numbers -
asked for the CAS of glycerin, one will answer 56-81-5 whether or not the page says so - so a code that
passes its checksum has proved nothing about where it came from.
"""

import argparse
import re
from pathlib import Path

CAS = re.compile(r"\b(\d{2,7})-(\d{2})-(\d)\b")
EC = re.compile(r"\b(\d{3})-(\d{3})-(\d)\b")

# The same two shapes, tolerating the spaces a conversion puts inside a number. One real row came out
# of MarkItDown as `8000-41-7; 98-55- 5; 138-87-4`, so the middle code was in the document and in no
# list the reader was given. Spaces and tabs only, never a line break: two cells of a table that
# happened to fall either side of one are not a number.
LOOSE = {
    "cas": re.compile(r"\b\d{2,7}[ \t]*-[ \t]*\d{2}[ \t]*-[ \t]*\d\b"),
    "ec": re.compile(r"\b\d{3}[ \t]*-[ \t]*\d{3}[ \t]*-[ \t]*\d\b"),
}
SPACES = re.compile(r"[ \t]+")


def cas_ok(value):
    """CAS check digit: each digit right to left times its position, modulo 10."""
    match = CAS.fullmatch((value or "").strip())
    if not match:
        return False
    digits = (match.group(1) + match.group(2))[::-1]
    total = sum(int(d) * (i + 1) for i, d in enumerate(digits))
    return total % 10 == int(match.group(3))


def ec_ok(value):
    """EC check digit: the six digits weighted 1..6, modulo 11."""
    match = EC.fullmatch((value or "").strip())
    if not match:
        return False
    digits = match.group(1) + match.group(2)
    total = sum(int(d) * (i + 1) for i, d in enumerate(digits))
    return total % 11 == int(match.group(3))


CHECKS = {"cas": cas_ok, "ec": ec_ok}


def shaped_like(text, kind):
    """Every run of characters shaped like a code of that kind, closed up. Nothing checked yet."""
    return [SPACES.sub("", match.group(0)) for match in LOOSE[kind].finditer(text or "")]


def from_cell(value, kind="cas"):
    """Every well-formed code of that kind in one cell, in the order the cell prints them.

    A composition's code column is not one code per row. A fragrance names the isomers it may contain
    and an INCI covers several registry entries, so a document really does print
    `138-86-3 5989-27-5 5989-54-8` against one ingredient. Nothing is chosen between them: which isomer
    is in this drum is not a question the page answers, and picking one would invent an answer.
    """
    return [code for code in shaped_like(value, kind) if CHECKS[kind](code)]


def everything_in(value):
    """Every code of either kind in a cell, as (kind, code).

    Both kinds, whichever column the cell came from. The two shapes are disjoint - `\\d{2,7}-\\d{2}-\\d`
    and `\\d{3}-\\d{3}-\\d` cannot both match one run - and that is exactly why asking only about the
    column's own kind leaves a hole: `5989-27-5 / EC 231-791-2` in a CAS cell answers for the CAS and
    says nothing about the EC number, which the workbook then prints unchecked.
    """
    out = []
    for kind in CHECKS:
        for code in shaped_like(value, kind):
            out.append((kind, code))
    return out


def cell_ok(value, kind="cas"):
    """Whether a whole cell is well formed: at least one code of its own kind, and every code passing.

    `cas_ok` asks this of a single code, and asking it of a cell is what refused
    `5989-27-5 or 7705-14-8` - which blocks the material, not the row. Every code still has to pass its
    own check digit, so a mistyped digit is caught exactly as before; what is no longer caught is a
    second number sitting beside the first.
    """
    return bool(shaped_like(value, kind)) and all(CHECKS[k](code) for k, code in everything_in(value))


def find(text, kind="cas"):
    """Every well-formed code of that kind in the text, in the order they appear.

    Screened by check digit rather than by pattern alone, because a document is full of numbers shaped
    like codes - phone numbers, order references, a date written 231-791-2 would not be, but a batch
    number can be. The checksum is what separates a code from a coincidence.

    Spaces inside a number are closed up first, and then the checksum decides. A conversion that broke
    `98-55-5` into `98-55- 5` otherwise hides it from every list built off this.
    """
    seen, out = set(), []
    for value in from_cell(text, kind):
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text_file", type=Path)
    args = parser.parse_args()
    text = args.text_file.read_text(encoding="utf-8")
    print("CAS: " + (", ".join(find(text, "cas")) or "none"))
    print("EC:  " + (", ".join(find(text, "ec")) or "none"))


if __name__ == "__main__":
    main()
