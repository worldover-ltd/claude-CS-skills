"""Is this line really in that document, or did an agent write it?

Imported by collect_compositions.py. Every row a composition sub agent returns carries the line it read
the row off, and every one of those lines is checked against the exact text the agent was shown. A
percentage nobody can trace to a line in the document is a percentage somebody invented, and it is
indistinguishable from a real one once it reaches a workbook.

Five tiers, the middle three being ways a faithful transcription still drifts from a PDF conversion:

  exact       in the text, character for character
  whitespace  there once runs of whitespace are collapsed - the conversion's line breaks re-flowed
  spacing     there once whitespace is removed - the extractor glued words together, `toRegulation`
  table       there once table pipes are removed too - the agent re-rendered a row's empty cells
  stitched    every word there, in order and close together, but not as one run - the agent joined a
              heading to the value beside it
  ABSENT      not there at all

None of the middle four forgives a different word or a different order, so an invented line cannot pass
any of them. `stitched` is weaker than the rest and kept separate for that reason: it says the words are
the document's own while the line is the agent's.
"""

import re

FLAT = re.compile(r"\s+")
WORD = re.compile(r"[^\W_]+", re.UNICODE)

TIERS = ("exact", "whitespace", "spacing", "table", "stitched")

flatten = lambda s: FLAT.sub(" ", s or "").strip().casefold()
despace = lambda s: re.sub(r"\s+", "", s or "").casefold()
# Markdown table pipes and emphasis: a PDF's table becomes a grid of cells here, and an agent copying a
# row rarely reproduces the empty ones. Stripping the punctuation still leaves the words and their order
# to match on, so an invented line cannot pass this.
bare = lambda s: re.sub(r"[\s|*_-]+", "", s or "").casefold()


def forms(text):
    """The four shapes of the document's text every reference is held against."""
    return text, flatten(text), despace(text), bare(text)


def stitched_in(reference, text):
    """True when every word of the reference is in the text, in order, within a tight span.

    An agent told to quote the line a row came from often returns the ingredient name joined to the
    figure printed beside it - `Behenyl Behenate 40-70` - where the document prints those in two table
    cells. The line is not in the document as written, so it fails every tier above, and the check then
    reports ABSENT and the material is blocked over a transcription that was right.

    Deliberately weaker evidence than the tiers above - the words are the document's, the line is not -
    but an invented quotation fails it, which is what the check exists for. The span cap is what keeps it
    honest: words scattered across four thousand characters are not a quotation of anything.
    """
    words = [w.casefold() for w in WORD.findall(reference or "")]
    if len(words) < 2:
        return False
    lowered = text.casefold()
    start, first = 0, None
    for word in words:
        found = lowered.find(word, start)
        if found < 0:
            return False
        if first is None:
            first = found
        start = found + len(word)
    return (start - first) <= max(len(reference) * 4, 120)


def check(reference, shapes):
    """Which tier finds this reference in the text, or ABSENT. `shapes` comes from forms()."""
    text, flat_text, despaced_text, bare_text = shapes
    if not (reference or "").strip():
        return "ABSENT"
    if reference in text:
        return "exact"
    if flatten(reference) and flatten(reference) in flat_text:
        return "whitespace"
    if despace(reference) and despace(reference) in despaced_text:
        return "spacing"
    if bare(reference) and bare(reference) in bare_text:
        return "table"
    if stitched_in(reference, text):
        return "stitched"
    return "ABSENT"
