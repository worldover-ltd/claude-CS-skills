# Reading the tree

How to get from a folder of documents to a role for every level of it, and to a verdict on whether it is
legible. Nothing here opens a document: the tree answers **which item**, and reading the documents answers
what kind of document each one is.

## Walking it

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/map_tree.py" "<folder>" ".workflow/active/${sessionId}"
```

That writes `TREE.json` — every file with its depth and its path split into parts — and prints the summary
the roles are read off: how many files, how deep, and per level how many distinct folder names there are,
a sample of them, how often each repeats, and which extensions sit under it. It also flags the two things
that most often make a tree illegible: files at mixed depths, and files sitting loose at the root.

Read the printed summary rather than `TREE.json` itself; a customer's document folder runs to thousands of
paths, and the summary is what the roles are decided from. Go into the JSON for a specific branch when a
level is ambiguous.

## Assigning the roles

The three roles are in "### The tree" in `SKILL.md`. What tells them apart is repetition, measured against
the level's own distinct-name count:

- A level whose names are nearly all distinct, and whose count is in the order of the customer's item
  count, is the **anchor**. Codes, SKUs and long names sit here. `read_export.py` printed the item count
  per table, so this is a comparison rather than a guess.
- A level with a handful of names that each cover a large, disjoint chunk of the tree is an ***item_kind*
  level**. Match its names against the tables in `WORKFLOW.json`.
- Everything else is **noise** for mapping purposes, including a level whose few names repeat across every
  branch ("SDS" under 300 item folders). Such a level names a kind of document, and it is recorded as the
  branch's `hintLevel` so the classifier sees it — a hint the document's contents can overrule. Dates,
  versions, "Final", "OLD", "scans" and "to check" are recorded as plain noise, since the user is the one
  who knows whether an "OLD" folder should be migrated at all.

Check the anchor against the app rather than against your reading of it. `check_branches.py` does exactly
that, so a candidate anchor is worth writing into `BRANCHES.json` and testing rather than deliberating
over. Anchor names that are `Doc1`, `Scan 2023`, `Client A` or `New folder (2)` identify nothing the app
can find, and the check will say so in those words.

When no folder level is the anchor, test the file names — documents sitting flat in one folder often carry
the identifier themselves (`RM-0142_SDS_2026.pdf`). A file-name anchor is legible when the identifier can
be split out of the name by the same rule for every file in that branch; a name where the identifier is
merely somewhere inside, differently each time, is not.

## The verdict

`check_branches.py` reaches it, and it is one condition: **every file reaches exactly one live item in
`ITEMS.csv`**. The check prints the rate per branch and names every file that fails, under the reason it
failed:

| reason | what the user does about it |
| --- | --- |
| `unidentified` — the rule yielded nothing | the anchor is the wrong level, or the file-name pattern misses; fix the rule |
| `unmatched` — no item has that identifier | a folder named for something the app does not hold, or a spelling difference; the check offers the app's nearest identifiers |
| `ambiguous` — several items share it | the customer's data has two items on one code; they settle it in the app |
| `archived` — the item is archived | unarchive it, or leave those documents out |
| no branch covers it | a part of the tree the mapping missed, often files loose at the root |

Case is the one difference the matching forgives, and it says when it did: `rm-0143` reaches `RM-0143`
and the check reports how many matched that way, so a systematic case difference is visible rather than
silent.

A tree can be legible in part, and the check reports it that way — branch by branch, with rates — rather
than as one verdict over the whole folder, since a customer who organised half their documents well
should not have to redo the half that was already fine.

## Writing BRANCHES.json

Your reading of the tree, in the form `check_branches.py` tests and `plan_batches.py` reads. Write it
before the gate rather than after: it is the thing under test. One entry per branch, at
`.workflow/active/${sessionId}/BRANCHES.json`:

```json
{
  "branches": [
    {
      "pathPrefix": "Raw Materials/",
      "table": "raw_materials",
      "identifier": { "type": "folderLevel", "level": 2 },
      "hintLevel": 3
    },
    {
      "pathPrefix": "Products/Flat/",
      "table": "products",
      "identifier": { "type": "fileName", "pattern": "^(PRD-\\d{4})" }
    }
  ]
}
```

- **`pathPrefix`** — matched against each file's path relative to the folder the user gave. The branch with
  the longest matching prefix wins, so a general branch and a more specific one can coexist. One branch
  covering the whole tree uses `""`.
- **`table`** — the *item_kind*'s table, as `WORKFLOW.json` spells it. A table that is not there stops the
  script rather than producing a sheet the migration cannot place. The branch names the table and never an
  *item_template*: which *item_template* an item is on is the items file's answer, not the folder's.
- **`identifier`** — how to get the item's identifier out of a path, in one of two forms:
  - `{"type": "folderLevel", "level": N}` — the Nth folder level, counting from 1 at the top of the
    relative path. `Raw Materials/RM-0142/SDS.pdf` at level 2 yields `RM-0142`.
  - `{"type": "fileName", "pattern": "<regex>"}` — matched against the file name; the first capture group
    is the identifier, or the whole match where the pattern has no group. Escape backslashes for JSON
    (`\\d`), and prefer anchoring the pattern at the start.
- **`hintLevel`** — optional. The folder level whose names look like kinds of document, passed to the
  classifier as `folderHint`. Leave it out where no level does.

Write the rule rather than the values: both scripts apply it to every path and report the documents it
yields nothing for, which catches the branch whose anchor is one level off across a whole folder.
