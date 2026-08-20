# Building the document upload workbook on your own machine

This guide covers the part of a document upload that happens in Claude Code on your own
computer. You start with two export files and a folder of the customer's documents. You
finish with a single spreadsheet, `DOCUMENT_UPLOAD_WORKBOOK.xlsx`, sitting next to that
folder — the file you take back into Worldmaker to start the migration.

Everything here is `{LOCAL}` — it happens in Claude Code on the user's own machine, and none
of it touches the customer's app. The run makes no decision on its own that matters: most of
this guide is the judgement calls it puts to the user, and what each one costs if it goes
the wrong way.

## Where this guide starts and stops

The whole journey has three parts, and this guide owns the middle one.

| Part | Where it happens | Guide |
| --- | --- | --- |
| Getting the two export files out of the customer's app | Worldmaker, app chat | [Document uploads](../WORLDMAKER/DOCUMENT_UPLOADS.md) |
| **Building the workbook from those files and your documents folder** | **Your machine, Claude Code** | **This guide** |
| Attaching the workbook, uploading the files, applying the card | Worldmaker, Migration board | [Document uploads](../WORLDMAKER/DOCUMENT_UPLOADS.md) |

The wider migration flow this sits inside — what a card is, how environments work, what
else a migration carries — is in [Migrations](../WORLDMAKER/MIGRATIONS.md).

So: everything below assumes you already have the two export files downloaded, and it stops
the moment the workbook exists. What you do with the workbook afterwards is the
Worldmaker guide's job.

---

## Before you start

**What you need to have already**

- **The two export files**, downloaded from the customer's app chat — where the user asks
  for them in plain language or types **/export-document-data**. Their names look like
  `<PROJECT>_DOCUMENT_UPLOAD_WORKFLOW_<id>.json` and
  `<PROJECT>_DOCUMENT_UPLOAD_ITEMS_<id>.csv`. Check the id on the end is the **same on
  both** — a workflow file paired with a stale items list is a real and easy mistake, and
  the run will tell you about it, but it is cheaper to notice now.
- **The folder of customer documents**, all of it, in one place on your computer.
- **Claude Code**, with the `upload-documents` skill available.

**What has to be installed**

- **`uv`** — this is what reads the documents. If it is missing it installs into your own
  home folder and needs no administrator rights.
- **A Python with `openpyxl`** — this is what writes the spreadsheet at the end.

The run checks for both before it does anything else and stops with a plain message naming
whichever is missing, and what that blocks. Someone on the engineering team can set either
one up for you.

**What the run will need from you while it runs**

Roughly six decisions, spread across the run. You cannot start it and walk away. The two
that take real attention are confirming how your folders map onto the customer's items, and
looking at a page of document samples and saying whether the groupings hold.

**How long it takes**

The slow part is reading the documents. Budget about **half a second per file**: a folder
of 3,500 mixed files, 1.46 GB, took about **29 minutes** the first time and **8 seconds**
on a re-run. Scanned pages are much slower than that — recognition runs at seconds per
page rather than half a second per file — so a folder that is mostly scans will take
considerably longer. Everything else in the run is minutes, apart from your own review time.

**Two things worth knowing up front**

- **No document leaves your computer.** The run reads your documents locally and records
  each one's fingerprint. The actual files are uploaded later, by you, from inside
  Worldmaker.
- **A document is identified by its contents, not its name.** Everything is matched on the
  file's SHA-256 hash. You can rename files and move them between folders after the
  workbook is built and everything still matches. But if you *edit* or *re-export* a
  document it becomes a different file, and it will no longer match its row.

---

## What the run is actually doing

Two questions have to be answered about every document, and they come from two completely
different places. The run never lets one guess at the other's job.

- **Which item does this document belong to?** This comes from the **folder structure**.
  Reading a document cannot reliably recover it.
- **What kind of document is this?** This comes from **reading the document**. The folder
  name is at most a hint.

Everything else follows from that split. The section a document ends up in on the item's
Documents tab is not a third question — it is looked up afterwards from the document's
type, in code, and nothing that reads a document is ever asked about it.

One more idea worth holding onto: the run reads **content, not files**. Two identical files
filed under two different items are read once and the answer is copied to both. On the
first customer folder this ran against, 8,082 of 30,922 files shared their contents with
another file, so this saves a great deal — and it is also what makes two copies of one
certificate unable to come back as two different document types.

---

## How the run talks to you

Three surfaces, and it helps to know which is which.

- **The board.** A plain table in the terminal, one row per branch of your folder tree,
  one column per decision. Anything not yet settled shows as `?` rather than being left
  blank. It is redrawn in full every time something changes.
- **Questions.** Multiple-choice prompts with the run's own recommendation first. Options
  are taken from your export files rather than asking you to remember what the app calls
  things.
- **Published pages.** Two points in the run publish a page and give you a link: the form
  review page, and the final preview before the workbook is written. If publishing is not
  available on your account, the same content is written as a file in the run's working
  folder and you are walked through it there — the approval still happens either way.

The run keeps its working files in a `.workflow/active/<session id>/` folder underneath
wherever you started Claude Code. You will not normally need to open anything in there.

---

## Step 1 — Start the run and let it check its tools

### 1. Start Claude Code where you want the working files

Open Claude Code in a folder you are happy for the run's working files to live in. This does
not have to be, and usually should not be, the customer's documents folder.

### 2. Ask for the run

Type the skill name:

> upload-documents

Or just describe what you want: "I need to attach a folder of documents to items that
already exist in a customer's app."

### 3. Wait for the tool check

Before anything else, the run checks that `uv` and a Python with `openpyxl` are both
present and working. This takes a few seconds.

If either is missing the run **stops**. It will tell you which one and what it blocks — no
`uv` means the documents cannot be read at all, no `openpyxl` means no spreadsheet can be
written at the end. Get whichever it named installed, then start again.

This check deliberately does **not** cover LibreOffice, which is what makes older Word and
OpenDocument files readable — file types are settled per file as each one is read, not up
front. If your folder has a lot of `.doc` or `.odt` files you will
find out about it later, during extraction.

---

## Step 2 — Hand over the two export files

### 1. Give it both file paths

The run asks for the workflow JSON and the items CSV. Give it the full path to each, or
drag them into the conversation.

**Without both files the run cannot start.** They are the only thing on your machine that
knows what the customer's app actually holds. Describing the app's document types in chat
is not a substitute — the run matches your documents against real items with real database
ids, and there is nothing to match against otherwise.

If you do not have them, go and get them: that is Step 1 of the
[Worldmaker document uploads guide](../WORLDMAKER/DOCUMENT_UPLOADS.md).

### 2. Read back what the app holds

The run checks the two files against each other and then reads the app back to you as a
table per kind of item. For each one you get:

- what identifies an item of that kind (the code, the SKU, whatever the app indexes),
- how many items of that kind exist,
- which item templates that kind has,
- which document types the app allows on it.

Confirm that this is the app you mean before moving on.

### 3. Deal with the three things that cost you documents

Three findings get called out separately, because each one means documents that will not
attach:

- **Archived items.** Documents pointing at an archived item cannot be placed. Somebody
  unarchives the item in the app, or those documents get left out.
- **Items with no identifier at all.** If your folders are named by code and an item has no
  code, there is nothing to match on.
- **Identifiers held by more than one item.** A folder named with a colliding code resolves
  to *no* item rather than to either one, deliberately.

All three are settled in the customer's app, not here. If any of them affect a meaningful
number of your documents, it is worth going back and fixing them before carrying on — you
would otherwise be re-running the whole thing later.

---

## Step 3 — Point it at the documents folder

### 1. Give it the folder

Give the run the top-level folder holding all the customer's documents.

### 2. Let it walk the tree

It walks the entire folder without opening a single document, and prints a summary: how
many files there are, how deep the folders go, and per level how many distinct folder names
there are, a sample of them, how often each repeats, and which file types sit underneath.

It also flags the two things that most often make a folder unusable: files sitting at mixed
depths, and files loose at the very top of the folder with nothing above them.

Nothing is read, nothing is hashed, and nothing is decided yet. This step is cheap and
exists so the next one can be argued with.

---

## Step 4 — Confirm the board

This is the most important thing you will be asked in the whole run, so it is worth slowing
down for. Everything downstream depends on it, and a wrong answer here files a document
against the wrong substance.

### 1. Understand what it is proposing

Every level of your folder tree gets one of three roles:

- **A kind of item** — a level whose names are things like "Raw Materials" and "Products",
  matching the kinds of item in your export.
- **The anchor** — the level whose names carry the identifier of one specific item. This is
  what the whole mapping hangs off. It is usually a folder level, but it can be the file
  names themselves when documents sit flat in one folder (`RM-0142_SDS.pdf`).
- **Noise** — dates, "Final", "OLD", "scans", version folders. A level named after a *kind
  of document* ("SDS" under 300 item folders) counts as noise for matching purposes, but it
  is passed to the reading step as a hint that the document's own contents can overrule.

### 2. Read the board

The run puts its reading back to you as a table, one row per branch of the folder:

| Folder | Kind of item | Identified by | Documents | Reaching an item |
| --- | --- | --- | --- | --- |
| `Raw Materials/` | Raw Material | folder name, a code like `RM-0142` | 208 | 208 of 208 |
| `Products/` | Product | folder name — **is it the code or the name?** | 96 | ? |
| `Misc/` | ? | ? | 14 | ? |

Two things make this checkable rather than something you have to take on trust:

- **Each row carries a match rate**, which was measured against the customer's real item
  list rather than reasoned about. A branch whose anchor is one folder level off comes back
  at a rate near zero, which is exactly what you want to see at this point rather than an
  hour later.
- **Each row carries two or three real folder names** as evidence, so you are checking the
  reading against something concrete.

### 3. Work down it one branch at a time

Answer each row. The kind of item is offered as a choice taken from your export file, so
you do not have to recall the app's exact wording. The board is redrawn in full after each
answer.

The run will re-test and re-measure as your corrections land. This loop is free — nothing
has been hashed or read yet, so getting it right costs only your time.

### 4. Deal with what cannot be placed

Where a folder cannot be resolved you get told exactly which one and why, and the reasons
are specific:

| What you are told | What you do about it |
| --- | --- |
| The rule got no identifier out of this path | The anchor is the wrong level, or a file-name pattern misses. Correct it and re-test. |
| No item in the app has that identifier | The folder is named for something the app does not hold, or spelled differently. The run offers the app's nearest matching identifiers, so a typo is visible. |
| Several items share that identifier | The customer has two items on one code. They settle it in the app. |
| The item it names is archived | Unarchive it in the app, or leave those documents out. |
| No branch covers this file at all | A part of the tree the mapping missed, usually files loose at the root. |

Case differences are forgiven and reported — `rm-0143` reaches `RM-0143`, and you are told
how many matched that way, so a systematic case difference is visible rather than silent.

### 5. Accept a partly legible tree if that is what you have

A folder can be legible in part, and that is worth building from. The branches that pass go
into the workbook; the rest come back to you as the exception pile. The run says which is
which rather than stopping the whole thing over one bad folder.

Your options for an unresolvable folder are: fix the folder names and come back, fix the
item in the app and come back, or tell the run directly which item that folder belongs to
(recorded as your answer rather than something it worked out).

Nothing is ever guessed. A guessed attachment is a safety data sheet filed against the
wrong chemical, which is worse than no row at all.

---

## Step 5 — Say what you do not want to carry

A customer's folder holds much more than a migration wants. On the first folder this ran
against, **12,218 of 30,922 files** were left out by decision — archive copies, saved
emails, quotes, price lists. Reading them would have cost exactly what reading the real
documents cost.

So you get asked before anything is paid for.

### 1. Look at the two lists

The run shows you two short lists with counts:

- **Folder names**, ranked by how many different parents they repeat under. This ranking
  matters: a category somebody deliberately created under every item ("Oud", "Offertes",
  "Archief") floats to the top, and an individual item's own folder sinks to the bottom.
- **File extensions**, with a count each.

### 2. Pick what to leave out

Choose the folder names and the extensions you do not want carried. Or say "carry
everything" — that is a real answer and it gets recorded rather than skipped.

Nothing is excluded unless you name it. There is no default drop list, deliberately: a
blanket rule on file names is what silently dropped real documents on an earlier folder,
where 132 files genuinely ended `.pdf.pdf`.

### 3. Know that ignored is not failed

An **excluded** file is one somebody decided not to migrate. A **failed** file is one the
run could not read. They end up on two different sheets of the workbook for exactly that
reason. Every excluded file is listed by name with the rule that caught it, so a rule that
swallowed more than you intended is visible.

### 4. Look at the match rates again

Excluding files changes the picture, so the legibility check runs once more against the
smaller set. A branch that read as half-legible because an old archive folder named items
in a scheme the app has since dropped can come back completely clean. Still free, still
opens nothing.

---

## Step 6 — Hashing, reading and batching

Three mechanical passes, in order. This is the part where you mostly wait.

### 1. Hashing

Every file that is being carried gets its SHA-256 computed. That fingerprint is the
document's identity all the way through to the upload screen in Worldmaker — names collide
between item folders and paths change, but the hash does neither.

If the same file appears under several items, you are told. That is one document belonging
to several items, which becomes a row each rather than a problem.

This is fast.

### 2. Reading the documents

Every document is converted to text. PDFs with no text layer at all — scans, photographed
or faxed pages — have their pages rendered to images instead, and those images are then
read back into text by optical character recognition.

That last part matters more than it sounds. A scan read as pictures is expensive and cannot
be quoted against; the same scan read as text costs nothing extra and can be checked like
any other document.

**This is the slow part.** Half a second per file for ordinary conversion, seconds per page
for scans. Start it and go and do something else.

What reads and what does not:

- **Reads fine**: PDF, Word `.docx`, Excel (`.xlsx`, `.xls`, `.csv`, `.tsv`), PowerPoint
  `.pptx`, Outlook `.msg`, HTML, plain text, Markdown, JSON, XML, EPub, and ZIP archives
  (which are expanded and their contents converted).
- **Reads only if LibreOffice is installed on your machine**: `.doc`, `.rtf`, and
  OpenDocument files (`.odt`, `.ods`, `.odp`). Where it is not installed these come back
  unsupported with a note naming LibreOffice — so the difference between "install this" and
  "the customer has to re-save these" is visible rather than guessed at. On one real
  customer folder that was 333 files.
- **Never reads**: `.pages`, `.numbers`, `.key`, `.7z`, `.rar`.

A file's actual contents outrank its name. Customer folders are full of files saved under
the wrong extension, and these are handled and reported: a JPEG called `.pdf` is treated as
an image, an `.xls` called `.xlsx` is converted as the `.xls` it really is. Only what
survives as unsupported or failed is a file somebody genuinely has to re-save.

### 3. Batching

The documents are resolved to real items — folder rule to identifier, identifier to a row
in the customer's item list — copies are collapsed into single readings, and the work is cut
into batches. You are told how many readings the copies saved.

Six kinds of document never make it into a batch, and each is reported separately:

- no branch covers it,
- the branch rule yielded no identifier,
- no item in the app has that identifier,
- several items share that identifier,
- the item it names is archived,
- nothing could be read from it.

Step 4 should have emptied the first five. Anything left comes to you now, and it will also
appear on the workbook's `FILES_WITH_ISSUES` sheet at the end.

---

## Step 7 — Grouping the documents by form

Most of a customer's folder is the same few pieces of paper filled in over and over. A
**form** is that blank paper — a title, field labels, column headings, with everything
somebody typed in stripped out.

Grouping by form costs nothing and changes what can be asked next. Two copies of one form
cannot come back as two different document types if the form is what gets named. And a form
of a thousand documents that fits nothing in the app becomes one obvious question rather
than a thousand quiet wrong answers.

### 1. The grouping pass

A script reads what was extracted and groups the documents. No document is read by a model
here, and nothing is named yet. You are told how many forms it found and how strongly their
members joined.

Two settings decide the outcome, and both are recorded alongside the answer so a form can be
explained to a customer later. The defaults come from one real folder of 1,887 scanned
documents, where they put 98.4% of documents into a form whose members all turned out to be
the same type. They are a starting point, not a constant.

**A folder under about forty documents is skipped entirely** and says so. At that size "a
word most documents share" means nothing, so every document is read individually instead —
skip ahead to Step 9.

### 2. The naming pass

One agent per form is shown five of its members with everything typed in blanked out, and
writes a title and a description for the blank form.

The important detail: **that agent is not shown the app's list of document types at all.**
Naming a form is not the same as choosing a type. On the run this design came from, showing
the app's list at this point turned a form the app had no word for into nine hundred
documents filed as `Questionnaire`.

You do not see the forms yet. The next step goes first, on purpose.

---

## Step 8 — Where the app has no word for a form

Now, and not before, the form names are held up against the document types the app actually
has.

### 1. Read the gap

You get a list of the forms the app has **no** document type for, each with the number of
documents behind it, and the nearest names the app does have with a similarity score.

This comparison only means anything because the names were written without the app's list in
view. A form named after seeing `Questionnaire` would be called `Questionnaire`, its name
would match, and the gap would be invisible.

The scale of this on a real folder: three forms carrying **1,808 of 1,887 documents** had no
document type in the app. All of them were filed under the closest available name instead,
1,016 of them as `Questionnaire`. The same folder run against an app that had those types
produced none of that.

### 2. Choose a road

For each miss you have two options, and the number of documents behind it decides which:

- **Create the document types in the app and re-export both files**, then hand the new
  export over and re-run this check. Every document behind those forms then attaches on its
  own. Worth the round trip for a form of a thousand.
- **Carry on knowingly.** Those documents reach the workbook flagged as needing a type
  somebody has to create before they can attach. The right answer for the tail — a form of
  two documents is not worth holding up a folder for.

A near match is reported with its score rather than accepted. Deciding that
"Certificate of Analysis" is the customer's "Certificate of Analysis (CoA)" is your call,
not the script's.

---

## Why you are not shown the forms

The run used to publish a page of samples per form and ask you to mark the documents that
did not belong. That page is gone, and nothing replaces it: nobody confirms the grouping
before the documents are read.

Two checks still stand where it fell:

- **Step 8** — the vocabulary gap you just read. On real document folders this is the one
  that caught most: three forms carrying 1,808 of 1,887 documents the app had no template
  for, every one of which would otherwise have been filed under the nearest name.
- **Step 11** — the workbook preview, now the only place a person sees what the grouping
  did: the templates actually used with a count each, and the lowest-confidence rows.

Know what that costs. The grouping settings are defaults carried from the one folder
anybody measured, not findings about yours, so a form holding two kinds of document is
answered once — as whichever kind the run picked. If you can see that a form is wrong, say
so before the preview: a grouping can still be dissolved or split on wording, but that
takes someone technical writing a rule by hand rather than a click.

---

## Step 9 — Reading the documents and deciding what each one is

### 1. The forms get answered first

**One answer per form, not per document.** Every document printed on the same form is the
same kind of document, so one reading covers all of them — 84 readings instead of 1,887 on
the folder this design came from.

Each form is read against the app's list for the kinds of item its documents sit on, so it
is never offered a type the app would refuse.

### 2. Then everything the forms did not answer

Four kinds of document are still read one at a time, and between them they are everything a
per-document batch now carries:

- members of a form you marked as "same paper, different documents",
- documents pulled out of a form, or from a form that dissolved,
- forms of a single document,
- every document in a folder too small to group at all.

Each of those gets read individually and given: the document type it is, a runner-up type, a
confidence score, a line quoted verbatim out of the document, and one line of evidence
saying what actually decided it.

A useful evidence line reads like "Header reads SAFETY DATA SHEET and section 3 lists hazard
classifications, so not the CoA". "Appears to be an SDS" is not evidence.

### 3. Understand what the confidence score means

**Confidence is a margin, not a legibility score.** It is the gap between the best-fitting
type and the second-best. A sheet headed TECHNICAL DATA SHEET that is equally plausibly a
Product Specification scores *low*, however clearly it announces itself, because two types
fit it.

So sorting by confidence surfaces the genuinely ambiguous documents, not the badly-scanned
ones. A low score is not a failure — it is what earns a document a second reading.

### 4. Second readings

Documents below the confidence floor are read again. Two readings that agree clear the
floor; two that disagree go in front of you carrying both answers, so you decide.

Every answer is checked three ways before it counts: the type has to be one the app allows
on that kind of item, the quoted line has to actually appear in what was read, and the
reader has to confirm the document reached it. An answer whose quotation is not in the
document is thrown away and the document is read again.

### 5. Deal with the exception pile

What is left is yours to settle, and each kind is a different action:

- **Document types the app does not have.** These arrive **grouped by proposed name with a
  count**, folding together spellings that differ only in case or punctuation. Your action
  is creating each type once in the app, not answering per document — and creating it clears
  every document waiting on it.
- **A type with no section to put it in.** The document really is that type; what is missing
  is somewhere to file it on the item's Documents tab. Grouped by item template and type,
  listing the sections that item template does have. Often the answer is to leave it — a
  document with no section still attaches.
- **Nothing fitted and nothing was proposed.** The reader could not tell what it was at all.
  This is the one where you have to open the document yourself.
- **Read twice, settled differently.** You pick, and the row carries both answers.
- **Nothing readable.** Describe it yourself, or get it re-saved in a readable format.

For each one you get the file name, its folder and the evidence line. That trio is usually
enough to answer in a single pass.

### 6. The cross-check

One more pass sets the individual answers against each other, which is a different thing
from checking each answer alone. It reports two patterns: one quoted line resolving to
several different types, and one evidence line written across documents from different
forms.

Both are short by construction. On the run this came from, 1,632 contradictory answers sat
on **eight quotations** — eight things for a person to look at, not 1,632 rows. Whatever it
finds comes to you with both readings shown together, because neither is more likely right
than the other.

---

## Step 10 — Arranging the Documents tab

Every document now has a type, so where each kind of document belongs on each kind of item's
page can be answered from the rows themselves. No file is opened and nothing is re-read.

Expect **most of the answers to be new sections rather than lookups**. On one real export
the app held five sections across three item templates, and 68 of 82 rows had no section at
all. Where the app already arranges a document type into a section, the app's own
arrangement wins and any disagreement is reported rather than applied.

You do not review this in chat. It lands on two sheets of the workbook where a column called
`is_new` says `yes` on a yellow fill and `no` on a green one, and that is where you read it.

---

## Step 11 — Approve the preview

Before the workbook is written, the run publishes one page and asks you to approve it.

### 1. Read all six parts

1. **A diagram of your folder tree**, with each level labelled by the role it was given.
2. **One card per branch**: kind of item, what identifies it, how many of that kind of
   item the documents actually reached, and the document count. "Reaching 40 of 300 items"
   is worth seeing before the workbook exists.
3. **The document types actually used**, with a count each, and the sections they fall into
   per item template — so the shape an item's page will take is visible in advance.
4. **A preview of every sheet the workbook will have**, with a real header row and three to
   five real rows: real identifier values, real file names, real type names.
5. **What will be flagged as an issue**, by file name with its evidence, grouped by reason —
   and separately what will be listed as ignored, as a count per rule.
6. **The attachments worth spot-checking** — the lowest-confidence rows that are still going
   into the workbook.

### 2. Spend your attention on the sheet preview

Those are the rows that will be created. Everything else on the page is context for them.

### 3. Correct and re-approve

Give your corrections in chat. They are applied and the page is republished **at the same
link**, so you can keep the tab open. Nothing is written until you approve.

---

## Step 12 — Take the workbook

### 1. Find it

The workbook is written as `DOCUMENT_UPLOAD_WORKBOOK.xlsx` **inside the customer's documents
folder** — the folder you pointed the run at, not a working directory. The run gives you the
full path.

If that file is already open in Excel the write fails with a permission error. Close it and
ask the run to write again — it deliberately will not write to a second file name, because
two workbooks in one folder is how the wrong one gets uploaded.

### 2. Read the hand-over summary

The run tells you, per sheet, which kind of item it attaches documents to and how many; what
sections each item template ended up with; how many files were ignored and how many have
issues; and the two or three lowest-confidence attachments worth spot-checking.

### 3. Know what is in the file

Three sheets come first, before any data:

- **`README`** — what the run did. One row per data sheet with the counts, plus the totals
  that let you check them: files in the folder, files carried, attachments written, files
  ignored, files with issues. Then two blocks of work for somebody in the app: **document
  types to create**, one row per proposed name with the number of documents waiting on it,
  and **types no section renders**, one row per item template and type.
- **`IGNORED_FILES`** — every file left out by *your* decision at Step 5, with the rule
  that caught it. These need nobody. They are listed per file rather than summarised so that
  a rule which caught more than you intended is visible.
- **`FILES_WITH_ISSUES`** — every file the run could not attach, with the reason in the
  words of whichever step found it, and the evidence where there is any. **This is the short
  list, and it is the one to read.** A folder can ignore twelve thousand files and still have
  only forty that need somebody.

Then the data:

- **One sheet per kind of item**, named after the app's own table (`raw_materials_documents`,
  `products_documents`). One row per document per item — a document attached to two items
  gets two rows.
- Each row carries the item identifier, the item's id, the document type and its app id, the
  file name, the file's SHA-256, the item template, the source folder, and then the review
  columns: confidence, evidence and the quoted line.
- **`Document Templates`** and **`Document Sections`** — how the app's Documents tabs should
  be arranged, with the `is_new` column filled yellow for `yes` and green for `no`. That is
  the only colour anywhere in the workbook, and these are the two sheets somebody reads to
  decide what to build in the app before the migration runs.

Every sheet with a header row has that row frozen and bolded with the filter turned on. On
the two file lists the filter is the whole point — it is how you read one reason at a time.

Every file under your folder appears in exactly one place: a data row, an ignored row, or an
issues row. If the totals do not add up, something went wrong.

### 4. Stop touching the document files

The workbook records what each file was at the moment it was hashed. From here on, do not
edit, re-save or re-export any of them — an edited file no longer matches its row and will
not tick off at upload time.

---

## What happens next

You are done on your machine. The remaining work is all in Worldmaker, and it is
[the document uploads guide](../WORLDMAKER/DOCUMENT_UPLOADS.md) from Step 4 onwards:

1. Attach `DOCUMENT_UPLOAD_WORKBOOK.xlsx` in the customer's app chat and ask for the
   migration. The assistant finds the `file_name` and `file_sha` columns and creates a card
   that knows it is waiting for documents.
2. Open the card's upload window on the Migration board and drop the document files in.
   Each is matched to its row by hash, so the folder structure no longer matters and neither
   does renaming — only the bytes.
3. Drag the card onto Staging, then onto Production.

Two things from this run carry forward and are worth remembering when you get there:

- The document types listed on the `README` as needing to be created have to exist in the
  app **before** the migration runs, or those documents cannot attach.
- The files you upload must be **the same files this run hashed**. This can be days later,
  so keep the folder as it was.

---

## Troubleshooting

**Problem: the run stops immediately saying `uv` or `openpyxl` is missing**

That is the tool check doing its job. Neither is something you can work around: without
`uv` no document can be read, and without `openpyxl` no spreadsheet can be written. Ask
someone on the engineering team to install whichever it named, then start again.

**Problem: it says the two export files do not match**

Both file names end in the same short id when they come from one export. Different ids mean
you have a workflow file paired with an older items list, which is the kind of mistake that
produces a workbook full of items that no longer exist. Go back to the app chat and take a
fresh export of both.

**Problem: a whole branch shows a match rate near zero**

Almost always the anchor is one folder level off. If the identifier lives at
`Raw Materials/RM-0142/SDS/file.pdf`, the anchor is the second level, not the third. Correct
the row on the board and it re-measures immediately. This costs nothing at this point, which
is exactly why the check happens here.

**Problem: folders that look right are reported as matching no item**

Read the near-misses the check offers. It shows the app's closest actual identifiers, so a
spelling difference or an extra character is visible. If the folder name is genuinely
correct and the app does not hold that item, the item has to be created in the app first —
this flow attaches documents to items that already exist and never creates them.

**Problem: two items share the same identifier**

A document naming that value resolves to *no* item, deliberately, rather than being filed
against a coin toss. Somebody settles it in the customer's app and you re-export. This is
also reported at the export step in Worldmaker, so it should not be a surprise here.

**Problem: extraction has been running for ages**

Expected on a large folder — half a second per file, and considerably more per page for
scans. A folder of 3,500 files took about 29 minutes. Re-runs reuse everything already
converted and take seconds, so an interrupted run is not a disaster.

**Problem: a lot of files came back unsupported**

If they are `.doc`, `.rtf`, `.odt`, `.ods` or `.odp`, LibreOffice is not installed on your
machine — installing it makes all of them readable. If they are `.pages`, `.numbers`,
`.key`, `.7z` or `.rar`, nothing will read them and the customer has to re-save them.
Either way you get the exact list rather than a count.

**Problem: nearly every form comes back with no matching document type**

That is a genuine finding, not a fault, and it is the single most valuable thing this run
produces. The app's list of document types is closed — a migration can only land on words
the app already has. Take the list of missing types back to the app, create them, re-export
both files, and re-run. For a form carrying hundreds of documents this is unambiguously
worth the round trip.

**Problem: I pasted my form review back and it was refused**

The page copies two things: readable prose, and a machine-readable block. The run needs
both, and it refuses a paste without the block rather than trying to interpret the prose —
guessing there would silently change which documents get read again. Copy again using the
page's own copy button, which takes both together.

**Problem: a form clearly holds two different kinds of document**

Do not mark it as broken. Use the middle answer — "same paper, different documents" — and
describe in your own words what tells them apart. The form stays intact and its documents
are read one at a time carrying your description, which is what makes them come out right.

**Problem: lots of rows have low confidence and I do not know if that is bad**

Low confidence means two document types both fitted, not that the document was hard to read.
It is a measure of ambiguity, not legibility. Those rows have usually already been read a
second time. Sort by the confidence column in the workbook and spot-check the bottom few
against the actual files.

**Problem: the workbook will not write, permission denied**

The file is open in Excel. Close it and ask the run to write again. It will not write to a
second name instead, on purpose.

**Problem: I cannot find the workbook**

It is inside the customer's documents folder — the folder you pointed the run at — not in
any working directory. The run prints the full path when it hands over.

**Problem: I need to change something after the workbook is written**

Corrections are cheapest at the preview step, before the file exists. After that, ask the
run to correct and rebuild; it does not need to re-read the documents, because everything
already extracted is reused.

---

## Open questions

These are things this guide could not pin down from the current material. Check with
engineering rather than assuming.

- **Resuming an interrupted run.** Re-running the document extraction is explicitly cheap
  and reuses what is already converted. Whether an interrupted *run* as a whole can be
  picked up from where it stopped, rather than restarted, is not documented.
- **Total run time is not measured.** Only the extraction pass has published timings. How
  long grouping, reading and cross-checking take on a large folder is recorded nowhere, so
  say it is unknown rather than estimating.
- **What to do when publishing a page is unavailable.** The fallback is documented as
  writing the same content as a file in the working folder and being walked through it. What
  that actually looks like for the sample-heavy form review page, which relies on showing
  you pictures of documents, is not described.

---

## Related guides

- [Document uploads in Worldmaker](../WORLDMAKER/DOCUMENT_UPLOADS.md) — the two halves of
  this flow that happen in the web app: getting the export files out of the app chat before
  this run, and attaching the workbook, uploading the files and applying the card afterwards.
- [Migrations](../WORLDMAKER/MIGRATIONS.md) — the wider migration flow this sits inside.
