"""What a composition looks like on a page, in one place.

Imported by score_composition.py, which culls the folder down to a shortlist, and by
build_review_page.py, which decides which page of a PDF to render. Both ask the same question of a piece
of text - is this a composition? - and an earlier version of this answered it twice, with two regexes
that had drifted apart: one matched `ingredient list` and the other did not.

Deliberately free of dependencies, so the uv-run review page can import it without the rest of the lib
coming with it.
"""

import re
from pathlib import Path

# The headings suppliers print over a composition. Worth more than any other signal: a document saying
# "Composition / information on ingredients" is telling you what the table under it is.
HEADING = re.compile(
    r"composition\s*[/:]?\s*information|information on ingredients|composition breakdown|"
    r"product composition|ingredient declaration|ingredient list|inci breakdown|components \(inci|"
    r"\bsection\s*3\b|\bcomposition\b", re.I)

# Where a document discusses the substance rather than lists what is in it. An SDS names every
# ingredient again in its toxicology section, which otherwise wins on word count alone.
ELSEWHERE = re.compile(
    r"toxicological|stability and reactivity|physical and chemical properties|transport information|"
    r"disposal considerations|exposure controls|accidental release|fire[- ]fighting|first[- ]aid", re.I)

# A safety data sheet names itself, in whichever language it was written in. Held apart from the file
# name, because a sheet quoted inside another document says the same words.
SDS_TITLE = re.compile(
    r"safety\s+data\s+sheet|veiligheidsinformatieblad|sicherheitsdatenblatt|"
    r"fiche\s+de\s+donn[e\u00e9]es\s+de\s+s[e\u00e9]curit[e\u00e9]|ficha\s+de\s+datos\s+de\s+seguridad|"
    r"scheda\s+(?:di\s+)?dati\s+di\s+sicurezza", re.I)

# What the customer called the file. Precise where the text is not: over 3,771 sheets this fired on
# 59% of them and on none of 639 compositions.
SDS_FILE_NAME = re.compile(
    r"\b(?:m?sds|vib|sdb|fds)\b|veiligheids\w*|sicherheitsdatenblatt", re.I)

# The words around the phrase when the document is pointing at a sheet rather than being one.
SDS_CROSS_REFERENCE = re.compile(r"\b(?:see|refer|available|request|consult|zie|siehe|voir)\b", re.I)

SDS_TITLE_HEAD = 3000
SDS_TITLE_LINE = 70

PERCENT = re.compile(r"\d+(?:[.,]\d+)?\s*(?:[-\u2013]\s*\d+(?:[.,]\d+)?\s*)?%")
BALANCE = re.compile(r"\bbalance\b|\bto\s*100\s*%|\bq\.?s\.?\s*(?:to|ad)\b|\bad\s*100\b", re.I)
INCI = re.compile(r"\bINCI\b", re.I)
CODE_OR_PERCENT = re.compile(r"\b\d{2,7}-\d{2}-\d\b|\d+(?:[.,]\d+)?\s*%")


def file_key(path):
    """The one spelling of a path the passes join on.

    An extraction adopted from an earlier session stores whatever root that run was given, and this run
    was given its own. Joining on the raw string then matches nothing, which surfaces only as "N file(s)
    had no text to score" - the silent failure the reuse step exists to prevent.
    """
    try:
        return str(Path(path).resolve()).casefold()
    except (OSError, TypeError):
        return str(path).casefold()


def looks_like_sds(text, file_name=""):
    """Whether this file is a safety data sheet, and so never a composition's single source.

    An SDS section 3 answers a different question. Under CLP it lists the substances classified above
    their cut-off, so a sheet can be complete and correct and still omit the water, the solvent and
    everything else that is not hazardous. Read as a composition it produces one with holes in it, and
    on this customer's folder the sheets outnumber the composition statements six to one, so the
    shortlist fills with them.

    Two signals, measured against 3,771 files a classification run called SDS and 639 it called
    Composition. What the customer named the file catches 59% of the sheets and none of the
    compositions. The sheet's own title, standing on a line of its own rather than quoted inside a
    sentence, takes that to 96.2% for 1.9% of compositions wrongly banned - the twelve are dossiers
    that print the phrase as a heading over their own hazard summary.
    """
    if file_name and SDS_FILE_NAME.search(file_name):
        return True
    for line in (text or "")[:SDS_TITLE_HEAD].splitlines():
        stripped = line.strip(" |#*\t")
        if (SDS_TITLE.search(stripped) and len(stripped) <= SDS_TITLE_LINE
                and not SDS_CROSS_REFERENCE.search(stripped)):
            return True
    return False


def read_text(record):
    """What the extraction got out of one file, whichever way it got it.

    `fullTextFile` first, because an extraction made for classifying documents caps each one at a few
    thousand characters and a composition is rarely in the first of them. On the folder this came from,
    851 of 2310 documents were at the cap, and one material's whole ingredient table sat in the 19,889
    characters that had been trimmed - so the agent was asked to find a composition in text that no
    longer contained one.

    Lives here rather than in a scoring module because three passes need it and none of them is about
    scoring.
    """
    return join(*body_and_tables(record))


def body_and_tables(record):
    """The conversion and the tables apart, for a caller that has to treat them differently.

    `read_text` joins them, which is right for scoring and for the haystack a quote is checked against.
    A pass that takes a *slice* cannot use the joined text: the tables sit past the end of any window
    anchored on a heading, so slicing the join silently drops them.
    """
    body = ""
    for key in ("fullTextFile", "textFile", "ocrTextFile"):
        path = record.get(key)
        if path and Path(path).is_file():
            text = Path(path).read_text(encoding="utf-8")
            if text.strip():
                body = text
                break
    tables = ""
    path = record.get("tablesFile")
    if path and Path(path).is_file():
        tables = Path(path).read_text(encoding="utf-8").strip()
    return body, tables


def join(body, tables):
    """The conversion, then whatever tables were read out of the same PDF, labelled as tables.

    Appended rather than substituted, because the two finders disagree: over 150 pages carrying
    composition signals, pdfplumber produced a table on 92 and MarkItDown on 61, agreeing on 38. A
    composition flattened out of one may survive in the other, so a reader is given both.

    Joined here rather than in the pass that builds a task, because this same text is the haystack every
    quoted value is checked against. Hand a sub agent a table it can quote and check its quote somewhere
    else, and a correct row fails as unverifiable.
    """
    if not tables.strip():
        return body
    if not body.strip():
        return tables
    heading = "# Tables read from this document"
    return "\n\n".join([body.rstrip(), heading, tables])


def with_tables(body, record):
    """`join`, for a caller that has the body and the record rather than the tables."""
    return join(body, body_and_tables(record)[1])
