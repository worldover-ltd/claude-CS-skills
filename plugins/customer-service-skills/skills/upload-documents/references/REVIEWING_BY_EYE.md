# Putting documents in front of a person

A published page that shows samples of each *form* and takes one judgement per document: does this belong
with the others. Used to confirm the grouping before anything is classified, and reusable for any other
pile this skill needs eyes on.

The person is on the Customer Service team and is not a developer, so
`${CLAUDE_PLUGIN_ROOT}/docs/PRESENTING.md` governs how this is put to them.

## Build it

```sh
uv run --with pillow "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/review/build_review.py" ".workflow/active/${sessionId}"
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/review/render_review.py" ".workflow/active/${sessionId}"
```

The first writes `REVIEW.json`; the second folds it into `review.html`. Pillow is only needed where there
are rendered pages to shrink — without it the samples carry their first lines of text instead, and the
script says so rather than failing.

Then publish `review.html` as an Artifact and give the person the link.

**Never open `review.html` with any other tool.** Every sample travels inside it as a data URI, which puts
it at several megabytes of base64. `render_review.py` is the only thing that writes it and nothing should
read it.

## The two blocks, and why they are not one

Each form shows samples in two labelled strips, and the distinction is load-bearing:

- **A fair sample** — chosen at random. The only block a failure rate is ever counted from.
- **Least convincing members** — whatever joined the form on the thinnest overlap, shown first because
  that is where a wrong grouping hides. Never counted.

Mixing them is a real mistake and not an obvious one. A strip that front-loads the worst members makes a
good form look bad, and the better the choosing algorithm gets at surfacing errors, the worse every form
scores. `read_verdict.py` computes the rate from the fair block alone.

Sizes are `--random` (8) and `--suspect` (6) per form. A published page holds about 16 MB and scans are
what fill it, so `build_review.py` warns when the manifest gets close; lower the counts or `--width`.

## What the person does

Two things, and the page asks for both:

- **Mark the documents that do not belong.** One action per card, and anything left alone counts as
  belonging. Marking only the wrong ones is far less work than confirming every right one, and the thing
  being measured is how few are wrong.
- **Give each form a verdict on two axes.** Does the *grouping* hold, and do the *title and description*
  fit. They are separate because a form can be perfectly grouped and badly named — and a bad name poisons
  the classification step, which uses the description as its check.

## Read the answer back

The page copies prose for the person and a fenced ```form-review block for the run. Save what they paste
to a file and read it:

```sh
<interpreter> ".../lib/review/read_verdict.py" ".workflow/active/${sessionId}" "<the pasted file>"
```

Writes `REVIEW_RESULT.json`. A paste with no fenced block is **refused, not interpreted** — parsing the
prose would mean guessing, and a guess here silently changes which documents get read again. If the person
pastes only the readable half, ask for the rest; the page copies both together.

A verdict naming a form nobody was shown is refused too. That paste belongs to another run.

## The item contract

`REVIEW.json` is deliberately item-shaped rather than form-shaped, so the same page can carry any pile
this skill needs looked at — the exception list, the readings under the confidence floor, the documents
whose quotation did not hold up.

```json
{
  "documents": 1887,
  "shown": 95,
  "forms": [{
    "formId": "f01",
    "title": "Specifications and Analytical Report for Raw Materials",
    "description": "A controlled quality document template used to …",
    "documents": 68,
    "randomShown": 8,
    "samples": [{
      "sha": "3e12f5d3…", "block": "random", "name": "R0101166.pdf",
      "path": "C:\\folder\\R0101166.pdf", "fit": 0.8,
      "image": "<base64 JPEG, or null>",
      "lines": ["first lines of text, where there is no picture"]
    }]
  }]
}
```

`block` is `random` or `suspect`. `image` and `lines` are alternatives — a sample carries whichever it
has. Anything writing this file for another purpose fills the same fields and gets the same page.

## The page's own styling

`assets/review/template.html`, styled to `assets/review/plm-style.md`, which is the house design language
for anything this skill publishes. One thing that cannot be honoured: a published page is blocked from
fetching fonts, so the type is a system stack standing in for the brief's own faces.
