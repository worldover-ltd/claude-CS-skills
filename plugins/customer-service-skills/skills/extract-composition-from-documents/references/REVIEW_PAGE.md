# The review page

`lib/build_review_page.py` writes a local page putting each composition beside the page of the PDF it
was read from. `assets/example-review.html` is what one looks like, with invented materials, so the
shape is visible without running anything.

It is base code on purpose. A run that needs a column the workbook does not carry, or a different way of
choosing which page to show, changes this script rather than working around it.

```sh
uv run "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/build_review_page.py" ".workflow/active/${sessionId}" "<documents folder>"
```

Writes `<session>/review/index.html` with `<session>/review/pages/*.png` beside it. `--out` puts it
somewhere else; `--scale` changes the render resolution, 2.0 by default and 2.5 for a small or dense
page.

## Reading it

One card per material, a screenful tall. Table on the left with the folders the candidates came from
under it; the rendered source page on the right with the file name and its date under it. Materials
carrying no composition get a card too, saying what stopped them and which files were considered — the
absences are the point of the review as much as the compositions are.

Scrolling settles on whichever card is nearest, so the page reads as one composition at a time. Click a
page to open the full render.

**Check the numbers against the picture, not against your expectations.** A row that disagrees with the
page is a recut (`apply_recut.py`); a row that agrees with the page but disagrees with what you know of
the material is a conversation with the supplier.

## Which page it renders

Not page one. Page one of a dossier is a cover sheet, and an SDS states its composition in section 3.
Every page is scored on the material's own ingredient names, a composition heading, a `CAS` column and
percentages — and penalised for the sections that discuss the substance rather than list it, because
toxicology names every ingredient too and otherwise wins on word count.

The page after the best one is rendered only where it also scores: these forms carry blank continuation
sheets, and a picture of an empty grid is worse than no second picture.

To change what it looks for, change `HEADING`, `ELSEWHERE` and the weights in `score()`. Two page
renders per material is the budget the layout assumes; more than two need the CSS below reworked.

## If the images do not appear

A viewer that will not load images from a `file://` page shows the tables and nothing else. Serve the
folder instead:

```sh
python3 -m http.server 8731 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8731/index.html`. The `pages/` folder can be deleted once the review is
done; the page is rebuilt from `COMPOSITIONS.json` whenever it is needed.

## Two things in the CSS that will bite

Both cost a round of "why is the image spilling out of its card", so they are commented in the script as
well as here.

- **The image needs a definite height to measure against.** `align-items: start` on the grid makes a
  column only as tall as its content, so `max-height: 100%` inside it resolves against nothing and the
  page renders at full size. The columns stretch instead, and the link is `display: contents` so the
  anchor is not a box in the chain either.
- **A border is outside the box unless you say otherwise.** `max-height: 100%` bounds the content box,
  so a 1px border puts every image 2px over its container. `box-sizing: border-box` on the image fixes
  it.

Colours follow `../../upload-documents/assets/review/plm-style.md`, which is the house design language
for anything these skills put in front of a person.
