# Reading the app schema out of the customer's repo

How to get from a customer name and an app name to `APP_SCHEMA.md`. Every customer app lives in the
`WorldoverProd` GitHub organisation and is read with `gh`.

Every command here runs the same on macOS, Linux and Windows: filtering happens inside `gh --jq`
rather than in a shell pipeline, the extractor fetches its own input, and each command stays on one
line — so nothing depends on `grep`, `base64`, shell redirection or POSIX line continuations.
`<interpreter>` is whichever Python the preflight step resolved.

## Resolving the repo

Repos are named `<customer>-<app>`, both parts lower case with spaces stripped: `mondial-app`,
`expack-expackplatform`, `lbp-lbpmainapp`, `ringana-plm`, `intercos-f10`.

List them and filter on the customer name:

```sh
gh repo list WorldoverProd --limit 500 --json name --jq '.[] | select(.name | ascii_downcase | startswith("<customer>")) | .name'
```

Three outcomes:

- **One match** — name it to the user and get their confirmation.
- **Several matches** — normal, since one customer often has several apps (`bentleylabs-demo` and
  `bentleylabs-main`, `carstandwalker-app` and `carstandwalker-v1`). Put the list to the user and ask
  which app the data is going into.
- **No match** — the customer name may be spelled differently in the repo than the user said it.
  Search the whole list for something close, offer the near misses, and ask.

Repos prefixed `internal-`, `templates-`, `demos-` and `testing2026-` are not customer apps. When a
filter turns one up, say so rather than reading it as the customer's app.

## Extracting the schema

The authoritative, current shape of the app's database is its generated Supabase types file,
`src/types/database.types.ts`. It holds every table with its columns, which columns are required on
insert, and every foreign key. It is around 6,000 lines, so extract rather than read it. The
extractor takes the repo name and fetches the file itself:

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/generate-workbook/lib/extract_app_schema.py" <repo> ".workflow/active/${sessionId}"
```

That prints one line per table — column count, foreign key count, what it references — and writes
`APP_SCHEMA.json` with the full detail: every column's type and nullability, which columns are
required on insert, and each foreign key's direction and cardinality (`one_to_one`).

Read the JSON for the tables that matter rather than all of them; a typical app has around 90 tables
and most are plumbing.

## Choosing the entities

`APP_SCHEMA.json` gives you every table. The app's **entities** are the handful a user of the app
would recognise, and `CONTEXT.md` at the repo root is the domain glossary that names them. Ask the
API for the raw file so no decoding step is needed:

```sh
gh api "repos/WorldoverProd/<repo>/contents/CONTEXT.md" -H "Accept: application/vnd.github.raw"
```

In a PLM app it names Product, Component, Raw Material and Formulation as the core entities, and
explains the surrounding vocabulary — entity templates, instances, dynamic fields, document
templates. Take the entity list from there and the field and relationship detail from the JSON.

Two more places worth reading when `CONTEXT.md` leaves something open:

- `docs/implementations/<feature>/how-to-implement.md` — how one entity actually works.
- `docs/adr/` — decisions that explain why the shape is what it is.

List what a repo actually has with
`gh api "repos/WorldoverProd/<repo>/git/trees/HEAD?recursive=1" --jq '.tree[].path'`, then read
individual files with the raw `Accept` header above.

Reading `supabase/migrations/*.sql` directly is the slow path and easy to get wrong: there are
dozens per app and later ones rename and drop what earlier ones created. The generated types file
already reflects all of them.

## Custom fields

These apps store fields two ways, and the distinction decides what happens to customer data that
does not fit:

- A **static field** is a real column on the entity's table — visible in `APP_SCHEMA.json`.
- A **dynamic field** is user-created at runtime, held in `field_definitions` and `field_values`.

So a customer field with no matching column is not a dead end: the app can hold it as a dynamic
field. Record it in the mapping as needing one, and put it to the user in the grilling.

## Writing APP_SCHEMA.md

One entry per entity, in the order a user of the app would meet them. Business language for "what it
is" — the sentence you would say to the user, not the table comment. Keep the table name beside the
entity name so the mapping can name app columns exactly.
