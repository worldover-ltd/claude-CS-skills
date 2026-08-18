# Putting documents in front of a person

**No step reaches this.** It confirmed the grouping until `docs/adr/0007` took that step out, and it is
kept whole — this file, `lib/review/`, and `assets/review/` — for the next pile this skill needs eyes
on. Read it when you are building that; a run does not.

A published page that shows samples of each *form* and takes one judgement per document: does this belong
with the others.

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

## The three blocks, and why they are not one

Each form shows samples in three labelled strips, and the distinction is load-bearing:

- **A fair sample** — chosen at random. The only block a failure rate is ever counted from.
- **Least convincing members** — whatever joined the form on the thinnest overlap, shown because that is
  where a wrong grouping hides. Never counted.
- **Least and most filled in** — both ends of how much was *typed into* the form. Never counted.

The third block exists because `fit` cannot see a value split, and this was measured rather than assumed.
On the form holding 45 Product Specifications and 23 Certificates of Analysis:

```
Certificate of Analysis (CoA)   n= 23   fit mean=0.806
Product Specification           n= 45   fit mean=0.795
```

Choosing by fit at either end returns the form's own 66/34 mixture — the two are one form precisely
because the words marking a filled-in sheet fall below the mask floor. So this strip is chosen by digit
density instead, which tracks what was typed rather than what was printed, and it puts a blank sheet
beside a completed one.

Mixing the blocks is a real mistake and not an obvious one. A strip that front-loads the worst members
makes a good form look bad, and the better the choosing algorithm gets at surfacing errors, the worse
every form scores. `read_verdict.py` computes the rate from the fair block alone.

Sizes are `--random` (8), `--suspect` (6) and `--filled` (4) per form; no member is shown twice, so a
small form runs out and simply shows fewer. A published page holds about 16 MB and scans are what fill it,
so `build_review.py` warns when the manifest gets close; lower the counts or `--width`.

## What the person does

Two things, and the page asks for both:

- **Mark the documents that do not belong.** One action per card, and anything left alone counts as
  belonging. Marking only the wrong ones is far less work than confirming every right one, and the thing
  being measured is how few are wrong.
- **Give each form a verdict on two axes.** Does the *grouping* hold, and do the *title and description*
  fit. They are separate because a form can be perfectly grouped and badly named — and a bad name poisons
  the classification step, which uses the description as its check.

The grouping axis takes **three** answers, and the middle one is easy to miss:

| answer | means | what happens |
| --- | --- | --- |
| holds | all one form | the form is answered once, for all its members |
| same paper, different documents | one form, and the app calls them different things | the form stands; its documents are read one at a time |
| more than one form here | these are not all the same stationery | the form is repaired by a wording rule, or dissolves |

Choosing the middle one opens a box for *what tells them apart*, in the person's own words — "Product
Specification where the results column is blank, Certificate of Analysis where it is filled". That
reaches the reading as data for that form alone and is never carried to another customer.

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
