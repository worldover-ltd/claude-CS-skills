# A pass reports in the user's words, not the agent's

A *pass* — one mechanical script run inside a step — writes its progress as sentences for the person
watching the run, on stderr, and those sentences reach them unaltered. No agent stands in the middle
turning a counter into prose.

The scripts already printed progress: `extract_documents.py` reported every 25 files, and had done since
it was written. Nobody ever saw it. Python block-buffers a stdout that is not a terminal, and Claude Code
hands a `Bash` tool's output over only when the process exits — so a 29-minute read of a customer's folder
was 29 minutes of nothing, then everything at once. Flushing alone fixes neither half. The fix had to cross
the process boundary while the process was still running, which is what `Monitor` does: it runs the pass
and turns each stdout line into a chat message as it lands.

## Why not machine lines and a translator

The obvious split is the other one, and it was the first recommendation: the script emits
`[ocr] 412/768 1.4/s eta 4m`, the agent reads it and says something a Customer Service person can act on.
It keeps `extract-document-text` free of any opinion about who is reading.

It lost because the translation step buys nothing once `Monitor` is delivering the line. The agent would
have to be awake, holding the run, reading and re-emitting — and every re-emission is a chance to
paraphrase a number. Meanwhile the machine line would have to reach the user *anyway* on any turn the
agent was busy, and a Customer Service person cannot read `eta 4m` off a chat notification and know
whether it is minutes or a model's guess.

## Consequences

- **The wording is contract.** Anything reading that stderr is reading English, so a change to a line is a
  change other things see. `extract-document-text/SKILL.md` says how those lines must read, deferring to
  `docs/PRESENTING.md` for the vocabulary.
- **A user-facing surface cannot live in a general utility.** `extract-document-text` moved out of
  `util-skills` and into `customer-service-skills`, and `util-skills` — which held nothing else — was
  deleted. That also removed a two-plugin install from the README, which was worth having on its own.
- **No time is quoted until one has been measured.** The opening line carries counts only. A published
  constant was available for conversion — half a second a file — and was rejected anyway: a person cannot
  tell a measured estimate from an invented one, and OCR has no constant at all.
- **The waits lengthen as the news thins: thirty seconds, five minutes, then every fifteen.** The early
  updates carry an estimate and then a corrected one; the later ones only say the pass is still alive, and
  each one costs the user a desktop notification. The opener is exempt, so a pass finishing inside the
  first thirty seconds costs exactly two lines. The schedule is per pass rather than per run, because
  sharing one would mean five processes coordinating through a file for nothing.
- **Silence must never read as progress.** Everything the pass writes to stderr is the event stream — no
  filter to keep current — so a crash the top-level handler could not catch, an out-of-memory kill above
  all, arrives the same way the progress did.
- **`progress.py` is duplicated exactly once, and only where it must be.** `hash_documents.py` and
  `lib/grouping/` share one copy, the second lives beside `extract_documents.py`, which `uv run` executes
  in an interpreter that reaches nothing outside its own directory.
