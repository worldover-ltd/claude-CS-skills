---
name: assign-documents
description: "Skill to categorize documents and assigning them to items present on a source of excel files. Triggers on \"assign-documents\" or when user asks to categorize some documents, match documents to excel file(s) or match documents to some type of items."
allowed-tools: Skill, Agent, AskUserQuestion, TodoWrite, Read, Write, Edit, Bash, Glob, Grep
---

### Context

The user will provide files related to products, raw materials or other items related to the area of cosmetics, chemicals and other substance-based industries.

### Goal

THe goal is to take the document files and do the following:
- categorize them.
- assign them to a specific item in an excel file.
- produce a final excel file listing all of this information.

### Session setup

All intermediate and output files for a run live under a per-run session directory:
`.workflow/active/${sessionId}/` (relative to the user's current working directory).

At the start of a run, if `${sessionId}` is not already set for this conversation, generate one
(a UUID, e.g. via `uuidgen`, or a timestamp-based slug) and create the directory before writing
any files. Reuse the same `${sessionId}` for every file in the same run.

Files inside this skill are referenced relative to the skill's install location using
`${CLAUDE_PLUGIN_ROOT}` (set by Claude Code when the plugin is installed). When running the skill
from a raw checkout instead of an installed plugin, treat `${CLAUDE_PLUGIN_ROOT}` as the plugin
root directory (the folder containing this `skills/` directory).

### Instructions

# Step 1

Do the following in sequence:
1. prompt the user for the the document files -> the user should provide specific documents or a folder containing documents.
  - never read the document files on your own decision
  - maintain the list of documents according to the "### Keeping track of documents" section
2. write to the user a sample of the file names in a list format (no more than 10) + a total count of the files, ask for the user to confirm it.
3. prompt the user for excel files to match the documents with -> the user should provide specific excel files.
4. write to the user a sample of the file names in a list format (no more than 10) + a total count of the files, ask for the user to confirm it.

# Step 2

Analyze the excel files:
- learn the contents of each file, note down the types of items found.
- files might share the same structure, for each file type create a group and assign the corresponding files to them.

# Step 3

For each excel file group from "# Step 2", one at a time, do the following in sequence:
1. prompt the user with a multi-selection question for which items on the file the documents should be assigned to, offer suggestions from items found on "# Step 2".
2. for each item figure out where the item can be found in the excel file, look for columns related to the area mentioned in the "## Context" section (examples: "Name", "Trade Name", "Product", "Raw Material", "Code", "SKU", "Primary Identifier", etc...).
3. write down in a table format what tab and columns for each item you've chosen to use to identify them, ask the user to revise and confirm or ask for changes
4. store this information by following the instructions on "${CLAUDE_PLUGIN_ROOT}/skills/assign-documents/specs/EXCEL_FILE_ITEMS.md"
5. continue re-doing these steps until the user has confirmed, when confirmed move to next step

# Step 4

Execute the plan described on "${CLAUDE_PLUGIN_ROOT}/skills/assign-documents/workflows/assign_documents.md"

# Step 5

Inform the user its completed and locate to him where the output excel file is at.

### Keeping track of documents

Write all the documents to be assigned on a json file with the following format:

```json
{
  "document_files": [
    {
      "SHA": "<DOCUMENT_FILE_SHA_VALUE>",
      "path": "<DOCUMENT_FILE_PATH>"
    }
  ]
}
```

where:
  - DOCUMENT_FILE_SHA_VALUE: SHA-256 value of the document file
  - DOCUMENT_FILE_PATH: path to the document file

Store the file on: .workflow/active/${sessionId}/DOCUMENT_FILES.json
