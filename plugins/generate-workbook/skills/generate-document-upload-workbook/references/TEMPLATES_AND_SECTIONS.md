# Document templates, and the sections that group them

Two things the workbook has to name, in this order, because the second is built out of the first.

- A **document template** is what a single document *is*: "Safety Data Sheet (SDS)", "Certificate of
  Analysis (CoA)". Every row of the workbook names one.
- A **document section** is a group of templates that belong together on an item's page: "Safety",
  "Quality", "Commercial". The app holds these in `field_sections`, attached to templates through
  `section_attachments` with `kind` set to `document`, and scoped to one entity by `owner_type` — so raw
  materials have their own sections, separate from products'.

Templates come first and sections are derived from them. A section with no templates under it is nothing.

## Part 1 — the template for every document

The tree usually names it; only the documents it leaves silent are opened.

### The vocabulary

Template names come from the app's own document template list in `APP_SCHEMA.md` — those are the names the
migration can land on. Where the app has none yet, the `categorise-documents` skill falls back to its own
taxonomy of cosmetics, chemical and compliance document types, which is why an empty vocabulary is passed
rather than an invented one.

### From the tree

For a branch whose **template level** was confirmed against the tree, the template is that folder's name —
no document opened. Land each name in the app's list:

- **Exact or obvious match** — `SDS` against "Safety Data Sheet (SDS)", `CoA` against "Certificate of
  Analysis (CoA)". Record the app's name, not the folder's.
- **No match** — keep the folder's name and record it in the mapping as a template the app will need. Say so
  in the workbook's `README` sheet too, since somebody has to create it before the migration runs.

A folder name that names several templates at once ("SDS + TDS") is one folder holding two kinds of
document. Put it to the user rather than picking one.

### From the documents, for the branches the tree leaves silent

Documents in a branch with no template level are the only ones opened, and the `categorise-documents` skill
does that reading. Its contract still speaks of *categories* — it is a general-purpose skill with its own
callers — so translate at the boundary: what it returns as a `category` is a template name here.

1. **Check it is there.** Absent, tell the user it is a separate plugin
   (`/plugin install categorise-documents`) and offer the alternative: they name the kind of document per
   folder themselves, recorded as user-supplied.
2. **Write its input** to `.workflow/active/${sessionId}/TO_CATEGORISE.json` — the silent-branch documents
   from `DOCUMENTS.json` and nothing else, plus the app's template list as the `vocabulary`, or `[]` when
   the app has none.
3. **Invoke it**, passing this run's `${sessionId}` so it writes back into the same session directory, and
   the document tooling verdict from the preflight so it does not probe again.
4. **Read `CATEGORIES.json` back** and join to the tree on `path`, each `category` becoming that document's
   template.

What comes back marked `invented`, `unknown` or `unread` goes to the user as the exception pile — with the
file name and its folder, which is usually enough for them to say what it is. A template marked `invented`
is one the app will need, so it belongs in the workbook's `README` sheet alongside the unmatched folder
names.

## Part 2 — the sections, once the templates are settled

Only now, with the full list of templates the workbook uses, is there anything to group. Do it per entity,
since that is how the app scopes a section.

**Where the tree already says it.** A level above the template level whose few names repeat across branches
is the customer's own grouping — `Raw Materials/RM-0142/Safety/SDS_2026.pdf` has already sorted its
templates into `Safety`. Take it, and match the name against the app's existing sections where it has any.

**Otherwise, group them.** For each entity, take its distinct templates and sort them into groups of
templates that would sit together on that item's page. Aim for **two to six sections per entity** — one
section holding everything is not a grouping, and a section per template is not one either. A template that
fits nothing goes into a section named for what it is rather than being forced into a neighbour.

Then put the grouping to the user, since it is a judgement rather than a reading, and they are the ones who
know how the customer thinks about their documents. Show it as the board — one row per section, its
templates listed, and the document count behind each — and let them move a template, rename a section, or
merge two.

The section's `key` is the label lower-cased with spaces as underscores (`Safety and Regulatory` →
`safety_and_regulatory`); its `sort_order` is the order the user approved them in, counting from 0.

Done when every template used by the workbook belongs to exactly one section of its entity, and the user has
approved the grouping.
