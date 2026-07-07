## TASK OBJECTIVE

Generate a json file containing all of the relevant data of each excel file as described on "### Phase 1"

## SESSION PATHS
Input:
  - EXCEL_FILES_ITEMS: .workflow/active/${sessionId}/EXCEL_FILES_ITEMS.md
  - DOCUMENT_FILES: .workflow/active/${sessionId}/DOCUMENT_FILES.json
Outputs:
  - ASSIGNED_DOCUMENTS: .workflow/active/${sessionId}/ASSIGNED_DOCUMENTS.xlsx


## INSTRUCTIONS

# Step 1

This workflow spawns many sub-agents and is token-intensive. If the `ultracode` effort mode is
available in this environment, prefer switching to it (```/effort ultracode```); if it is already
active, let the user know. If `ultracode` is not available, proceed anyway — it is a performance
preference, not a hard requirement.

# Step 2

Read the EXCEL_FILES_ITEMS.md for context.

# Step 3

Take all excel files mentioned in EXCEL_FILES_ITEMS.md and generate a json file with the following structure:

```json
{
  "excel_files": [
    {
      "SHA": "<EXCEL_FILE_SHA_VALUE>",
      "path": "<EXCEL_FILE_PATH>",
      "rows": [
        {
          "ref": "<EXCEL_REF>",
          "data": {
            "<COLUMN_KEY": "<COLUMN_VALUE>"
          }
        }
      ]
    }
  ]
}
```

where:
  - EXCEL_FILE_SHA_VALUE: SHA-256 value of the excel file
  - EXCEL_FILE_PATH: path to the excel file
  - EXCEL_REF: reference to the row in the excel file, formatted as such: `${TAB_KEY}::${ROW_NUMBER}`
  - COLUMN_KEY: key of each excel column, one key on the object per column
  - COLUMN_KEY: value of the excel column

Store the file on: .workflow/active/${sessionId}/EXCEL_FILES_DATA.json

# Step 4

Use a workflow to complete the following task:

- For all the documents on DOCUMENT_FILES.json, use sub agents to do the assigning process.
- Spawn 10 agents at a time, each one is given 10 documents.
- Pass to the sub agents the following prompt template:

```javascript
const prompt = `
  ### DOCUMENT FILE PATHS

  ${EXCEL_FILES_FOR_AGENT.map((excelFile, index) => {
    return `${index}. ${excelFile.path}`
  }).join("\n")}
  
  ### INSTRUCTIONS
  
  For each document file do the following:
  - Check the document file and access its content
  - Check the data on .workflow/active/${sessionId}/EXCEL_FILES_DATA.json".
  - Check if the document is referencing any item in the "rows" array present on "EXCEL_FILES_DATA.json", if no item is found do not return it.
  - Categorize the document by selecting the most relevant category on "${CLAUDE_PLUGIN_ROOT}/skills/assign-documents/lib/document_categories.txt", if no relevant category is found create one with at most 20 characters.

  Output your response in this EXACT json format:

  {
    results: [
        "<DOCUMENT_FILE_PATH>": {
          "row_ref": "<ROW_REF_VALUE>",
          "category": "<DOCUMENT_CATEGORY"
        }
    ]
  }

  where:
  - ROW_REF_VALUE: the "row.ref" value of the row, when no item is found use the "NONE" string literal -> string | "NONE"
  - DOCUMENT_CATEGORY_NUMBER: the number of the category as a stirng, return "NONE" if no relevant one was found -> string | "NONE"
  - DOCUMENT_NEW_CATEGORY: if a new category is needed add it here, otherwise return "NONE" -> string | "NONE"
`;

```

# Step 5

Generate an excel file where each row is one of the documents with these columns:

- "Document File" -> file name of the document
- "Category Name" -> category of the document
- "Is New Category" -> if a new category was created, only "YES" or "NO" as values here
- "Matched Item" -> primary column value of the matched item (prefer the item's name if available)
- "Matched Excel File" -> file name of the excel file
- "excel_row_ref" -> ref value of the row item
- "excel_path" -> file path of the row item's excel file
- "excel_sha" -> SHA value of the excel file
- "doc_path" -> file path of the document file
- "doc_sha" -> SHA value of the document file

Place the file on ".workflow/active/${sessionId}/ASSIGNED_DOCUMENTS.xlsx"
