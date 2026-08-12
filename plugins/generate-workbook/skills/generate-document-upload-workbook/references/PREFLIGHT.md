# Preflight

What a preflight step settles before a run commits to anything, and what it returns. Two questions, both
of them cheap, and each answered by a command that actually runs. It goes to **one sub agent**: the
probing produces output that matters only until it reaches a verdict, and a sub agent keeps that out of
the run's context.

This skill reads documents and writes a workbook, and touches no repo — so neither question asks about
one.

## The two questions

- **`uv`** — `uv --version`. This is what reads the customer's documents: the `extract-document-text` skill
  runs MarkItDown under it. Where it is missing, its "### Setup" holds the installer, which needs no
  administrator rights. It returns the `uv` command that worked, by name or by full path, since a shell
  opened before the install will not have it on `PATH` yet.
- **Python with `openpyxl`** — this is what *writes* the workbook at the end. Try `python3`, `python`,
  then `py -3`, taking the first that runs `-c "import openpyxl"` cleanly. When the interpreter runs but
  the library is missing, `<interpreter> -m pip install openpyxl` is worth one attempt; a refusal that
  the environment is externally managed is a system Python saying no, and is engineering's to sort out.
  It returns the interpreter name, which every later command in the run uses.

## Reading the verdict

Either one missing stops the run, because each blocks a different half of it: no `uv` and the customer's
documents cannot be read, so nothing can be classified; no `openpyxl` and no workbook can be written, so
there is nothing to hand over.

Tell the user which one it was, in terms of what it costs rather than what is absent, and that someone on
the engineering team can set it up — `uv`, or a Python with `openpyxl`. Then wait for them to come back
with it.

Whether a given *file type* can be read is settled per file as it is extracted, and `EXTRACTED.json` carries
that **verdict**. So this step confirms the two commands and leaves file types to the run that meets them.
