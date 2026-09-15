# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdfium2", "pillow"]
# ///
"""Build the page a person checks the run on: each composition beside the page it was read from.

Usage:
    uv run build_review_page.py <session_dir> <documents_folder> [--out <dir>] [--scale 2.0]

Reads <session_dir>/COMPOSITIONS.json and writes <out>/index.html with <out>/pages/*.png beside it,
defaulting to <session_dir>/review.

One card per material, a screenful tall: the table on the left, the rendered source page on the right,
the folders the candidates came from under the table. Checking a transcription means looking at the
table and the page at once, and a card that makes you scroll between them is a card nobody checks.

Which page to render is decided by looking for that material's own ingredient names and a composition
heading, page by page. An SDS repeats its ingredient names in section 8 and section 11, so a picture of
the first page that mentions them is usually a picture of the wrong table.

Open it over HTTP rather than as a file:// path if the viewer will not load the images -
`python3 -m http.server` in <out> is enough.
"""

import argparse
import html
import json
import re
from pathlib import Path

import pypdfium2

# Pages that discuss the substance rather than list what is in it. Without this the toxicology section
# outscores the composition on word count alone, because it names every ingredient too.
ELSEWHERE = re.compile(
    r"toxicological|stability and reactivity|physical and chemical properties|transport information|"
    r"disposal considerations|exposure controls|accidental release|fire[- ]fighting|first[- ]aid", re.I)
HEADING = re.compile(
    r"composition\s*[/:]?\s*information|information on ingredients|composition breakdown|"
    r"product composition|ingredient declaration|ingredient list|inci breakdown|components \(inci|"
    r"\bsection\s*3\b", re.I)


def page_texts(pdf):
    out = []
    for number in range(len(pdf)):
        try:
            out.append(pdf[number].get_textpage().get_text_range() or "")
        except Exception:
            out.append("")
    return out


def score(text, ingredients):
    """How much this page looks like the composition these rows were read off."""
    lowered = text.casefold()
    points = sum(5 for name in ingredients
                 if re.split(r"[/(,]", name)[0].strip().casefold()[:14] in lowered)
    if HEADING.search(text):
        points += 8
    if re.search(r"\bCAS\b", text):
        points += 2
    if re.search(r"\d\s*[-–]\s*\d+\s*%|\d+(\.\d+)?\s*%", text):
        points += 1
    if ELSEWHERE.search(text) and not HEADING.search(text):
        points -= 10
    return points


def render(source, out_dir, code, ingredients, scale):
    """The page the composition is on, and the one after it where the table runs on."""
    images = []
    pdf = pypdfium2.PdfDocument(str(source))
    try:
        scores = [score(text, ingredients) for text in page_texts(pdf)]
        best = max(range(len(scores)), key=lambda i: scores[i]) if scores else 0
        wanted = {best}
        # Only where a table really continues: these forms carry blank continuation sheets, and a
        # picture of an empty grid is worse than no second picture.
        if best + 1 < len(scores) and scores[best + 1] >= 5:
            wanted.add(best + 1)
        for number in sorted(wanted):
            out = out_dir / f"{code}_p{number + 1}.png"
            if not out.is_file():
                pdf[number].render(scale=scale).to_pil().save(out)
            images.append(f"pages/{out.name}")
    finally:
        pdf.close()
    return images


STYLE = """
  :root { color-scheme: light; }
  /* Each card is a screenful, and scrolling settles on whichever one is nearest - the page reads as one
     composition at a time rather than as a continuous list. */
  html { scroll-snap-type: y mandatory; }
  body { margin: 0; padding: 24px; font: 14px/1.45 -apple-system, "Segoe UI", system-ui, sans-serif;
         color: #17181c; background: #fafaf8; }
  h1 { font-size: 20px; margin: 0 0 20px; font-weight: 600; }
  section { background: #fff; border: 1px solid #e3e3df; border-radius: 6px; padding: 16px 18px;
            margin-bottom: 18px; height: 80vh; box-sizing: border-box; display: flex;
            flex-direction: column; scroll-snap-align: center; overflow: hidden; }
  h2 { font-size: 15px; margin: 0 0 12px; font-weight: 600; }
  /* The columns stretch rather than sitting at the top: a grid item only as tall as its content gives
     the page image no height to measure itself against, and it renders full size. */
  .split { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; flex: 1; min-height: 0; }
  .left { min-height: 0; overflow-y: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th { text-align: left; font-weight: 600; color: #6b6d75; border-bottom: 1px solid #e3e3df;
       padding: 5px 8px 5px 0; white-space: nowrap; }
  td { padding: 5px 8px 5px 0; border-bottom: 1px solid #f0f0ec; vertical-align: top; }
  td.n, td.c { white-space: nowrap; font-variant-numeric: tabular-nums; }
  td.c { color: #6b6d75; }
  .folders { margin: 12px 0 0; font-size: 12px; color: #6b6d75; }
  .folders span { display: block; }
  .src { margin: 8px 0 0; font-size: 12px; color: #8a8c94; word-break: break-word; }
  .right { display: flex; flex-direction: column; min-height: 0; min-width: 0; }
  .shots { display: flex; gap: 10px; flex: 1; min-height: 0; justify-content: center;
           align-items: center; }
  /* The link is not a box: with the anchor in the chain the image measures itself against something of
     auto height and renders full size. `display: contents` puts the image straight into the flex row,
     where the two maximums below bound it in both directions. */
  .shots a { display: contents; }
  .shots img { max-height: 100%; max-width: 100%; width: auto; height: auto; box-sizing: border-box;
               border: 1px solid #e3e3df; border-radius: 4px; display: block; }
  .shots.two img { max-width: calc(50% - 5px); }
  .none { color: #8a8c94; font-size: 13px; }
  .issue { color: #9a3412; font-size: 13px; }
  @media (max-width: 900px) {
    html { scroll-snap-type: none; }
    section { height: auto; }
    .split { grid-template-columns: 1fr; }
    .shots { flex-wrap: wrap; }
    .shots img { max-height: none; width: 100%; }
  }
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("documents_folder", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--scale", type=float, default=2.0)
    args = parser.parse_args()

    out_dir = args.out or (args.session_dir / "review")
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    state = json.loads((args.session_dir / "COMPOSITIONS.json").read_text(encoding="utf-8"))
    cell = lambda value: "" if value is None else html.escape(str(value))

    parts, rendered = [], 0
    for material in sorted(state["materials"], key=lambda m: m["identifier"]):
        source = args.documents_folder / material["sourcePath"]
        code = re.sub(r"[^A-Za-z0-9_.-]", "_", material["identifier"])
        images, note = [], ""
        if source.is_file():
            try:
                images = render(source, pages_dir, code,
                                [row["ingredient"] for row in material["rows"]], args.scale)
                rendered += 1
            except Exception as error:
                note = f"could not render: {error}"
        else:
            note = "the source file is not where the run left it"

        rows = "".join(
            f"<tr><td>{cell(r['ingredient'])}</td><td class=c>{cell(r['cas'])}</td>"
            f"<td class=c>{cell(r['ec'])}</td><td class=n>{cell(r['min'])}</td>"
            f"<td class=n>{cell(r['max'])}</td><td class=c>{cell(r['statedAs'])}</td></tr>"
            for r in material["rows"])
        folders = "".join(f"<span>{cell(folder)}</span>"
                          for folder in material.get("sourceFolders") or [])
        shots = "".join(f'<a href="{i}" target="_blank"><img src="{i}" alt=""></a>' for i in images) \
            or f"<p class=none>{cell(note) or 'no source page'}</p>"
        printed = material.get("documentDate") or {}
        stamp = f" &middot; {cell(printed.get('written'))} ({cell(printed.get('kind'))})" \
            if printed.get("written") else ""
        parts.append(f"""<section>
  <h2>{cell(material['identifier'])} &middot; {cell(material['itemName'])}</h2>
  <div class=split>
    <div class=left>
      <table>
        <thead><tr><th>Name</th><th>CAS</th><th>EC</th><th>min %</th><th>max %</th>
        <th>stated as</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <p class=folders>{folders}</p>
    </div>
    <div class=right>
      <div class="shots{' two' if len(images) > 1 else ''}">{shots}</div>
      <p class=src>{cell(material['sourceFile'])}{stamp}</p>
    </div>
  </div>
</section>""")

    for issue in sorted(state["issues"], key=lambda i: i["identifier"]):
        parts.append(f"""<section>
  <h2>{cell(issue['identifier'])}</h2>
  <div class=split>
    <div class=left>
      <p class=issue>{cell(issue['why'])}</p>
      <p class=folders>{"".join(f"<span>{cell(name)}</span>"
                                for name in issue.get('candidates') or [])}</p>
    </div>
    <div class=right><div class=shots><p class=none>no composition document</p></div></div>
  </div>
</section>""")

    page = ("<!doctype html>\n<meta charset=\"utf-8\">\n"
            "<title>Raw material compositions</title>\n<style>" + STYLE + "</style>\n"
            "<h1>Raw material compositions</h1>\n" + "\n".join(parts) + "\n")
    (out_dir / "index.html").write_text(page, encoding="utf-8")

    print(f"{len(state['materials'])} composition(s) and {len(state['issues'])} issue(s) on the page, "
          f"{rendered} with a rendered source page")
    print(f"\n-> {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
