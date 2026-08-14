# Document upload

The language of `upload-documents`: taking a customer's folder of files and producing a workbook that
attaches them onto items that already exist in their Worldmaker app.

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
is still one form.
_Avoid_: group (a *section* is the app's group), cluster, layout, template

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
land. Always the worse answer of the two.
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
