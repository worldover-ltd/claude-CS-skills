---
name: assign-documents
description: "Skill to categorize documents and assigning them to items present on a source of excel files. Triggers on \"assign-documents\" or when user asks to categorize/match/assign documents to some type of items or sheet file(s), or if the user wants to prepare some documents for uploading/migrating."
allowed-tools: Skill, Agent, AskUserQuestion, TodoWrite, Read, Write, Edit, Bash, Glob, Grep, WebFetch
---

### Context

The user will provide document files related to products, raw materials or other items related to the area of cosmetics, chemicals and other substance-based industries.
The user will provide excel files, these contain migration data for a specific customer.
The user will provide a document upload manifest json, this file lists the document files already uploaded to the customer's app.
Before running this skill the user has already uploaded the documents to the customer's app, and provides an upload manifest json describing that upload (see "### The upload manifest").
This process is part of an initial setup to assign these documents to specific items on the customer's excel files, later on the user will migrate this data and the documents to the customer's app.

### Goal

THe goal is to take the document files and do the following:
- categorize them into document categories.
- assign them to specific item(s) in the excel files.
- write the assignments into annotated copies of the customer's excel files.

# General Instructions

- Follow the instructions in "${CLAUDE_PLUGIN_ROOT}/skills/assign-documents/specs/MAIN_AGENT_PROMPT.md"
- Refer to the documents as the "customer's documents".
- Refer to the excel files as the "customer's data sheet" files.
- Refer to the document upload manifest json as the "document upload manifest" file.

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

### Process

Follow these steps in a sequence to go through the process.
The user might ask to revisit a previous step, restart from the beginning on a new set of files or ask you to modify the output file.

# Step 1

Do the following in sequence:
1. prompt the user for the document files -> the user should provide specific documents or a folder containing documents.
  - never read the document files on your own decision
  - maintain the list of documents according to the "### Keeping track of documents" section
2. write to the user a sample of the file names in a list format (no more than 10) + a total count of the files, suggest the user to verify and proceed to next step
3. prompt the user for the upload manifest json file.
4. prompt the user for excel files to match the documents with -> the user should provide specific excel files.
5. write to the user a sample of the file names in a list format (no more than 10) + a total count of the files, suggest the user to verify and proceed to next step

# Step 2

Analyze the excel files:
- learn the contents of each file, note down the types of items found.
- files might share the same structure, for each file type create a group and assign the corresponding files to them.

# Step 3

1. for each item figure out where the item can be found in the excel file, look for columns related to the area mentioned in the "## Context" section (examples: "Name", "Trade Name", "Product", "Raw Material", "Code", "SKU", "Primary Identifier", etc...).
  2.1. the "primary columns" should be unique values such (ex: "Primary Identifier" or "Code"), the name of the item can be used as primary if no unique value exists.
  2.2. the "secondary columns" should be non-unique values such as its name, these are to be used as extra information to help identify the item when data is limited.
  2.3. always store this information and keep it up to date by following the instructions on "${CLAUDE_PLUGIN_ROOT}/skills/assign-documents/specs/EXCEL_FILE_ITEMS.md"
2. For each excel file group from "# Step 2" write down in a table format what tab and columns for each item you've chosen to use to identify them, ask the user to revise and confirm or ask for changes
3. For each excel file group from "# Step 2" in sequence: prompt the user with a multi-selection question for which items on the file the documents should be assigned to, offer suggestions from items found on "# Step 2".
5. continue re-doing these steps until the user has confirmed, when confirmed move to next step

# Step 4

Execute the plan described on "${CLAUDE_PLUGIN_ROOT}/skills/assign-documents/workflows/assign_documents.md"

# Step 5

The workflow (Step 4) writes an annotated copy of each customer excel file, named
`<original>_with_documents.xlsx`, next to the original.
Inform the user the task is completed and list where each annotated file is located.

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

### The upload manifest

Before this skill runs, the user uploads the documents to the customer's app and exports a manifest
describing that upload. The user provides this file; store it verbatim at
`.workflow/active/${sessionId}/UPLOAD_MANIFEST.json`. Its shape is:

```json
{
  "documents": [
    {
      "fileName": "<DOCUMENT_FILE_NAME>",
      "storageKey": "<APP_STORAGE_KEY>",
      "sha": "<DOCUMENT_FILE_SHA_VALUE>"
    }
  ]
}
```

where:
  - fileName: the document's file name
  - storageKey: the key/id of the uploaded file in the customer's app (Supabase)
  - sha: SHA-256 of the document file

Manifest entries are joined to the local documents (and to assignment results) by `sha`, so the same
SHA-256 you record in `DOCUMENT_FILES.json` links each document to its `storageKey`.

### Helping the User

The user might require your help on the actions that the user needs to do himself, some examples:
- actions on the Worldmaker app: uploading the documents to the customer's app, downloading the uploaded documents manifest, etc...
- actions on his computer: organizing all of the files in a folder, where to get your generated files, etc...
- actions related to claude: linking files/folders to you

Offer help to the user proactively or when the user asks for it.

Use the link below when assisting the user, its a Notion page that contains a tutorial:
https://worldover.notion.site/Worldmaker-Upload-Documents-39619f2640b280bab6f6d981f3172118

If you cannot access the page let the user know and ask for it to be fixed by one of the colleagues on the Engineering team.
