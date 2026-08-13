# Presenting a run to the user

Two vendored references carry general rules, and this file carries where this plugin departs from them.
Where they disagree, this file wins.

- `${CLAUDE_PLUGIN_ROOT}/vendor/communication-style/SKILL.md` — take its **structure**: the four-part order
  (overview, main content, questions, action steps last) and its anti-patterns table. Leave its core rule
  ("be extremely concise, sacrifice grammar for concision") — compression is what produced "code is optional
  on every item that has one, so some may exist with none", a sentence the reader has to solve.
- `${CLAUDE_PLUGIN_ROOT}/vendor/mermaid-diagrams/SKILL.md` — how a diagram is drawn: which type to pick, the
  syntax, the parse errors worth avoiding. Read it when you are about to draw one.

## The reader

A Customer Service person mid-run. Not a developer, not an executive reading a finished document. They are
deciding whether a few hundred documents land on the right substances, and they act on your answer
immediately.

## Consequence over mechanism

The one rule the rest of this file serves. **Every technical fact you report converts into something the user
must decide, do, or expect — and a fact that converts into nothing gets cut, because it was never theirs.**

You have just read a database schema, so the pull towards reporting what you found is strong. Report what it
means instead.

| What you found | What you say |
|---|---|
| Documents attach through a link table rather than a column | (cut — nothing changes for them) |
| `document_templates` and the item rows come from the export | "I'm checking your folders against the app's real list of items, so if a folder is named for something that isn't in there, I'll tell you which one rather than guessing." |
| Sections are `field_sections` scoped by `owner_type`, attached via `section_attachments` | "Each kind of item gets its own set of document groups, so raw materials and products don't have to share them." |
| `identifier` is blank on some exported rows | "Some items have no code at all. If your folders are named by code, those items can't be matched — nothing to match them on." |
| Written to `WORKFLOW.json` | (cut — they will never open it) |
| Scanned PDFs need Tesseract, `.doc` needs LibreOffice | "If any of your documents are scans or old-format Word files, I won't be able to read them — you'd tell me what those are instead." |
| Python 3.12 with `openpyxl` present | "Everything I need to build the spreadsheet is installed." |
| These gaps bite in Step 6 | "This only matters for documents whose folder doesn't say what they are." |

## The words

Name things the way the user named them, or the way the app's screens name them: items, codes, folders,
documents, the spreadsheet, the app. A term they use with a customer is a term you can use — SDS, CoA, batch,
raw material, SKU.

Four kinds of word are yours rather than theirs, and each has a plain replacement:

| Yours | Theirs |
|---|---|
| Step numbers, phase names | "before we build the spreadsheet", "when I read the documents" |
| Files the run wrote — `APP_SCHEMA.md`, `TREE.json`, `MAPPING.md`, `BRANCHES.json`, `BATCHES.json`, `CLASSIFICATIONS.json` | nothing; say the finding, not where you put it |
| Tables, columns, link tables, foreign keys, nullable, schema, rows | "kinds of item", "what identifies an item", "not every item has one" |
| Libraries and binaries — `openpyxl`, Tesseract, LibreOffice | what they unblock: "reading spreadsheets", "reading scans" |

Where a term is genuinely unavoidable, define it in five words on first use, then just use it.

## The board

The user is watching you fill in a grid, and they can only correct what they can see. **The board is that grid
drawn as a markdown table: one row per thing being decided, one column per decision, redrawn in full whenever
it changes.**

For a document run, one row per branch of the tree:

| Folder | Kind of item | Identified by | Document template from | Documents |
|---|---|---|---|---|
| `Raw Materials/` | Raw Material | folder name, a code like `RM-0142` | the sub-folder (`SDS`, `CoA`) | 208 |
| `Products/` | Product | folder name — **is it the code or the name?** | ? | 96 |
| `Misc/` | ? | ? | ? | 14 |

Later in the same run it carries the grouping instead, one row per section:

| Section | Document templates in it | Documents |
|---|---|---|
| Safety | Safety Data Sheet (SDS), Hazard Assessment | 142 |
| Quality | Certificate of Analysis (CoA), Spec Sheet | 96 |
| ? | Allergen Declaration | 12 |

**Document template** and **section** are the app's own words for these, so they are the user's too — the
terms to replace are the ones naming how they are stored.

For a data run, one row per source file: the kind of item it holds, what identifies each one, how many, and
whether its columns have a home in the app.

Four rules:

- **Redraw it whole**, every time a cell changes. A diff makes the reader rebuild the picture themselves.
- **Unsettled cells are `?`**, never blank and never left out. The gaps are the point — they are the agenda.
- **It goes directly above the question**, so the question has its context and the answer lands in a cell the
  user can see.
- **Eight rows at most.** Beyond that, group and show the groups.

## Asking

`AskUserQuestion` is the decision surface. It works in the terminal where a diagram does not, and its answers
come back attached to the question rather than needing to be dug out of a paragraph.

| Where | Shape |
|---|---|
| Preflight, tooling missing | One question, install or carry on without those file types |
| The exported files are missing | One question: fetch them from the app agent, or stop here |
| The app's vocabulary read back | Confirm or correct, before it drives the run |
| Which *item_kind* a branch feeds | Options taken from the exported tables, never free recall |
| The tree reading, branch by branch | One question per branch, `preview` carrying the real folder names |
| The exception pile | One question per unresolved document, its file name and folder in the description |
| Artifact approval | Approve, iterate, or stop |

Two to four options each, your recommendation first with `(Recommended)` on the label — you did the digging,
so bring an answer rather than a menu. Never add an "Other" option; it is supplied. Reach for `preview`
whenever the choice is between two concrete things worth seeing side by side.

A run never ends a message by showing something and moving on. Anything you read back is either confirmed or
corrected before it drives the next step.

## Showing

Match the thing to the surface that can draw it:

| To show | Use | Where |
|---|---|---|
| What is settled so far | The board | Terminal |
| A choice | `AskUserQuestion` | Terminal |
| A structure — entities, a folder tree, a lifecycle | A mermaid diagram | A `.md` artifact |
| The whole reading, for approval | A `.md` artifact | Published, private by default |

Artifacts are published as **markdown**, not HTML. A ```` ```mermaid ```` fence renders in a `.md` artifact; in
an `.html` file the same fence is literal text, which is how a diagram silently ships as a code block.

Artifacts need a paid plan and an authenticated session. Where publishing is refused, write the same content to
the session directory as a markdown file and walk the user through it — the approval gate still happens.

## The diagram brake

`mermaid-diagrams` is written to suggest diagrams proactively, which is right for its author and too eager
here. A run draws three: the app's entities (`erDiagram`), the folder tree (`flowchart TD`), and the upload
lifecycle (`stateDiagram-v2`). Everything else that has structure is a table, and the board is a table.

Two rules on top of that reference:

- **Label every edge out of a decision.** An unlabelled branch out of a `{diamond}` is the one thing a diagram
  of decisions cannot afford — the reader cannot tell which way is which.
- **The headline is the takeaway, not the topic.** One sentence above each diagram saying what to conclude:
  not "Folder tree" but "Every document resolves to a raw material code except the 14 under `Misc/`."
