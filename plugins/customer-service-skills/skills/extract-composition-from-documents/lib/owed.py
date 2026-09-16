"""What a material still owes somebody, after its composition has been verified.

A material can carry a clean, checked composition and still be incomplete. The workbook and the review
page both have to say so, in the same words, or the two disagree about the same run - and they used to,
because each decided for itself when a short answer was worth mentioning and one of them got it wrong.

Deliberately free of dependencies, like `signals`: the review page runs under `uv` and cannot drag the
rest of the lib in behind it.
"""


def owed_on(material):
    """[(what it is about, what somebody has to do about it)] for one verified material.

    Both kinds are reported, never one or the other. A reader that withheld a row it could not carry
    may *also* have returned far less than the page holds, and the earlier version suppressed the
    second whenever the first was present - so a material withholding one row of eighteen said one row
    was missing and stayed quiet about the other thirteen.
    """
    owed = []
    for entry in material.get("withheld") or []:
        missing = "" if entry.get("inDocument") else " (the line it names is not in the document)"
        owed.append((entry.get("ingredient") or "",
                     f"the reader could not carry this row: {entry.get('why') or 'no reason given'}"
                     f"{missing}"))
    return owed
