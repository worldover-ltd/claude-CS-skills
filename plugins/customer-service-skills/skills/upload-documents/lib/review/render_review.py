"""Put the samples inside the page, so the page needs nothing else to open.

Usage:
    python3 render_review.py <session_dir> [--template <path>] [--out review.html]

Reads `REVIEW.json` and the template beside this skill's assets, and writes one self-contained HTML file.
Publish that file as an Artifact; a strict policy blocks it from fetching anything, which is why every
rendered page travels inside it as a data URI and the whole thing runs to several megabytes.

Nothing else should ever write that file. It is too large to open, read or edit as text, and every tool
that tries will spend its context on base64.
"""

import argparse
import json
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent.parent / "assets" / "review" / "template.html"
PLACEHOLDER = "__DATA__"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--out", default="review.html")
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    manifest = options.session_dir / "REVIEW.json"
    if not manifest.is_file():
        raise SystemExit(f"missing REVIEW.json in {options.session_dir} — build_review.py has not run")
    if not options.template.is_file():
        raise SystemExit(f"missing template: {options.template}")

    body = options.template.read_text(encoding="utf-8")
    if PLACEHOLDER not in body:
        raise SystemExit(f"{options.template.name} has no {PLACEHOLDER} to put the samples in")

    # A JSON block inside a script tag ends at the first `</script>` in it whatever the quoting, and the
    # two line separators are line breaks to a JavaScript parser but not to JSON.
    data = manifest.read_text(encoding="utf-8")
    for character, escaped in (("<", "\\u003c"), (" ", "\\u2028"), (" ", "\\u2029")):
        data = data.replace(character, escaped)

    out = options.session_dir / options.out
    out.write_text(body.replace(PLACEHOLDER, data), encoding="utf-8")
    print(f"-> {out} ({out.stat().st_size / 1024 / 1024:.1f} MB)")
    print("Publish this file as an Artifact, then paste what the page copies back into the run.")


if __name__ == "__main__":
    main()
