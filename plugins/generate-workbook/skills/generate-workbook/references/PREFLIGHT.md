# Preflight

What a preflight step settles before a run commits to anything, and what it returns. Three questions,
all of them cheap, and each answered by a command that actually runs. It goes to **one sub agent**: the
probing produces output that matters only until it reaches a verdict, and a sub agent keeps that out of
the run's context.

A caller that needs only some of them says which when it briefs the sub agent — `generate-workbook` asks all
three, `generate-document-upload-workbook` asks the first two and never touches a repo.

## The three questions

- **`uv`** — `uv --version`. This is what reads the customer's files: the `extract-document-text` skill
  runs MarkItDown under it. Where it is missing, its "### Setup" holds the installer, which needs no
  administrator rights. It returns the `uv` command that worked, by name or by full path, since a shell
  opened before the install will not have it on `PATH` yet.
- **Python with `openpyxl`** — this is what *writes* the workbook at the end. Try `python3`, `python`,
  then `py -3`, taking the first that runs `-c "import openpyxl"` cleanly. When the interpreter runs but
  the library is missing, `<interpreter> -m pip install openpyxl` is worth one attempt; a refusal that
  the environment is externally managed is a system Python saying no, and is engineering's to sort out.
  It returns the interpreter name, which every later command in the run uses.
- **Repo access** — whether `gh repo list WorldoverProd --limit 1` returns a repo, which is how the app
  schema step reaches the customer's app.

## Reading the verdict

Any of the three missing stops the run, because each one blocks a different half of it: no `uv` and the
customer's files cannot be read, no `openpyxl` and no workbook can be written, no repo access and the app's
own vocabulary is out of reach.

Tell the user which one it was, in terms of what it costs rather than what is absent, and that someone on
the engineering team can set it up — `uv`, a Python with `openpyxl`, or access to the `WorldoverProd`
GitHub organisation. Then wait for them to come back with it.

Whether a given *file type* can be read is settled per file as it is extracted, and `EXTRACTED.json` carries
that **verdict**. So this step confirms the three commands and leaves file types to the run that meets them.
