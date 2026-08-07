# Reading the tree

How to get from a folder of documents to a role for every level of it, and to a verdict on whether it is
legible. Nothing here opens a document: every fact comes from folder names, file names and nesting.

## Walking it

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/generate-document-upload-workbook/lib/map_tree.py" "<folder>" ".workflow/active/${sessionId}"
```

That writes `TREE.json` — every file with its depth and its path split into parts — and prints the summary
the roles are read off: how many files, how deep, and per level how many distinct folder names there are,
a sample of them, how often each repeats, and which extensions sit under it. It also flags the two things
that most often make a tree illegible: files at mixed depths, and files sitting loose at the root.

Read the printed summary rather than `TREE.json` itself; a customer's document folder runs to thousands of
paths, and the summary is what the roles are decided from. Go into the JSON for a specific branch when a
level is ambiguous.

## Assigning the roles

The four roles are in "### The tree" in `SKILL.md`. What tells them apart is repetition, measured against
the level's own distinct-name count:

- A level whose names are nearly all distinct, and whose count is in the order of the customer's item
  count, is the **anchor**. Codes, SKUs and long names sit here.
- A level whose few names repeat across every branch is a **template level**. "SDS" appearing under 300
  item folders is a kind of document, not an item. Where two such levels sit one inside the other, the
  inner one is the template level and the outer one is the customer's own grouping of them — a section.
- A level with a handful of names that each cover a large, disjoint chunk of the tree is an **entity
  level**. Match its names against the entities recorded in `APP_SCHEMA.md`.
- Anything left — dates, versions, "Final", "OLD", "scans", "to check" — is **noise**, and is recorded as
  noise rather than quietly ignored, because the user is the one who knows whether an "OLD" folder should
  be migrated at all.

Check the anchor against the app rather than against your reading of it: its names have to look like values
of a column the app can look an item up by. Anchor names that are `Doc1`, `Scan 2023`, `Client A` or
`New folder (2)` identify nothing the app can find.

When no folder level is the anchor, test the file names — documents sitting flat in one folder often carry
the identifier themselves (`RM-0142_SDS_2026.pdf`). A file-name anchor is legible when the identifier can
be split out of the name by the same rule for every file in that branch; a name where the identifier is
merely somewhere inside, differently each time, is not.

## The verdict

The tree is **legible** when all four hold:

- every file in `TREE.json` sits under exactly one anchor value;
- every anchor value looks like a value of the identifier column the app can look items up by;
- each anchor value names one item, not several — two items sharing a folder is an unresolved attachment,
  not a two-row one;
- every branch reaches an entity in `APP_SCHEMA.md`.

Anything else is **illegible**, and the failures worth naming separately are: files loose at the root with
no folder above them, an anchor level whose names carry no identifier, one folder holding documents for
several items, and a branch whose kind of item has no matching entity in the app.

A tree can be legible in part. Report it that way — branch by branch, with counts — rather than as one
verdict over the whole folder, since a customer who organised half their documents well should not have to
redo the half that was already fine.

## Reporting an illegible branch

Give the user the folder path, the count of documents stranded under it, and which of the four conditions
it failed, in the plainest form of it: "these 34 documents are in a folder called `Scan 2023`, and nothing
in the folder names says which raw material they belong to". Then what a legible version looks like for
their case — one folder per item, named with the code the app knows the item by — and the two moves they
own: reorganise those folders and come back, or tell you which item each folder belongs to, recorded as
user-supplied.
