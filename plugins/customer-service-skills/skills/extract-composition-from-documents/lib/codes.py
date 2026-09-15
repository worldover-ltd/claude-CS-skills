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


def find(text, kind="cas"):
    """Every well-formed code of that kind in the text, in the order they appear.

    Screened by check digit rather than by pattern alone, because a document is full of numbers shaped
    like codes - phone numbers, order references, a date written 231-791-2 would not be, but a batch
    number can be. The checksum is what separates a code from a coincidence.
    """
    pattern, valid = (CAS, cas_ok) if kind == "cas" else (EC, ec_ok)
    seen, out = set(), []
    for match in pattern.finditer(text or ""):
        value = match.group(0)
        if valid(value) and value not in seen:
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
