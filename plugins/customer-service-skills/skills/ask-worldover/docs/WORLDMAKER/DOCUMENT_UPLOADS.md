# Uploading a customer's documents into their app

This guide takes you from a folder of PDFs and Word files on your computer to those
documents attached to the right items inside a customer's Worldmaker app.

Most of this is `{WORLDMAKER}` — the Worldmaker web app. Building the workbook is `{LOCAL}`,
on the user's own machine, and is marked where it comes up.

Document uploading is one phase of a wider migration. For the rest of that journey —
starting a migration, moving data between environments, and everything that is not about
document files — see [Migrations](MIGRATIONS.md).

---

## Before you start

**What has to be true already**

- The **items** the documents belong to already exist in the customer's app — the raw
  materials, products, components or formulations you are attaching files to. This flow
  attaches documents to existing items; it does not create them. If the items are not in
  the app yet, that is a data migration first, and the documents come after it.
- Those items exist in the app's **Development** environment. When the assistant publishes
  the plan it checks every reference against Development, so an item that is not there
  makes the plan fail. For a customer already live in Production, Development usually has to
  be made to mirror Production first — reset it, then copy Production down. That is a
  destructive step with its own instructions in
  [Migrations](MIGRATIONS.md#before-a-document-migration-on-a-live-customer).
- The customer's app is **deployed to both Staging and Production**. The upload window
  pushes every file to both environments together and refuses to start if either one is
  not deployed.
- You have access to the project in Worldmaker, and can open its editor.

**What you need on your own machine**

- The folder of customer documents, all of it, in one place.
- Claude Code, with the `upload-documents` skill available.
- The tools that run checks for before it starts anything — see
  [the local guide](../LOCAL/DOCUMENT_UPLOAD.md), which lists them and what each one blocks.

**How long it takes**

Not a single sitting. The slowest machine work is reading the documents, and you will be
asked to confirm a good many decisions along the way. The upload at the end often happens
days after the workbook was built, so keep the customer's original files where you can
find them again.

**Two things worth knowing up front**

- **Your document files never leave your computer until the very last step.** The
  workbook only records each file's fingerprint. You upload the actual files at the end,
  from inside Worldmaker.
- **A document is identified by its contents, not its name.** Every file is matched by its
  SHA-256 hash. That means you can rename files or move them between folders after the
  workbook is built and everything still matches — but if you *edit* or *re-export* a
  document, it becomes a different file and will no longer match its row.

---

## The whole journey at a glance

There are six steps. Steps 1, 4, 5 and 6 happen in Worldmaker; steps 2 and 3 happen on
your own machine.

| Step | Where | What happens |
| --- | --- | --- |
| 1 | Worldmaker, app chat | The assistant exports the app's document vocabulary and its item list as two files you download |
| 2 | Your machine | The documents folder is put into a shape a run can read |
| 3 | Your machine, Claude Code | A run reads every document and builds the upload workbook — [its own guide](../LOCAL/DOCUMENT_UPLOAD.md) |
| 4 | Worldmaker, app chat | You attach the workbook; the assistant creates a migration card |
| 5 | Worldmaker, Migration board | You drop the document files into the card's upload window |
| 6 | Worldmaker, Migration board | You move the card onto Staging, then Production |

---

## Step 1 — Export the app's vocabulary and item list — `{WORLDMAKER}`

Before anything can be matched, you need two things out of the customer's app: the words
the app uses for its document types, and the list of items documents can attach to. The
app's assistant produces both.

`{WORLDMAKER}`: the assistant this step asks for is you, and the export is the
`worldover-export-data-for-document-upload` skill. Walk the user through what it will ask
them, then offer to run it. The two steps below are how the user reached you; the
confirmations from **3** on are yours to ask once they say go.

### 1. Open the project's app chat

Open the project in Worldmaker and use the chat panel in the editor. This is the same chat
you would use to ask for anything else about the app.

### 2. Ask for the document upload export

Type **/export-document-data**, or say what you want in plain language:

> I need to upload a folder of documents for this customer. Can you export the document
> upload data?

Either way the assistant reads the app's live database to work out which kinds of item can
carry documents.

### 3. Confirm which kinds of item your documents are for

The assistant shows you a table: one row per kind of item that can hold documents (raw
materials, products, and so on), with how many items of that kind exist and how many
document types are set up for it.

Reply in the chat with the ones your documents are for. Any subset is fine. If your folder
only holds raw-material documents, say so — a smaller export is a simpler run later.

### 4. Approve the customer identifier for each kind

This is the most important thing you will be asked, so it is worth slowing down for.

The **customer identifier** is the value the customer actually calls an item by — a code,
a part number, a primary identifier. It is not the app's internal database id. It is what
your document folder names will be matched against later, so it has to be the value that
appears in those folder names.

The assistant inspects the candidates, proposes one, explains why, and names the exact
column it lives in. Read the proposal against your own folder names and either approve it
or correct it.

The assistant will also report **collisions** — two items sharing the same identifier
value. A collision is not fatal, but it means a document naming that value cannot be
resolved to one item. You have three ways out, and the choice is yours:

- Fix it in the app, and ask the assistant to check again.
- Leave that item out of the export.
- Accept the risk and carry on.

Occasionally the best identifier is not a real column on the item's table — it lives in
the app's custom-field system instead. The assistant will say so plainly. When that
happens, the workbook cannot express it, and the customer needs either a real column or a
different identifier.

### 5. Download the two files

When you have approved everything, the assistant writes two files and they appear in the
chat as download chips. Their names look like this:

```
<PROJECT>_DOCUMENT_UPLOAD_WORKFLOW_<id>.json
<PROJECT>_DOCUMENT_UPLOAD_ITEMS_<id>.csv
```

`<PROJECT>` is the app's own repository name, and the same short id appears on both files
so you can tell at a glance that they belong together.

- The **workflow** file holds the app's vocabulary: every document type the app knows, and
  for each kind of item, the sections its Documents tab carries and which document types
  sit in each section.
- The **items** file is a spreadsheet with one row per item: the item's id, its customer
  identifier, its name, which template it is built from, and whether it is archived. It is
  a plain CSV, so you can open it in Excel.

Both are needed. The workflow file gives the app's wording; the items file says which
template each item is on, which is what decides the sections a document can be filed into.

Save them next to your documents folder. Download both — a workflow file paired with a
stale items file is a real risk, and the shared id in the file names is how you catch it.

The assistant also tells you the row count per kind of item, how many items are archived
or have no template, and any collisions you chose to proceed with. Keep that message; it
is the sanity check for the counts you will see later.

---

## Steps 2 and 3 — Build the workbook — `{LOCAL}`

These two steps happen in Claude Code on your own computer, not in Worldmaker, and they
are a guide in their own right.

**Read [Building the document upload workbook on your own machine](../LOCAL/DOCUMENT_UPLOAD.md)
and come back here when you have `DOCUMENT_UPLOAD_WORKBOOK.xlsx`.**

In outline, so you know what you are walking into:

- You get the documents folder into a shape the run can read. Folder names are the only
  thing that says *which item* a document belongs to; reading the document says *what kind*
  of document it is. The run never lets one guess at the other's job.
- You start the `upload-documents` skill and hand it the two files from Step 1, plus the
  documents folder.
- The run maps the folder, agrees each branch with you, sets aside the files nobody wants,
  groups the documents by form, and asks you to eyeball those forms before it commits to
  anything.
- It then hashes and reads every document, decides what each one is, and puts the whole
  result to you as a review page before writing the workbook.

It ends with `DOCUMENT_UPLOAD_WORKBOOK.xlsx` written **beside your documents folder**. Two
things from it matter to the rest of this guide:

- Every row identifies its file by a SHA-256 of the exact bytes. That is what Step 5
  matches your files against.
- The `IGNORED_FILES` and `FILES_WITH_ISSUES` sheets list every document that did **not**
  make it into a data row, with the reason. Read those before you go on — a document is in
  exactly one place, a data row or one of those two sheets.

**Do not edit or re-export the documents after the workbook is built.** An edited or
re-saved file has different bytes, so it no longer matches its row and Step 5 will not
recognise it.

---

## Step 4 — Start the migration with the workbook — `{WORLDMAKER}`

Back in Worldmaker.

`{WORLDMAKER}`: the assistant here is you again. Once the workbook is attached, say what
preparing the migration involves and offer to do it.

### 1. Attach the workbook to the app chat

Open the project editor and go to the app chat. Click the **+** button on the chat
composer, and under **Modes** turn on **Add Files**. Attach
`DOCUMENT_UPLOAD_WORKBOOK.xlsx`.

Attaching it to the chat is the only way a workbook gets in.

### 2. Ask the assistant to prepare the migration

Tell it what the workbook is, for example:

> This workbook attaches documents to raw materials that already exist in the app. Please
> prepare the migration.

The assistant reads the sheets and looks for the `file_name` and `file_sha` columns.
Finding them is what makes it expect document files at all — it creates the document
records and marks each file as still to come. The rows will be in place; the files are not.

It will agree the mapping with you before it starts, and will ask about anything the
workbook does not settle on its own. Answer those questions rather than letting it guess.

### 3. Check the card appeared

When the assistant publishes, it reports how many records the plan holds and how many
documents it marked. A card now exists on the Migration board.

The assistant cannot upload the files for you. Marking which files are wanted is the whole
of its part; pushing the bytes is yours.

---

## Step 5 — Upload the document files from the card — `{WORLDMAKER}`

### 1. Open the Migration board

In the project editor, go to **Settings** and choose **Migration** in the left sidebar.
Your card is on the board, in the Development column's shelf.

A card that is waiting for documents has an amber left edge and reads **Waiting for
documents**. Under the card title there is an amber link reading, for example,
**12 documents to upload**.

You cannot drag the card anywhere while that count is above zero. Hovering it explains
why: the records would land with no files behind them.

### 2. Open the upload window

Click the **N documents to upload** link. A window titled **Documents to upload** opens.

At the top it shows the deployment state of **Staging** and **Production**. Both need to
read "deployed". If either does not, the window says so and the drop area is disabled —
the files go to both environments, so both have to be there to receive them.

Below that is the list of every document the card is waiting for: file name, and under it
the item it belongs to. Each row reads either "awaiting" or "uploaded".

When the window opens it checks what is already in both environments, so if you uploaded
some of these on an earlier visit they are already ticked off.

### 3. Drop the files in

Drag your document files onto the drop area, or click it to pick files, or use **or choose
a whole folder** to pick the folder.

**Dropping the whole folder is the normal way to do this.** Every file is hashed as it
arrives, and anything this card did not ask for is quietly ignored. You do not have to
find the exact subset.

You will see "Reading the files…" while the hashing runs, then a progress bar reading
"Uploading to Staging & Production…" with a running count.

Each file goes to both environments together and only ticks off as **uploaded** once it
has landed in both. A file that made it into one environment but not the other does not
count as uploaded, and will still be waiting.

Progress is saved file by file, so closing the window part-way through keeps whatever
landed.

### 4. Deal with anything that was skipped

If a file could not be uploaded, an amber panel lists it by name with the reason, and it
stays outstanding. Fix the cause and drop it in again.

### 5. Finish when the count reaches zero

When every document is in, the window's heading changes to say every document on the card
is in Staging and Production, and the card is free to move. The button in the corner
becomes **Done**.

The link on the card now reads **All documents uploaded**. It stays clickable, so you can
reopen the list any time to check what went where.

---

## Step 6 — Move the card to Staging and Production — `{WORLDMAKER}`

Uploading puts the files into a staging area belonging to this card. Applying the card is
what writes the records and puts each document's bytes at its final home in the app.

**A document card never goes to Development.** There is no "Add to Development" button on
it — that button only ever appears on a card carrying ingredients that needed matching, and
a card can only be dropped on Staging or Production. Development holds the shelf the card
sits on; the document bytes go to the other two environments. So once the upload count
reaches zero, Staging is the next stop.

### 1. Drag the card onto Staging

The card is now draggable. Drag it onto the **Staging** box.

A review panel opens. Before it will run, it checks that the files you uploaded really are
where they should be. If any are missing it stops and names them, and you go back to the
upload window.

### 2. Start the apply

Confirm in the panel. You will see two things happen in order:

- **Applying records** — the document records being written, table by table.
- **Placing documents** — the file bytes being put in place. This runs in up to three
  passes: "Checking what's already in place", "Copying uploaded documents" (the files you
  just uploaded), and "Copying from Development" (any files the app already held).

Documents are placed *after* every record is written, so a shortfall here leaves records
in place with documents that will not open. That is why the count at the end matters.

### 3. Read the file count

When it finishes you get a line like "412 document file(s) copied". If some did not copy,
you get an amber panel naming examples and saying those documents will not open until
their files are in place. Re-applying the card once storage is reachable brings the rest
across — nothing is lost, and applying again is safe.

### 4. Repeat onto Production

Drag the same card onto **Production**. Production asks you to type the project name back
to confirm. The same two phases run again.

Both environments have to be done. Applying to Staging alone leaves Production without the
documents.

---

## Checking the result

Three checks, cheapest first:

1. **On the card.** It reads **All documents uploaded**, and the apply reported a document
   file count with no shortfall.
2. **In the upload window.** Reopen it from the card. Every row reads "uploaded".
3. **In the customer's app.** Open two or three items — ideally the low-confidence ones the
   workbook run flagged — and look at their Documents tab. The documents should be there,
   under the right sections, and should open.

If the workbook run's review page flagged rows worth spot-checking, this is where you spend
that attention. A confidently-wrong classification looks exactly like a right one until
somebody opens the file.

---

## Troubleshooting

**Problem: the card will not drag anywhere**

- Check the amber link on the card. If it says "N documents to upload", that is why — the
  count has to reach zero first.
- A card can also be held back by unresolved ingredients, which is a different question the
  card asks. See [Migrations](MIGRATIONS.md).

**Problem: I dropped a file in and it did not tick off**

The file's contents no longer match what the workbook recorded. This almost always means
the document was edited, re-saved or re-exported after the workbook was built — even
opening and saving a Word file can change its bytes.

Find the original file. If it is genuinely gone, the fix is to rebuild the workbook from
the documents as they are now — back to [the local guide](../LOCAL/DOCUMENT_UPLOAD.md).

**Problem: "Both environments have to be deployed before documents can be uploaded"**

The customer's app is not deployed to Staging, or not to Production, or neither. Files go
to both together, so both have to exist. Get the app deployed to both, then reopen the
window.

**Problem: "This card has no slug, so there is nowhere to store its documents"**

Ask the assistant in the app chat to publish the migration again. This is a fault in how
the card was created, not something you can fix from the window.

**Problem: at apply, "N document file(s) aren't in Staging and aren't already in place"**

The apply re-checks the bytes before it writes anything, and some are not there. Open the
card's upload window, drop those files in again, and re-check. This is the safety net
working — nothing was written.

**Problem: at apply, "document file(s) on this card have no usable content hash or
destination"**

The plan the assistant published is malformed for those rows. Ask the assistant to rebuild
the script. The apply blocks rather than skipping, because a skipped one would land a
record with nothing behind it.

**Problem: the classifier could not find a type for some documents**

The app's list of document types is closed — the migration can only land on words the app
already has. If the run proposes a type the app does not have, somebody has to create that
document type in the app before the migration runs. The run surfaces these as a group,
with a count, precisely so you can take the list to the customer.

**Problem: anything else that went wrong while building the workbook**

Illegible folder trees, unreadable or legacy-format files, the exclusions gate, the form
review — all of that belongs to the local run. See
[the local guide's troubleshooting](../LOCAL/DOCUMENT_UPLOAD.md).

**Problem: the download chips did not appear in the app chat**

A file name that has already been used in the same conversation produces no download at
all. Ask the assistant to produce a fresh export; each hand-over gets a new short id in the
file names precisely to avoid this.

**Problem: two items share the same identifier**

The Step 1 export reports these. Your options are to fix it in the app and re-export, to
leave that item out, or to accept the risk. There is no fourth option, because a document
naming a value that two items share cannot be resolved to either one.

---

## Open questions

These are parts of the flow this guide could not pin down from the current material. Check
with engineering rather than assuming.

- **Where documents fit relative to the rest of a migration's ordering.** Whether the
  document card should be applied before, after or alongside the data cards for the same
  customer is a sequencing question that belongs with [Migrations](MIGRATIONS.md).

---

## Related guides

- [Building the workbook on your own machine](../LOCAL/DOCUMENT_UPLOAD.md) — Steps 2 and 3
  in full detail.
- [Migrations](MIGRATIONS.md) — the wider migration flow this fits into.
