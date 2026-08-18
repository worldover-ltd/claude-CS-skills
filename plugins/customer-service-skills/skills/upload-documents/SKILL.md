---
name: upload-documents
description: "Build the workbook that attaches a folder of documents onto items that already exist in a Worldmaker app, reading each document to decide what kind of document it is. Triggers on \"upload-documents\", or when the user wants documents assigned to existing items for a migration."
allowed-tools: Agent, Skill, AskUserQuestion, TodoWrite, Read, Write, Edit, Bash, Glob, Grep, Artifact
---

### Context

The user is on the Customer Service team and is not a developer. How a run talks to them — what gets asked,
what gets tabled, what gets drawn — is `${CLAUDE_PLUGIN_ROOT}/docs/PRESENTING.md`, read at the start of a run
and applied to every message after it.

The **items** already exist in the customer's Worldmaker app. The **documents** are a folder of files on
the user's computer. What is missing is the link between them, and this skill builds the workbook that
carries it — one row per document, naming the item it attaches to and identifying the file by its
SHA-256.

The files themselves are uploaded last, by the user, out of the migration once it exists. So a run reads
documents and never sends them anywhere:
`${CLAUDE_PLUGIN_ROOT}/docs/DOCUMENT_UPLOADING.md` is that wider journey.

### Session setup

All intermediate and output files live under `.workflow/active/${sessionId}/`, relative to the user's
current working directory. At the start of a run, if `${sessionId}` is not already set for this
conversation, generate one (a UUID, or a timestamp-based slug) and create the directory before writing
any files. Reuse the same `${sessionId}` for every file in the run.

Files inside this plugin are referenced with `${CLAUDE_PLUGIN_ROOT}`, set by Claude Code when the plugin
is installed. Running from a raw checkout instead, treat it as the plugin root — the folder containing
this `skills/` directory.

The user may be on macOS, Linux or Windows, and the shell differs with them. Write every path with
forward slashes, quote any that could contain a space, and keep each command on a single line — a
trailing backslash continues a line in `sh` and breaks it in PowerShell.


**A long pass runs under `Monitor`.** Hashing, reading the documents and grouping them take minutes to
hours, and a `Bash` call shows the user nothing until it exits. Run those with the `Monitor` tool instead,
splitting the two streams: progress on stderr becomes the event stream, and the end-of-run report goes to
a log to read afterwards.

```
Monitor({ command: "<the pass> 2>&1 1>>'.workflow/active/${sessionId}/logs/<pass>.log'",
          description: "reading the documents", persistent: true })
```

`persistent: true`, because a cold read of a customer's folder outruns the one-hour ceiling. Every line the
pass writes reaches the user as it happens, already in their own words — so relay nothing, and let a crash
it could not catch arrive the same way, which is what keeps silence from reading as progress.

That redirect is `sh` and stays `sh`: a `Monitor` command runs in the Bash environment rather than the
user's own shell, so it is the one command in this skill that does not have to survive PowerShell.

### The export

Nothing here reads the customer's app. Its own agent does that, through the
`worldover-export-data-for-document-upload` skill, and hands the user **two files**. They are what a run
is built from, and a run without them cannot start.

**The workflow** — `<PROJECT>_DOCUMENT_UPLOAD_WORKFLOW_<uuid>.json`, the app's vocabulary:

```json
{
  "documentTemplates": [
    { "id": "dt_sds", "name": "Safety Data Sheet (SDS)", "for_tables": ["raw_materials"] },
    { "id": "dt_coa", "name": "Certificate of Analysis (CoA)", "for_tables": ["raw_materials", "products"] }
  ],
  "itemTemplates": [
    {
      "name": "Raw Material",
      "table": "raw_materials",
      "identifierColumn": "code",
      "documentSections": [
        { "label": "Safety", "documentTemplates": ["dt_sds"] },
        { "label": "Quality", "documentTemplates": ["dt_coa"] }
      ]
    }
  ]
}
```

**The items** — `<PROJECT>_DOCUMENT_UPLOAD_ITEMS_<uuid>.csv`, every item documents can attach to:

```
table,id,identifier,name,template,archived
raw_materials,1,RM-0142,Glycerin,Raw Material,false
```

Both file names end in the **same uuid**. A mismatched pair is a workflow read against a stale item list,
which is why the check reports it.

Two words the app uses, and this skill uses with it:

- An ***item_kind*** is a type of item documents attach to, and it **is the `table`** — `raw_materials`,
  `products`. One sheet of the workbook per *item_kind*.
- An ***item_template*** is a blueprint an item is built from, and the owner of the **sections** its
  Documents tab renders. One *item_kind* has **many** *item_template*s, all on the same `table`, and the
  items file says which one each item is on. So the table decides the sheet and the *item_template*
  decides the sections.

`documentTemplates` is a **closed list**, and `for_tables` narrows it further: a document on a
`raw_materials` item can only be a template whose `for_tables` holds `raw_materials`. Every template
carries the app's own `id`, so nothing in a run invents one.

A **section** is never chosen while a document is being read. It is looked up from the template: whichever
section of the item's own *item_template* renders the template the document turned out to be. So a run
answers one question about a document — what kind it is — and derives the rest.

Where the app has no section that renders a template, a step at the very end names one, reading only the
rows the run has already written. That is the whole of the section question and it is nowhere near the
classifier — see `docs/adr/0002`.

### The unit

A run reads **content**, not files. Two identical files under two items are one **reading**, and the
answer is fanned back out to both. The key is the sha *and* the table, because the closed list is per
table and the same PDF under a raw material and a product is picked from two different lists.

This is worth holding onto because a customer's folder is mostly copies — on the first folder this ran
against, 8,082 of 30,922 files shared content — and because it is what makes two copies of one
certificate unable to come back as two different types.

### The tree

The user gives you one folder of documents: **the tree**. Its folder names carry the one thing reading a
document can never recover: **which item** the document belongs to. So the tree answers *which item*, and
reading answers *what kind of document* — two questions, two sources, neither guessing at the other's job.

Every level of a tree plays one of three roles:

- **item_kind level** — its names are kinds of item ("Raw Materials", "Products"), each matching a
  `table` in the workflow.
- **anchor level** — its names carry the identifier of one item. The anchor is the level the whole mapping
  hangs off. It can be a folder level, or the file names themselves when documents sit flat in an item's
  folder (`RM-0142_SDS.pdf`).
- **noise** — dates, "Final", "OLD", "scans", and folders naming a kind of document. A level that looks
  like a document type is not read as one here: it becomes a hint the classifier sees, and the document's
  contents settle it.

A tree is **legible** when every document under it reaches **exactly one live item in the items file**.
That is a fact to be measured rather than judged, and Step 4 measures it. What cannot be placed is named
to the user rather than guessed at — a guessed attachment is a document filed against the wrong
substance, which is worse than no row at all.

### Process

# Step 1 — preflight

Send **one sub agent**, briefed per
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/PREFLIGHT.md`, to settle its
two questions: `uv`, which reads the documents in Step 6, and a Python with `openpyxl`, which writes the
workbook in Step 13.

Either one missing stops the run, as that reference describes: tell the user which and what it blocks,
then wait.

Done when the sub agent has reported, and the `uv` command and the interpreter name are recorded.

# Step 2 — take the two exported files

Ask the user for the workflow JSON and the items CSV described in "### The export", then check them:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/read_export.py" "<workflow.json>" "<items.csv>" ".workflow/active/${sessionId}"
```

That copies them in as `WORKFLOW.json` and `ITEMS.csv` — the names every later step reads — and prints
what the app holds: per table, the identifier column, the item count, the *item_template*s, the document
templates allowed on it, and anything that will cost them documents later. Put that back to the user as
a table per *item_kind* and have them confirm it is the app they mean.

Three things in that report are worth naming to them rather than leaving in the output, because each one
is documents that will not attach: items that are **archived**, items with **no identifier**, and
identifiers **held by more than one item**. A folder named by a colliding identifier resolves to no item
at all, so those are the user's to settle in the app before a run can place them.

**Without the files, stop.** They come from the customer's app, not from this machine: the user asks
their app agent for them by running `worldover-export-data-for-document-upload`, and comes back with
both. Describing the app's templates in chat is not a substitute — a run matches documents against real
items, and there is nothing here to match against.

Done when `WORKFLOW.json` and `ITEMS.csv` are in the session directory, the check reported no error, and
the user has confirmed the tables read back to them.

# Step 3 — map the tree

Ask the user for the folder of documents, then map it with
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/READING_THE_TREE.md`.

Done when `TREE.json` holds every file under the folder, its summary has been read, and no document has
been opened.

# Step 4 — the legibility gate

Read the roles off the summary per that same reference, and write your reading into
`.workflow/active/${sessionId}/BRANCHES.json` — one branch per part of the tree, each naming a `table`
from `WORKFLOW.json` and the rule that gets an identifier out of a path.

Then **test it against the app's real items rather than reasoning about it**:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/check_branches.py" ".workflow/active/${sessionId}"
```

That opens no document and writes nothing. It applies each branch's rule to every path and prints, per
branch, how many files reach exactly one live item, and names the ones that do not — with the app's
nearest identifiers where a folder name looks like a misspelling of one. A branch whose anchor is one
level off reads as a match rate near zero, which is the cheapest possible moment to find out.

Correct the branches and run it again until the rate stops improving. This loop costs nothing: no
document has been hashed or read yet.

**Legible** — every file reaches one item. Put your reading to the user before acting on it, as **the
board**: one row per branch with its *item_kind*, its identifier rule, its match rate, and two or three
real folder names as the evidence. The *item_kind* choices are offered as options from `WORKFLOW.json`
rather than making them recall the app's vocabulary. Redraw the board as each answer lands.

**Not legible** — hand back what the check found, which is already specific: the folders that reach no
item, the ones naming an archived item, the ones whose identifier is held by two items, and the near
misses. Then the moves they own — fix the spelling or the folder names and come back, unarchive an item
in the app, or tell you the item a folder belongs to, which you record as user-supplied.

A tree can be legible in part, and a partly legible tree is worth building from: the branches that pass
go into the workbook, and the rest go to the user as the exception pile. Say which is which rather than
stopping the whole run over one bad folder.

Done when `check_branches.py` reports every file it can place, the user has confirmed the board, and
whatever it cannot place has been named to them.

# Step 5 — decide what not to carry

A folder holds more than a migration wants. Archive folders somebody kept a copy in, saved emails,
quotes and price lists — on the first folder this ran against, **12,218 of 30,922 files** were left out
by decision, and reading them would have cost exactly what reading the rest cost.

Ask before paying for it:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/plan_exclusions.py" ".workflow/active/${sessionId}"
```

With no rules that prints the candidates and writes nothing: folder names ranked by how many different
parents they repeat under, so the categories somebody made on purpose come first and an item's own
folder sinks; and every extension with a count.

Put those to the user as two short lists with counts and let them pick. Then record the decision:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/plan_exclusions.py" ".workflow/active/${sessionId}" --folders "Oud,Offertes" --extensions "msg,eml"
```

or `--none` where everything is being carried, which is an answer worth recording rather than a step to
skip.

**An exclusion is not a failure.** A file that fails is one the run could not read; a file that is
excluded is one somebody decided not to migrate, and it reaches the workbook under those words with the
rule that caught it. Nothing is excluded unless it is named — there is no default drop list, because a
blanket rule on names is what silently dropped real documents last time, on a folder where 132 files
genuinely ended `.pdf.pdf`.

Then **run Step 4's check once more**. It discounts whatever is excluded, so the match rate becomes a rate
over what is actually being carried — and a branch that read as half-legible because an archive folder
names items in an old scheme can come back clean. Still free, still opens nothing.

Done when `EXCLUSIONS.json` exists, the user chose what is in it, they have seen the count carried against
the count in the tree, and the legibility check has been re-read against the smaller set.

# Step 6 — hash, extract, and batch

Three mechanical passes, in order. Each writes a file the next one reads, and the first two are long enough
to run under `Monitor`, per **Session setup**.

**Hash.** A document is carried into the workbook as its SHA-256, because that is what the upload screen
matches on later — names collide between item folders and paths change, the hash does neither.

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/hash_documents.py" "<folder>" ".workflow/active/${sessionId}"
```

That writes `DOCUMENTS.json`, skipping whatever Step 5 excluded, and reports the same file filed under
more than one item — one document belonging to several items, which is a row each rather than a problem.

**Extract.** Invoke the `extract-document-text` skill, giving it `DOCUMENTS.json` as its input and
`.workflow/active/${sessionId}` as its output directory, **with `--scans 3 --max-chars 4000 --ocr`**. It
writes `EXTRACTED.json`, one record per file with the Markdown, rendered pages or OCR text a classifier
can read.

Both numbers are there to bound what one agent is handed. Three pages, because page one of a scanned
dossier is often its cover sheet, the least distinguishing page in it. Four thousand characters, kept as
the head and the tail, because a document names itself at the top and carries its form number at the
bottom — and because twenty uncapped documents in one conversation is what overflowed the context on the
first run of this pipeline. The full conversion stays on disk either way.

`--ocr` is what turns a scan into text, and it changes what the rest of this pipeline can do with one.
A scan read as pictures costs image slots and cannot be quoted against; the same scan read as text costs
neither and is checked like any other document. It needs a package the extraction skill does not declare,
so that run is `uv run --with rapidocr-onnxruntime …`, and it is the slow part of the step — recognition
is seconds a page against half a second a file for conversion. On a folder with few scans it costs almost
nothing. On a folder that is mostly scans, start it before you need the answer, or drop the flag and
accept reading them as pictures.

**Batch.** Join the three files and cut the work into batches:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/plan_batches.py" ".workflow/active/${sessionId}"
```

That resolves each document to a **real item** — branch rule to identifier, identifier to a row in
`ITEMS.csv` — collapses copies into **readings**, pairs each with what to read, and writes one input file
per batch plus `BATCHES.json`. It reports how many readings the copies saved.

A batch closes at twenty readings **or twelve images, whichever bites first**, so a batch of scans is
small and a batch of text is not. Images are what got dropped out of prompts mid-read last time, and the
count is of images rather than of rendered pages on purpose: a photograph the customer filed as a document
renders no pages and is still an image in the conversation. Each batch carries only the document templates
its own tables allow, so a classifier is never shown a choice the app would refuse.

Where the extraction step read a scan with OCR and got enough to identify it by, **the text goes in place
of the pictures** — so that reading costs no image slot, and the batch fills to twenty like any other.
Where OCR came back with a scrap, the pictures go instead, because a heading with nothing behind it is a
worse reading than the page itself.

Six kinds of document never reach a batch, and it reports each separately: no branch covers it, the rule
yielded no identifier, no item has that identifier, several items share it, the item is archived, or
nothing could be read from it. Step 4 should have emptied the first five; anything left here goes to the
user.

Done when `BATCHES.json` names at least one batch, every document in `DOCUMENTS.json` is either in a batch
or on the reported exception list, and the user has seen that list.

# Step 7 — group the documents by form

Most of a customer's folder is the same few pieces of paper filled in over and over. A **form** is that
blank paper — a title, field labels, column headings — and grouping by it costs nothing but changes what
the next step can be asked. Two copies of one form cannot come back as different types if the form is what
gets named, and a form of a thousand documents that fits nothing in the app is one obvious question rather
than a thousand quiet wrong answers. `docs/adr/0004` has the measurements.

Three passes, all in `references/GROUPING_DOCUMENTS.md`:

**Group.** One script over what Step 6 extracted, no agents, long enough to run under `Monitor`:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/grouping/group_documents.py" ".workflow/active/${sessionId}"
```

It writes `FORMS.json`, and reports how many forms it found and how strongly their members joined. The two
settings that decide that are recorded beside the answer, and `--sweep` shows what other settings would
do. A folder under about forty documents is **skipped and says so** — go straight to Step 9, and every
document there is read one at a time as it always was.

**Name.** `plan_naming.py`, then one sub agent per form carrying five members' *structure view*, then
`collect_names.py` for the roll call. The agent is shown no document templates at all: naming a form is
not choosing a type, and offering the app's list here is what turned a form the app had no word for into
nine hundred `Questionnaire`s on the run this came from.

Nobody looks at the forms. A run once put them in front of the user and took their marks back as wording
rules; `docs/adr/0007` says why that went and what it costs. The machinery is still here and still read:
`SPLIT_RULES.json`, written by hand, dissolves a form, splits one on wording, or marks one **split by
value** so its documents are read one at a time. A run writes no such file.

Done when `FORMS.json` holds the forms and `NAMED.json` a title and description for each.

# Step 8 — hold the forms up against the app's list

Now, and not before, ask whether the app has a word for each form. The titles were written in Step 7 with
no document templates in view, which is the only reason this comparison means anything: a form named after
seeing `Questionnaire` would be called `Questionnaire`, and the gap would be invisible.

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/grouping/check_vocabulary.py" ".workflow/active/${sessionId}"
```

It opens no document and decides nothing. It writes `VOCABULARY_GAP.json` and prints the forms the app has
no template for, each with the number of documents behind it and the nearest names the app does have.

**Put the misses to the user with those numbers, and let them choose.** On the folder this came from,
three forms carrying 1,808 of 1,887 documents had no template; every one of those documents was filed
under the closest name instead, 1,016 of them as `Questionnaire`. The same folder against an app that had
those templates produced none. Two roads:

- **create the templates in the app and re-export both files**, then re-run Step 2 and this check. Every
  document behind those forms then attaches on its own. Worth a round trip for a form of a thousand.
- **carry on**, and those documents reach the workbook as placeholder rows nobody can attach until
  somebody creates the template anyway. The right answer for the tail — a form of two documents is not
  worth holding up a folder.

A near match is reported with its score rather than accepted. Deciding that `Certificate of Analysis` is
the customer's `Certificate of Analysis (CoA)` is the user's call, not this script's.

Done when the user has seen the gap and said which road, and either the export has been re-taken or the
run is carrying the misses knowingly.

# Step 9 — classify, and reconcile

**Ask the form, not its documents.** Every document printed on one form is the same kind of document, so
one answer covers all of them — 84 readings instead of 1,887 on the folder this came from. `docs/adr/0005`
has the arithmetic and the one case where it does not hold.

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/grouping/plan_form_classification.py" ".workflow/active/${sessionId}"
```

One task per form, carrying its title, its description, five members' structure view, and the app's list
for the tables its documents sit on. Fan the tasks out to `document-classifier` sub agents exactly as the
per-document batches are fanned out, then:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/grouping/collect_form_templates.py" ".workflow/active/${sessionId}"
```

That checks each answer against the list that form was offered and against the samples it was shown, and
writes `FORM_TEMPLATES.json`. Re-send anything it could not settle.

**Then the documents nothing has answered yet** — singletons, every document in a folder too small to
group, and the members of any form somebody split by hand. Re-run `plan_batches.py` (Step 6) now that
`FORM_TEMPLATES.json` exists: readings whose form is already answered are left out of the batching entirely, and it reports how
many. Each remaining batch goes to one **`document-classifier`** sub agent — the agent this plugin ships,
which carries the model and holds the tools down to `Read` and `Write` — and it says, per reading, the
**id** of the document template it is, the runner-up, how confident it is, a line quoted from the
document, and the evidence for it. Follow
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/CLASSIFYING_DOCUMENTS.md` —
it holds the prompt, the output shape, and the model to run them on.

Then reconcile in code rather than by eye:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/collect_classifications.py" ".workflow/active/${sessionId}"
```

That fans each answer out to every copy, derives the section per copy, and checks the answer three ways
before it counts: the template has to be one the app allows on that table, the quotation has to appear in
what the classifier was actually given, and the classifier has to say the document reached it. Then it
writes `CLASSIFICATIONS.json` and prints the roll call — how many answered, which batches are missing, the
spread of confidence, and every document a person still has to settle. Send any missing batch again; that
reference holds how many rounds to give it.

**The confidence floor is not about legibility.** A score is the gap between the best-fitting template and
the runner-up, so a document that is plainly a technical data sheet *and* plainly a specification scores
low however clearly it announces itself. Those are the documents worth a second reading, and the collector
names them and writes `REREAD.json` rather than spending anything:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/plan_batches.py" ".workflow/active/${sessionId}" --round 2
```

Fan those out exactly as before and run the collector again. Two readings that agree clear the floor; two
that differ put the row in front of a person carrying both answers.

A classifier that finds nothing fitting in the app's list **proposes** a name instead, and the collector
groups those by name with a count, folding spellings that differ only in case or punctuation. Put them to
the user that way — as a short list of templates and sections to create in the app, each with how many
documents are waiting on it — rather than as one question per document. Creating a template once clears
every document that proposed it.

What is left over is the **exception pile**, and it is the user's to settle: documents that got neither a
pick nor a proposal, documents two readings disagreed on, and documents nothing could read. Put them to
the user with the evidence the classifier gave, since a file name plus one line of evidence is usually
enough for them to say what a document is.

Done when `CLASSIFICATIONS.json` holds one entry per batched document, every batch has answered or been
reported as unanswered, `REREAD.json` is empty or its round has been run, and the exception pile has been
through the user.

# Step 10 — set the answers against each other

Every check above judges one answer alone, which is how one line quoted from four hundred documents came
back as three different templates without anything noticing.

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/compare_answers.py" ".workflow/active/${sessionId}"
```

It compares only the answers given one document at a time — a form answered once cannot contradict itself
— and reports two things: one quotation resolving to several templates, and one evidence line written for
documents in different forms. Both are short by construction: 1,632 contradictory answers on the run this
came from sat on eight quotations, which is eight lines for a person rather than 1,632 rows.

Put whatever it finds to the user with both readings. Neither answer is more likely right than the other,
which is the point of showing them together.

Done when `CONTRADICTIONS.json` exists and anything in it has been settled or knowingly carried.

# Step 11 — arrange the Documents tab

Every document now has a template, so where each kind belongs can be answered from the rows themselves —
no file is opened and no extracted text is read.

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/plan_sections.py" ".workflow/active/${sessionId}"
```

One task holding every distinct **(document template, item template)** pair and the sections each item
template already has — 58 pairs behind 2,163 rows on the folder this came from. Send it to one sub agent,
which returns a section per pair, then:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/collect_sections.py" ".workflow/active/${sessionId}"
```

Expect most of the answers to be **new** sections rather than lookups: one real export held five sections
across three item templates, and 68 of 82 template rows had no section at all. Where the app already
arranges a template, the app's own arrangement wins and any disagreement is reported rather than applied.

The user reads this on the workbook's `Document Templates` and `Document Sections` sheets, where `is_new`
says `yes` on yellow and `no` on green. That is the review — do not put 58 rows in chat.

Done when `SECTIONS.json` holds a section for every pair, or names the ones nobody answered.

# Step 12 — show the workbook before building it

Load the `artifact-design` skill, then publish one **markdown** artifact to
`.workflow/active/${sessionId}/tree.md` holding, in this order:

1. The tree as a `flowchart TD`, each level labelled by the role Step 4 gave it, drawn per
   `${CLAUDE_PLUGIN_ROOT}/vendor/mermaid-diagrams/references/FLOWCHARTS.md`. A tree too wide to read is
   one diagram per branch, not one crowded diagram.
2. One card per branch: *item_kind*, identifier column, how many of that table's items the documents
   reached, and document count. Reaching 40 of 300 items is worth seeing before the workbook is built.
3. The document templates the classifier actually used, with a count each, and the sections they fall into
   per *item_template* — so the shape an item's page will take is visible before it is built.
4. A preview of each sheet the workbook will have — real header row, and three to five real rows, with
   real identifier values, real file names and real template names.
5. What will be on `FILES_WITH_ISSUES`, by file name with its evidence, grouped by reason — and
   separately what will be on `IGNORED_FILES`, as a count per rule, since the user made that call already
   and the workbook itself carries the per-file list.
6. The attachments worth spot-checking: the lowest-confidence rows that are still going into the workbook.

The sheet preview is what the user can judge, so fill it with real values rather than placeholders.

Iterate: take their corrections, update `CLASSIFICATIONS.json`, republish to the same file path so the URL
holds. Done when the user approves what the artifact shows.

# Step 13 — write the workbook

Build the Excel file per
`${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/references/DOCUMENT_WORKBOOK_FORMAT.md`, writing it
**beside the documents** at `<the folder the user gave>/DOCUMENT_UPLOAD_WORKBOOK.xlsx` — the folder it
describes, where the user will look for it, rather than two levels down a session directory they would
have to be guided to.

Three sheets come before the data: `README` with the counts and what needs doing in the app,
`IGNORED_FILES` with everything left out by decision and the rule that caught it, and
`FILES_WITH_ISSUES` with everything the run could not attach and why. Keeping the last two apart is what
makes the short list short: a folder can ignore twelve thousand files and still have only forty that need
somebody.

Done when every file under the folder appears exactly once — a data sheet row, an `IGNORED_FILES` row, or
a `FILES_WITH_ISSUES` row — every identifier value traces back to a row in `ITEMS.csv`, and the file loads
back with the row counts `CLASSIFICATIONS.json` predicted.

# Step 14 — hand it over

Give the user the full path to `DOCUMENT_UPLOAD_WORKBOOK.xlsx` — it is in their own documents folder, so
say that, since the last version of this skill left it somewhere they had to be shown. Then one line per
data sheet saying which *item_kind* it attaches documents to and how many, the sections each
*item_template* ended up with, how many files are on `IGNORED_FILES` and on `FILES_WITH_ISSUES`, and the
two or three attachments worth spot-checking — the lowest-confidence rows in the workbook.

Then what happens next, since two things are still to come and one of them can catch them out: they start
a migration with this workbook, and the migration then asks them for the document files themselves. Those
files have to be the ones this run hashed — an edited or re-exported document no longer matches its row.

### Helping the user

A run is one stage of a longer journey the user does the rest of by hand: they start the migration with
the workbook you hand over, then upload the document files from the migration card.
`${CLAUDE_PLUGIN_ROOT}/docs/DOCUMENT_UPLOADING.md` holds both stages, and is what to read when the user
asks how the upload works or what to do with the workbook. Offer that help as it comes up rather than
waiting to be asked.
