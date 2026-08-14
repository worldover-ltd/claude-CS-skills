"""Tell a form's own wording apart from what somebody typed into it.

A word printed on a blank form turns up on every copy of it; a word typed into one turns up on that copy
and few others. So how often a word appears across the folder is the whole test, and everything here is
built on that one count.

Two things read the result, and they must not be confused. The **signature** is the set of a document's
form words, which is what the clustering compares — it is never shown to anybody. The **structure view**
is the document's own text with the answers blanked out, in order, which is what a naming agent reads —
it is never compared. Order carries almost nothing for comparison, because OCR reads a skewed scan in a
different order each time; but it carries almost everything for reading.
"""

import re
from collections import Counter

WORD = re.compile(r"[A-Za-z]{3,}")
TOKEN = re.compile(r"[A-Za-z]+|[0-9][0-9.,/:%-]*|\S")
CASE_BOUNDARY = re.compile(r"([a-z])([A-Z])")
BLANK = "_"

# Long enough that splitting it is worth attempting, and that a false split is unlikely to matter.
JOINED = 12
# Parts a joined token may be broken into. Two is the common case (DOCNO), four covers a whole title.
MOST_PARTS = 6


def spaced(text):
    """Case boundaries treated as spaces, which is all OCR leaves of `DocNo` and `SupplierName`."""
    return CASE_BOUNDARY.sub(r"\1 \2", text or "")


def _split_joined(token, vocabulary):
    """`token` broken into words the folder uses elsewhere, or None where it cannot be.

    An all-caps run of letters carries no case boundary to cut on, so the only evidence available is
    that some other document in the same folder spaced the same words out. Longest match first, because
    the alternative finds `SPECIFICATION` inside `SPECIFICATIONS` and leaves an orphan `S`.
    """
    def walk(rest, depth):
        if not rest:
            return []
        if depth >= MOST_PARTS:
            return None
        for size in range(len(rest), 2, -1):
            head = rest[:size]
            if head == token:
                continue
            if head in vocabulary:
                tail = walk(rest[size:], depth + 1)
                if tail is not None:
                    return [head] + tail
        return None

    parts = walk(token, 0)
    return parts if parts and len(parts) > 1 else None


def _vocabulary(texts):
    """The words this folder writes as words, which is what a joined token can be split against."""
    seen = set()
    for text in texts:
        for word in WORD.findall(spaced(text)):
            seen.add(word.upper())
    return seen


def words(text, vocabulary=()):
    """Every word in this document, with joined tokens also counted as their parts.

    The joined token is kept alongside its parts rather than replaced by them, because the split is a
    guess made from other documents' spacing and a wrong one should not lose the evidence it was made
    from. Counting both costs nothing: whatever it does, it does to every document alike.
    """
    found = []
    for word in WORD.findall(spaced(text)):
        word = word.upper()
        found.append(word)
        if len(word) >= JOINED and vocabulary:
            found.extend(_split_joined(word, vocabulary) or ())
    return found


def frequency(texts):
    """How many documents each word appears on. The one number every decision here rests on."""
    vocabulary = _vocabulary(texts)
    counted = Counter()
    for text in texts:
        counted.update(set(words(text, vocabulary)))
    return counted


def signature(text, counted, floor, vocabulary=()):
    """The form words of one document: what is left once the folder's rare words are dropped.

    A set, deliberately. Two scans of one form come out of OCR in different reading orders, so anything
    that carries order — lines, runs of tokens — is comparing the scanner rather than the form. Measured
    on a real folder, a set separated same-form from different-form pairs by 28 points where 3-grams
    managed 5.
    """
    return frozenset(word for word in set(words(text, vocabulary)) if counted[word] >= floor)


def structure_view(text, keep, header_lines=8, vocabulary=()):
    """The document's own lines with everything outside `keep` blanked out.

    `keep` should be counted **inside the form**, not across the folder. A folder that is mostly one form
    puts every minority form's own wording under a folder-wide floor, so the documents whose description
    matters most come back blank. The header is never blanked at all: it holds the title, which is the
    single most useful line for naming and the one most likely to be rare.
    """
    lines = []
    for number, line in enumerate(spaced(text).split("\n")):
        if not line.strip():
            continue
        if number < header_lines:
            lines.append(re.sub(r"\s+", " ", line.strip()).upper())
            continue
        out = []
        for token in TOKEN.findall(line):
            upper = token.upper()
            if not re.fullmatch(r"[A-Za-z]{3,}", token):
                out.append(token if re.fullmatch(r"[^A-Za-z0-9]", token) else BLANK)
            elif upper in keep:
                out.append(upper)
            elif len(upper) >= JOINED and vocabulary and _split_joined(upper, vocabulary) and \
                    all(part in keep for part in _split_joined(upper, vocabulary)):
                out.append(upper)
            else:
                out.append(BLANK)
        lines.append(" ".join(out))
    return lines
