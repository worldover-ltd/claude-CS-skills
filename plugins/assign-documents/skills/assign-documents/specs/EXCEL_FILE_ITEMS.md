## TASK OBJECTIVE

Generate an EXCEL_FILES_ITEMS.md file containing the relevant data necessary to identify each items on each excel files.

## SESSION PATHS
Input:
- NONE
Outputs:
  - EXCEL_FILES_ITEMS: .workflow/active/${sessionId}/EXCEL_FILES_ITEMS.md


## INSTRUCTIONS

For each excel file provided, write down the following:

```md
# "<EXCEL_FILE_PATH>"
<INDEX_VALUE>.
ITEM_NAME: "<ITEM_NAME_VALUE>"
TAB_KEY: "<TAB_KEY_VALUE>"
COLUMN_KEYS: "<COLUMN_KEYS_VALUE>"
```

where:
- INDEX_VALUE -> index number of the item, from 1 to n
- EXCEL_FILE_PATH -> path to the excel file
- ITEM_NAME_VALUE -> name of the item
- TAB_KEY_VALUE -> key value of the excel tab
- COLUMN_KEYS_VALUE -> key value of relevant columns

Example:

```md
# "/home/documents/org_export_data.xlsx"
1.
ITEM_NAME "Product"
TAB_KEY: "products"
COLUMN_KEYS: "name","primary_identifier"
2.
ITEM_NAME: Raw Materials
TAB_KEY: raw_materials
COLUMN_KEYS: "trade_name","sku_code"

# "/home/documents/products_sheet.xlsx"
1.
ITEM_NAME: Product
TAB_KEY: products
COLUMN_KEYS: "name", "primary_identifier"
```

Store the file on: .workflow/active/${sessionId}/EXCEL_FILES_ITEMS.md
