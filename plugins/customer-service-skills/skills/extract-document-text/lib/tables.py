"""Turn the tables on a page into Markdown, without deciding whether they look like tables.

MarkItDown finds tables by clustering words, and pdfplumber finds them by ruling lines and alignment.
Neither is a superset of the other. Measured over 150 pages carrying composition signals, sampled from
63,686 customer PDFs: pdfplumber produced a table on 92 and MarkItDown on 61, agreeing on only 38. Fifty
four pages carried a table that the conversion alone never showed.

So this does not replace what MarkItDown wrote — it is written beside it, and a reader gets both. What
arrives here has already been found by a table extractor; the shape is not judged again. Only what cannot
be rendered at all is dropped: fewer than two filled rows, or fewer than two columns. A table wrongly
kept is noise a reader skips. A table wrongly dropped is a composition nobody can see.

`docs/adr/0011` is the argument.
"""

import re

SEPARATOR = re.compile(r"^\|(?: --- \|)+$", re.M)


def one_line(value):
    """One cell as a single line, safe to sit between pipes."""
    if value is None:
        return ""
    return " ".join(str(value).split()).replace("|", r"\|")


def worth_keeping(rows):
    """Whether these rows can be rendered as a table at all.

    Not whether they look like one. Two rows is a header and a value; one column is a list.
    """
    if not rows:
        return False
    filled = [row for row in rows if any(one_line(cell) for cell in row)]
    if len(filled) < 2:
        return False
    return max((len(row) for row in filled), default=0) >= 2


def as_markdown(rows):
    """Rows to a Markdown pipe table, the first row its header."""
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    lines = []
    for index, row in enumerate(rows):
        cells = [one_line(cell) for cell in row] + [""] * (width - len(row))
        lines.append("| " + " | ".join(cells) + " |")
        if index == 0:
            lines.append("| " + " | ".join(["---"] * width) + " |")
    return "\n".join(lines)


def render(by_page):
    """Every page's tables as one Markdown section, with how many survived.

    The count comes back with the text rather than being recovered from it, so nobody downstream has to
    parse this module's own output to learn what it wrote.
    """
    parts = []
    kept_count = 0
    for page in sorted(by_page):
        kept = [rows for rows in by_page[page] if worth_keeping(rows)]
        if not kept:
            continue
        kept_count += len(kept)
        parts.append(f"## Tables on page {page}")
        parts.extend(as_markdown(rows) for rows in kept)
    return "\n\n".join(parts), kept_count


def count_in(text):
    """How many tables a rendered section holds, for a run reusing one it wrote earlier.

    Counts separator rows, which `as_markdown` writes exactly once per table and which no data row can
    imitate — the pattern is anchored at both ends.
    """
    return len(SEPARATOR.findall(text or ""))
