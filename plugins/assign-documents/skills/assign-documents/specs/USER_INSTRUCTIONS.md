# Worldmaker Upload Documents

# Goal

This page describes how to take many documents, assign them to items (Products, Raw Materials, etc) from a customer’s data migration sheet(s) and  how to upload then to a customer’s app on Worldmaker.

# Part 1: Upload the documents

This section explains how to upload the documents to the customer’s app.

#### Step 1

In Worldmaker, go to the customer’s app and click on the “Upload Documents" button.

#### Step 2

Drag in all of the documents to be uploaded to the customer’s app and click to upload them.

Wait for the upload to finish. D**on’t close the tab / browser!**

#### Step 3

After the upload is finished a `.json` file should be auto-downloaded. If the download did not occur press the Download button to manually download it.

Make sure to download and store this file near the uploaded documents on your computer, as this file is necessary to complete the next steps.

# Part 2: Generate the document mapping

This section explains how to use the skill with claude to generate an excel file that matches the documents to specific items on the customer’s data sheets.

### Step 1:  Prepare the required files

Three file types are necessary for the skill:

1. Document Files → these are the documents to be uploaded
2. Excel Migration File(s) → this is the excel file(s) containing the org’s migration data
    1. the rows of these excel files is what the AI will attach the documents to
    2. this is the same files that are going to be used to upload the org’s data later on
3. The document upload json file from **“Part 1: Upload the documents”**

Gather these files and prepare them for the AI agent.

#### Organize the files (optional)

This is a suggestion for organizing the required files for the AI agent.

Visual folder structure:

```
Expack Documents/  ---------> new folder for the organisation
├── documents/  ------------> holds the documents
│   └── Document_1.doc
│   └── Document_2.doc
│   └── ...
└── sheets/  ----------------> holds the data sheets
│   └── expack_data_sheet.xlsx
│   └── ...
└── uploaded-documents.json -> the file from Part 1
```

1. Make a new folder for the organisation
2. Inside of it create the “documents” and the “sheets” folders.
3. Place all the documents on the “documents folder.
4. Place all the data sheets on the “sheets” folder.
1. Place the json file from Part 1 on the main folder.

### Step 2:  Use Claude to generate the document assignments sheet

1. Switch Claude to **Code**
    1. **IMPORTANT:** Do not use “Cowork”, it lacks the necessary tools to use this skill effectively - make sure to always use **Code.**
2. Start a new conversation.
3. Prompt the AI agent to assign the documents for you, the skill can be activated in two ways:
    1. manually activating the skill by typing `/assign-documents` in the input.
    2. asking the AI agent to “assign some documents”  or “prepare some documents for upload” for you.
4. Make sure that the AI agent loaded the `assign-documents` skill.
5. The AI agent will guide you through the process.
    1. He will ask you for the location of the documents, the data excel files and the uploaded-documents.json file, you can drag the folder over to reference it.
    2. The agent will analyze the data sheets then suggest a selection of items on the sheet(s) to match with the documents.
        1. Select the intended ones or specify some others.
    3. For each selected item, the agent will suggest which columns are to be used to identify it.
        1. “Primary columns” → these are columns that are unique to each item, it uses the item’s name as a fallback when not present
        2. “Secondary columns” → these are extra columns to assist identifying the item when data on a document is scarce
    4. Once all the previous steps are completed, the agent will start the process and output an excel file matching all the documents to items on the data sheets.
6. Once completed, the agent will have added a new version of each data sheet with the uploaded documents inside.

# Part 3: Create a new migration

In Worldmaker on the customer’s app, go the customer’s migration page and start a new migration as per usual, use the new data migration excel files that the AI agent generated.
