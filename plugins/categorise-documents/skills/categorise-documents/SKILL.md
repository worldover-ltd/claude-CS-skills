---
name: categorise-documents
description: "Give every file in a list its document type, picked from a vocabulary the caller supplies or a built-in taxonomy of cosmetics, chemical and compliance document types. Triggers on \"categorise-documents\", when the user wants a pile of documents sorted by what each one is, or when another skill needs categories for files it has already collected."
allowed-tools: Workflow, Agent, Skill, AskUserQuestion, TodoWrite, Read, Write, Edit, Bash, Glob, Grep
---

### Context

One job: take files, give each one a document type. What the files are for, which item they belong to and
what happens to them next are the caller's business — a run reads a document only to answer "what kind of
document is this".

The caller is often another skill rather than a person, so the contract below is the whole interface.

### The contract

Both files live in the run's session directory, `.workflow/active/${sessionId}/`, relative to the current
working directory. A caller that already has a `${sessionId}` passes it in and both files land there; a
user invoking this directly gets one generated (a UUID, or a timestamp-based slug) and the directory
created before anything is written.

**In** — `TO_CATEGORISE.json`, written by the caller:

```json
{
  "documents": [{ "path": "C:/…/RM-0142/scan001.pdf" }],
  "vocabulary": ["Safety Data Sheet (SDS)", "Certificate of Analysis (CoA)"]
}
```

**Out** — `CATEGORIES.json`, written by this skill, one entry per input document, `path` verbatim so the
caller can join on it:

```json
{
  "results": [{ "path": "C:/…/RM-0142/scan001.pdf", "category": "Safety Data Sheet (SDS)", "source": "vocabulary" }],
  "unread": []
}
```

`source` is `vocabulary` when the category came from the list, `invented` when nothing in the list fitted
and a name had to be made up, and `unknown` when the document was read and still could not be placed.
`unread` names the documents no sub agent managed to report on.

### The vocabulary

The `vocabulary` the caller passes is the closed list of names to land on, and it wins — those are the
names whatever consumes the output can already handle. An empty or absent list falls back to
`${CLAUDE_PLUGIN_ROOT}/skills/categorise-documents/lib/document_categories.txt`: one type per line as
`<n>: <canonical name> | <alias> | <alias>`, where the canonical name is the one before the first `|` and
the aliases exist to be recognised rather than written.

A document that fits nothing in the vocabulary gets a name invented for it, marked `invented`, and named
to the caller. Inventing beats forcing a document into a category it does not belong to, and marking it
is what lets somebody else decide.

### The roll call

Every document that goes out to a sub agent answers. One that does not goes out again in a fresh batch,
and one still silent after two rounds is returned in `unread` — named as unread rather than left looking
categorised. The roll call is checked against `TO_CATEGORISE.json`, which is the authority on how many
documents there are.

This is the whole reason the fan-out is trustworthy, so it is a count you actually make:
`results.length === documents.length`, every `path` matching an input path.

### Process

# Step 1 — take the input

Read `TO_CATEGORISE.json`. Invoked by a person rather than a skill, ask which files and write it yourself
— a folder, a list, or a glob is enough — and ask which vocabulary to use, offering the built-in taxonomy
as the default.

Done when `TO_CATEGORISE.json` holds at least one document, every `path` in it exists on disk, and the
vocabulary is settled.

# Step 2 — check what can be read

The documents arrive as PDFs, Word files, spreadsheets and images, and Anthropic's official document
skills are what read them. A caller that has already run
`verify-document-skills-requirements` passes its verdict in; otherwise invoke that skill in a sub agent
and read the verdict yourself.

Group the input by extension and compare against the covered types. Documents whose type is not covered
skip the reading entirely and come back as `unknown` — tell the caller which ones and why, since guessing
from a file name is what the `unknown` marker exists to avoid.

Done when every extension in the input is either covered or recorded as uncovered.

# Step 3 — read them

Ten documents or fewer are one batch for a single sub agent, and the roll call is a glance at its output.

Beyond that, fan out per
`${CLAUDE_PLUGIN_ROOT}/skills/categorise-documents/references/WORKFLOW.md`, which holds the script, how
its values are substituted, and the reconcile loop. Where the Workflow tool is unavailable or the user
declines it, run the same batches as parallel `Agent` calls — same batch size, same schema, same roll
call; the script is a way of running the work, not the work.

Done when the roll call holds: one result per input document, each `path` verbatim.

# Step 4 — hand back

Write `CATEGORIES.json`. Then report, in one short block: how many documents were categorised, the
distinct categories with a count each, every `invented` name, and every `unknown` and `unread` document by
file name. Those three lists are what the caller or the user has to act on.

Done when `CATEGORIES.json` exists, its `results` count equals the input count, and the three lists have
been reported.
