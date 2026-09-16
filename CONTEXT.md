# Document upload

The language of this plugin's skills: taking a customer's folder of files and producing a workbook that
attaches them onto items that already exist in their Worldmaker app (`upload-documents`), and guiding a
person through the wider journey that workbook belongs to (`ask-worldover`).

## Language

### What is being read

**File**:
One path on disk under the folder the customer gave. Two files can hold identical bytes.
_Avoid_: document (when you mean a path)

**Document**:
One distinct content, identified by its SHA-256. Several files can be one document.
_Avoid_: file, doc

**Attachment**:
One document on one item. A workbook data row is exactly one attachment.
_Avoid_: upload, link, row

**Reading**:
One sub agent's classification of one document. The unit is `(sha, table)` — copies that share both
share an answer, because they are picked from the same list of document templates.

**Form**:
The blank stationery a *document* is printed on — its title, field labels and column headings, never the
values typed into them. Documents are grouped by form before anything is classified, and a form carries
one title and one description of its own. A form is not a *document template*: it says what the paper is,
not what the app calls it. Two suppliers' safety data sheets are two forms; one form used for two purposes
is still one form. A form names one *document template*, unless it is *split by value*.
_Avoid_: group (a *section* is the app's group), cluster, layout, template

**Split by value**:
A *form* whose documents are not all the same *document template*, because what tells them apart is what
was typed into the form rather than the form itself — a blank specification and the same sheet with its
results filled in. Such a form is not wrong and does not dissolve: its documents are classified one at a
time, while every other form is answered once.
_Avoid_: mixed (that is a form holding documents printed on different stationery), contested, ambiguous

**Structure view**:
One document's text with everything its own *form* does not repeat blanked out, in the order it was read.
What a naming sub agent is shown. Never compared to anything — comparison uses the signature, which is an
unordered set of the same words.
_Avoid_: masked text, skeleton

### What is being read against

**Item**:
A record that already exists in the app, carrying an identifier, an id, an *item_template* and an
archived flag. Rows in `ITEMS.csv`.
_Avoid_: material, product, record

**Item kind**:
The app table an item lives on, which owns the sheet the item's documents go on: `raw_materials`,
`products`.
_Avoid_: type, entity, table (in prose; `table` is the field name)

**Item template**:
The blueprint an item is built from, which owns the *sections* its documents are arranged into. Many
item templates share one item kind.
_Avoid_: blueprint, schema, layout

**Document template**:
The kind of document the app recognises, carrying the app's own id. Permitted per *item kind*.
_Avoid_: category, type, classification

**Section**:
A named group a *document template* is arranged into on one *item template*. Two item templates with a
"Safety" section have two sections, not one shared.
_Avoid_: group, tab, heading

### What comes out

**Pick**:
An answer naming something the app already has. A pick attaches on its own.

**Proposal**:
An answer naming something the app does not have, which a person must create before the document can
land. Worse than a *pick* only where the app's list holds the right *document template*: there a proposal
is work somebody did not need to do. Where the list holds nothing that fits, a proposal is the only honest
answer and a pick is a filing error — one that attaches silently, which a proposal never does.
_Avoid_: invention, suggestion, new type

**Exception**:
A file the run could not turn into an *attachment*, carried onto the workbook's `FILES_WITH_ISSUES` with
the reason in the words of the step that found it. Every one is somebody's next action.
_Avoid_: failure, skip, error

**Exclusion**:
A file somebody decided not to migrate, caught at the gate before anything was read, listed on the
workbook's `IGNORED_FILES` with the rule that caught it. An exclusion needs nobody — it is recorded so
the totals add up and so a rule that caught more than intended is visible.
_Avoid_: exception, filtered, dropped

### How the work runs

**Step**:
One numbered unit of work in a skill or a guide, with a "Done when" and usually a question in it. The
same word covers both sides: a step of a run, and a step the person takes on their own screen.
_Avoid_: phase, stage, part

**Pass**:
One mechanical script run inside a *step*, counted in a unit of its own and reporting how far along it
is. A pass asks nobody anything and settles nothing a person must confirm — that is what separates it
from a *step*, which has a "Done when" and usually a question in it.
_Avoid_: phase, job, stage

**Conversation**:
The chat a run happens in. It launches *passes*, reports what they print and asks what a *step* owes the
user — and it holds no state of its own, because everything a run knows is written under
`.workflow/active/${sessionId}/`. That is what makes it disposable at a *step* boundary, and why a data
file read into it is a data file paid for on every turn after. See `docs/adr/0010`.
_Avoid_: context (that is what the conversation holds, not the thing itself), session (that is
`${sessionId}`, which outlives any one conversation), agent, thread

**Journey**:
Everything between a customer's raw files and their data live in Production, across as many *steps*,
screens and machines as it takes. A *step* belongs to one journey; a run covers part of one.
_Avoid_: flow, process, pipeline

**`{WORLDMAKER}`** and **`{LOCAL}`**:
The two agents `ask-worldover` runs as, and the tokens its docs use to mark which one a *step* is
addressed to. `{WORLDMAKER}` is the chat inside the customer's app, which reads the app's data and
publishes cards. `{LOCAL}` is Claude Code on the user's own machine, which reads their files and builds
the workbook. Neither can do the other's half, and this plugin is `{LOCAL}`.
_Avoid_: side, environment (an *environment* is Development, Staging or Production)

# Composition

The language of `extract-composition-from-documents`: reading a customer's supplier documents to say
what each of their raw materials is made of.

## Language

**Composition**:
What one raw material is made of, as one document states it: a list of ingredients with a quantity
against each. A composition belongs to a *material*, never to a document - two suppliers' sheets for one
material are two candidates for its composition, not two compositions.
_Avoid_: formulation (that is a finished product), recipe, breakdown

**Single source**:
The one document a composition is taken from, whole. A composition assembled from several documents is
not a composition with better coverage; it is a different kind of answer, one nothing downstream can
check. A *safety data sheet* is never one. See `docs/adr/0009` and `docs/adr/0012`.
_Avoid_: primary (the *role* on the reference sheet is `PRIMARY`; the concept is the single source)

**Safety data sheet**:
A supplier's hazard document. Its section 3 names the substances classified above a cut-off, so it can
be complete and still omit the water — which makes it a *document template* like any other and never a
*single source*. Its CAS and EC numbers are still used, as reference against a *candidate*.
_Avoid_: SDS as a bare word when what is meant is the composition it is not being read for

**Material**:
An *item* on the `raw_materials` table, seen from this skill. The wider plugin says *item*, because it
also means products; a composition only ever belongs to a raw material, and this is the word for one.
_Avoid_: ingredient (that is what a material is made of), substance, product

**Candidate**:
One file that might state a material's composition, shortlisted by score before any agent reads it. A
candidate is a guess about a file; what it turns out to be is the sub agent's answer.
_Avoid_: match, hit, source (a *single source* is the one that won)

**Composition reading**:
One sub agent's answer for one *material*: the *candidate* it picked as the *single source*, and the
rows it transcribed off it. Distinct from a *reading* in the document-upload sense, which is one
classification of one `(sha, table)`.
_Avoid_: reading on its own (it is already taken), extraction, transcription

**Balance row**:
An ingredient a document gives no figure for, stating only that it makes up the rest - `Balance`,
`to 100%`, `q.s.`. Carried with its words and no numbers, because the complement of the other rows is
arithmetic the document does not contain.
_Avoid_: remainder, filler, the rest

**Recut**:
A recorded decision that the run picked the wrong document for one material, naming the file it should
have used. Replayed by script rather than typed into the workbook, so a rebuild reproduces it.
_Avoid_: override, correction, fix

**Kind of date**:
What a document calls the date it prints - issue, revision, review, print, edition. Which one a document
carries decides whether it is newer than another: a print date is when somebody pressed print, and a
review that changed nothing does not age a document forward.
_Avoid_: timestamp, version (a *version* is a label the supplier chose, not a date)
