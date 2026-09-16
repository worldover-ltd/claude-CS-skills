---
name: extract-composition-from-documents
description: "Composition: read a folder of supplier documents and say what each raw material is made of, taking every composition from the single document that states it. Triggers on \"extract-composition-from-documents\", when the user wants compositions read out of a customer's documents, or when they ask what a raw material is made of."
allowed-tools: Agent, Skill, Monitor, AskUserQuestion, TodoWrite, Read, Write, Edit, Bash, Glob, Grep
---

### Context

The user is on the Customer Service team and is not a developer. How a run talks to them — what gets
asked, what gets tabled, what gets drawn — is `${CLAUDE_PLUGIN_ROOT}/docs/PRESENTING.md`, read at the
start of a run and applied to every message after it.

The **raw materials** already exist in the customer's Worldmaker app. The **documents** are a folder of
files on the user's computer. What is missing is what each material is actually made of: a list of
ingredients with a percentage against each, which the supplier has stated somewhere in that folder and
nobody has ever pulled out.

A run reads documents and never sends them anywhere. It produces two things: a page the user checks the
work on, and — only once they have approved it — a workbook beside their documents.

### Session setup

All intermediate and output files live under `.workflow/active/${sessionId}/`, relative to the user's
current working directory. At the start of a run, if `${sessionId}` is not already set for this
conversation, generate one and create it, along with the `logs/` directory the long passes redirect
into, before writing any files.

Files inside this plugin are referenced with `${CLAUDE_PLUGIN_ROOT}`, set by Claude Code when the plugin
is installed. Running from a raw checkout instead, treat it as the plugin root — the folder containing
this `skills/` directory.

The user may be on macOS, Linux or Windows. Write every path with forward slashes, quote any that could
contain a space, and keep each command on a single line — a trailing backslash continues a line in `sh`
and breaks it in PowerShell.

**A long pass runs under `Monitor`.** Hashing and reading the documents take minutes to hours, and a
`Bash` call shows the user nothing until it exits.

```
Monitor({ command: "<the pass> 2>&1 1>>'.workflow/active/${sessionId}/logs/<pass>.log'",
          description: "reading the documents", persistent: true })
```

### The conversation

What this run holds in the chat, as against what it writes down, is
`${CLAUDE_PLUGIN_ROOT}/docs/THE_CONVERSATION.md`, read at the start of a run alongside `PRESENTING.md`.
Its three rules bind every step below: start things and talk to the user but look at nothing yourself —
send a sub agent to read whatever a pass wrote; compact at the heavy boundaries, which steps 5 and 7 name;
and leave the judgement to the steps that ask the user something.

Its figures were measured on a run of `upload-documents`, which reads the same folders with the same
passes. Nothing here has been measured on a composition run yet.

### The single source

**A composition comes from one document that states the whole thing.** Where no single document states
it, the material has no composition and the run says so. This is a hard gate, and it costs real
information on real folders: `docs/adr/0009` is the argument and what it measured.

What counts as a composition, and what only looks like one, is
`${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/references/READING_A_COMPOSITION.md`.

### The unit

The words this skill uses — *material*, *candidate*, *single source*, *composition reading*, *balance
row*, *recut*, *kind of date* — are defined in `CONTEXT.md` under `# Composition`.

One material can have four suppliers' folders under it — a code's folder holding four sheets for the same
INCI is normal. The most recent qualifying document wins whichever supplier it came from, and the review
page lists every folder so the choice is visible rather than silent.

### Measuring a change

`lib/gold.py` says whether a change to extraction helped, against hand-made labels in `gold/` at the repo
root. A label is what a person read off the page — an ingredient and the figure beside it — and the score
asks whether that pair can still be found *together*. Nothing calls a model, so two runs are comparable.

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/gold.py" gold --extracted ".workflow/active/${sessionId}/EXTRACTED.json" --label "<what changed>" --history gold/HISTORY.jsonl
```

Not part of a customer run. It is how somebody changing the extraction finds out what they did.

### Process

# Step 1 — preflight

Send **one sub agent**, briefed per
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/PREFLIGHT.md`, to settle its two questions:
`uv`, which reads the documents, and a Python with `openpyxl`, which writes the workbook.

Either one missing stops the run: tell the user which and what it blocks, then wait.

Done when the sub agent has reported, and both are recorded: `<uv>`, the `uv` command it found, and
`<interpreter>`, the Python with `openpyxl`. Every command below uses one or the other, and on a machine
where `uv` installed into the user's home neither is a bare word on `PATH`.

# Step 2 — take the export and the folder

Ask for the two files the customer's app agent produced with
`worldover-export-data-for-document-upload` — the workflow JSON and the items CSV — and the folder of
documents.

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/read_export.py" "<workflow.json>" "<items.csv>" ".workflow/active/${sessionId}"
```

That copies them in as `WORKFLOW.json` and `ITEMS.csv` and prints what the app holds. Put the raw
materials line back to the user and have them confirm it is the app they mean.

**Without the files, stop.** They come from the customer's app, not from this machine. A composition
read against no item list is a composition attached to nothing.

Done when `WORKFLOW.json` and `ITEMS.csv` are in the session directory and the user has confirmed the
material count.

# Step 3 — map the folders to materials

Map the tree and write the branch rules, exactly as `upload-documents` does — the same two references,
the same check, the same `BRANCHES.json`:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/map_tree.py" "<folder>" ".workflow/active/${sessionId}"
```

Read the roles off the summary per
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/READING_THE_TREE.md`, write `BRANCHES.json`,
then test it against the app's real items:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/check_branches.py" ".workflow/active/${sessionId}"
```

That opens no document and writes nothing, so correct the rules and run it again until the match rate
stops improving. A folder named `R289 - Dissolvine GL-47-S` needs a `folderLevelPattern` rule to get
`R289` out of it; a folder whose name carries no code at all needs a `constant` rule naming the item.

Done when the check places every file it can, and whatever it cannot has been named to the user.

**Then decide what not to read**, with `upload-documents`' own step:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/plan_exclusions.py" ".workflow/active/${sessionId}"
```

With no rules that prints the candidates and writes nothing, in two lists: folder names that say on
their face they are put away — `Archive`, `Oud`, `Superseded`, `Vervallen` — and then every other name
ranked by how many parents it repeats under. Put both to the user with their counts and let them pick,
then record it:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/plan_exclusions.py" ".workflow/active/${sessionId}" --folders "Archief,Oud" --extensions "msg,eml"
```

or `--none` where everything is being carried. **Nothing is excluded unless the user names it** — the
first list is an order, not a decision, because a blanket rule on names silently dropped real documents
last time. On the first folder this ran against, 12,218 of 30,922 files were left out by decision, and
here that is doubly worth asking: an archived sheet costs a conversion, an OCR pass and a place in a
shortlist, and an out-of-date composition that wins on date is worse than no composition at all.

Done when `EXCLUSIONS.json` exists and the user chose what is in it.

# Step 4 — find the extraction somebody already paid for

Reading three thousand documents takes half an hour, and another skill on this machine may have done it
already.

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/reuse_extraction.py" ".workflow/active/${sessionId}" "<folder>"
```

That looks for `EXTRACTED.json` under every `.workflow/active/*/`, joins on the resolved path, and
reports what fraction of this folder each one covers. It writes nothing. **Say the number out loud
before reusing anything.** A stale session covering 60% of the folder is worse than no session, because
the 40% it misses looks like materials with no composition document.

Where the user wants one, adopt it:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/reuse_extraction.py" ".workflow/active/${sessionId}" "<folder>" --adopt "<the EXTRACTED.json>"
```

That copies it in and writes `STILL_TO_EXTRACT.json`, the list of paths Step 5 then reads.

Reuse also says which version of the skill read it — *"That extraction was read by version 0.11.0. You
are on 0.12.0."* It warns rather than refusing: not every version changes what a run writes, and the
user knows what changed between two of them. A manifest with no version was made before extractions
carried one.

Done when the user has seen what was found and said whether to reuse it, and `--adopt` has run where
they said yes.

# Step 5 — hash and read the documents

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/hash_documents.py" "<folder>" ".workflow/active/${sessionId}"
```

Then read them, through the `extract-document-text` skill:

```sh
<uv> run --with rapidocr-onnxruntime "${CLAUDE_PLUGIN_ROOT}/skills/extract-document-text/lib/extract_documents.py" ".workflow/active/${sessionId}/DOCUMENTS.json" ".workflow/active/${sessionId}" --scans all --ocr
```

`--with rapidocr-onnxruntime` is not optional: `--ocr` without it stops the run before it converts a
single file.

Three caps a classification run lives with are wrong here, because a composition sits wherever the
supplier put it:

- **No `--max-chars`.** A statement prints its table pages in, and a head-and-tail cap reaches the cover
  page and the footer instead. On the folder this came from, 851 of 2,310 documents were at the cap, and
  one material's whole ingredient table sat in the 19,889 characters that had been trimmed.
- **`--scans all`, not `--scans 3`.** OCR is what turns a scanned composition statement into text — one
  material's only composition was a photographed letter — and on that folder 339 scans run past three
  pages. A composition on scanned page 7 does not exist in any other form, so the text is never written
  and no later pass can recover it. This costs OCR time on every long scan, which is why a
  classification run does not do it.
- **`--table-pages`** defaults to the first 40 pages of a PDF. 205 documents on that folder run longer;
  raise it where the user has catalogues or bound dossiers, and a document with more says so in its
  `note` rather than dropping them quietly.

**Where Step 4 adopted an extraction**, read only what it did not cover, into a directory of its own,
and fold the result back in — the extractor writes a whole `EXTRACTED.json` and would otherwise replace
the adopted one with just the leftovers:

```sh
<uv> run --with rapidocr-onnxruntime "${CLAUDE_PLUGIN_ROOT}/skills/extract-document-text/lib/extract_documents.py" ".workflow/active/${sessionId}/STILL_TO_EXTRACT.json" ".workflow/active/${sessionId}/rest" --scans all --ocr
```

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/reuse_extraction.py" ".workflow/active/${sessionId}" "<folder>" --merge ".workflow/active/${sessionId}/rest/EXTRACTED.json"
```

Done when `EXTRACTED.json` answers for every file in `DOCUMENTS.json` — which the merge reports, as the
count of files in the folder that now have a record.

**Then ask the user to compact** — `/compact`, which clears what has been said and keeps a summary.
Tell them it is safe here in their words: the documents are read and saved, and the next step works from
what was saved.

# Step 6 — shortlist what could be a composition

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/score_composition.py" ".workflow/active/${sessionId}"
```

Scores every file for the things a composition has — a heading, a CAS column, percentages, a balance
line — and writes `CANDIDATES.json`: per material, the handful worth reading. Then cut those into one
task per material, with the text, the dates and the codes inlined:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/plan_readings.py" ".workflow/active/${sessionId}"
```

The cull is deliberately loose. A file wrongly shortlisted costs an agent a few hundred tokens; a file
wrongly culled is a composition nobody ever sees. Where a material shortlists nothing, that is worth
telling the user now — it is usually a folder of certificates and brochures, and no amount of reading
will produce a composition from it.

**Safety data sheets are the one hard cull, and it is a big one.** A sheet states the hazards rather
than the whole composition, so none is ever a source; only its CAS and EC numbers travel to the reader,
as reference. `docs/adr/0012` is the argument. The pass prints how many were left out and which
materials have nothing else, and that second number is the one to put to the user in their own words —
on the folder this was measured against it was 2,010 of 2,962 materials. Those are not failures and not
empty folders: the supplier was asked for a sheet and never for a composition, so there is somebody to
ask, and the workbook names each one.

Done when `READINGS.json` names one task per material, and the user has seen both which materials
shortlisted nothing and which have only safety data sheets.

# Step 7 — read each material

One agent per material, the whole wave in one message, briefed per
`${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/references/READING_A_COMPOSITION.md`.
Send them as `subagent_type: "composition-reader"`.

Each returns the one file it picked, the rows it transcribed, the line each row came from, and the date
the document prints with the label the document used.

Done when every task under `readings/` has an answer under `read/`.

**Then ask the user to compact.** This is the widest fan-out in the run. Every answer is saved, and the
next step checks those answers against the documents rather than against anything said here.

# Step 8 — check every value against the document

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/collect_compositions.py" ".workflow/active/${sessionId}"
```

Four checks, and a material failing any of them carries no rows: the file named was on its shortlist,
every quoted line is really in that file, every CAS and EC passes its check digit and is printed in that
file, and the reported date is printed in that file.

A model asked for the CAS of glycerin answers 56-81-5 whether or not the page says so, and a percentage
invented to make a table sum to 100 reads exactly like a transcribed one. This pass is the only thing
that tells them apart.

A CAS cell naming several numbers is a document being precise about isomers, not a mistyped one. Each
number in the cell has to pass its own check digit and be printed on the page; the cell is not required
to be a single number. Getting that wrong cost one material fourteen of its eighteen rows.

**A material can carry a composition and still be incomplete, and that is what a clean answer hides.**
A reading hands back the rows it saw and could not carry, with what stopped it on each one. Nothing
about those was checked, so they carry no figure anywhere — they are the run saying it saw more than it
could take, and `docs/adr/0013` is why that had to be made free to say.

Read them out the way the run says everything else: the material, what is missing, and that looking at
the page is what settles it. They reach the workbook and the review card on their own, so nothing
depends on being mentioned here.

What this does **not** catch is a reading that carried four rows off a page of eighteen and said nothing
— which is what happened, and was found only because somebody asked. Counting the rows a page appears to
hold was tried and cut: it flagged all eight verified compositions on the run it was measured against.

Writes `COMPOSITIONS.json` — the run's state, and what the next two steps are both built from. Excel
comes at Step 10, on the user's word.

Done when `COMPOSITIONS.json` exists, the materials it could not verify have been read out to the user
with what stopped each one, and any withheld rows or short answers have been named.

# Step 9 — put the page in front of them

```sh
<uv> run "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/build_review_page.py" ".workflow/active/${sessionId}" "<folder>"
```

One card per material: the table on the left, the page of the PDF it was read from on the right. Give
the user the path and tell them what to look for — the numbers against the picture, and the materials
with no composition at all.
`${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/references/REVIEW_PAGE.md` covers
serving it where a viewer will not load local images, and how to change what it shows.

Where they disagree with a pick, write a recut and replay it:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/apply_recut.py" ".workflow/active/${sessionId}" "<recut.json>"
```

That narrows the material's task to the file they named and clears the old answer. Send that agent
again, run Step 8, rebuild the page. A recut carrying `"sourceFile": null` instead records that nothing
in the folder states this composition, in the user's words — no agent is sent for it, and Step 8 puts
their reason on `MATERIALS_WITH_ISSUES`. Correcting rows by hand instead puts values in the workbook that
nothing checked.

Done when the user has been through the page and either approved it or had their recuts replayed.

# Step 10 — write the workbook

Only now, and only because they asked:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/extract-composition-from-documents/lib/write_workbook.py" ".workflow/active/${sessionId}" "<folder>"
```

Writes `<folder>/RAW_MATERIAL_COMPOSITIONS <date>.xlsx` — dated, never overwriting an earlier run's
file, because the customer's folder is an input and somebody may already be working from the last one.

Three sheets: `Composition`, one row per ingredient with the line it was read off; `Reference
Documents`, every file considered per material and why each one lost; and `MATERIALS_WITH_ISSUES`, every
material carrying no composition.

Done when the file is beside the documents and the user has the full path.

### Helping the user

Their next question is usually one of three.

**"Why this file and not that one?"** The `Reference Documents` sheet answers it — every candidate, its
role, the date the run read and what kind of date it was. That is the sheet to open, not the run's logs.

**"This composition is wrong."** Ask which row disagrees with the picture on the review page. A row
that disagrees with the page is a recut. A row that agrees with the page but disagrees with what they know of
the material is a conversation with their supplier, and the page is the evidence to send them.

**"Why does this material have nothing?"** Read them the `MATERIALS_WITH_ISSUES` line. The usual answer
is that the folder holds certificates, brochures and specifications but no composition — which is a
document to request, not a run to redo.

A run ends at the composition: the ingredient names as the supplier wrote them, the figures beside them,
and the document both came from.
