# Preflight

What the two sub agents of a preflight step probe and what each returns. The two questions are
independent, so both sub agents go out in a single message. Each does a pile of probing whose output
matters only until it reaches a verdict, and a sub agent keeps that out of the run's context.

## Document tooling

One sub agent invokes the `verify-document-skills-requirements` skill and returns its verdict:
which of Anthropic's official document skills (`xlsx`, `docx`, `pdf`) are installed, and which of the
tools they declare actually work on this system — expressed as the file types that are covered.

## This run's own prerequisites

A second sub agent settles two things and returns both:

- The Python this system has — try `python3`, `python`, then `py -3`, taking the first that runs
  `-c "import openpyxl"` cleanly. When the interpreter runs but the library is missing,
  `<interpreter> -m pip install openpyxl` is worth one attempt; a refusal that the environment is
  externally managed is a system Python saying no, and is engineering's to sort out. It returns the
  interpreter name, which every later command in the run uses.
- Whether `gh repo list WorldoverProd --limit 1` returns a repo, which is how the app schema step
  reaches the customer's app.

## Reading the verdicts

Missing Python or missing repo access stops the run: tell the user which one it was, and that someone
on the engineering team can set it up — access to the `WorldoverProd` GitHub organisation, or a Python
with `openpyxl`. Then wait for them to come back with it.

What partial document tooling costs differs by skill, so each skill reads that verdict against its own
process.
