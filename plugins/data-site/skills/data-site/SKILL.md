---
name: data-site
description: "Display data as a browsable site — icon rail, nav panel, list tables, item detail pages — built from a JSON config and delivered as one self-contained HTML file. Triggers on \"data-site\", when the user wants a dataset shown as a site, app, portal or dashboard rather than a table in chat, or when rows need clickable detail pages."
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, SendUserFile, Artifact, AskUserQuestion, TodoWrite
---

### The shell and the config

This skill ships a finished React app — the **shell** — that renders whatever a JSON **config**
describes: the icon rail, the nav panel inside each rail entry, a table per nav item, and a detail
page per row. The shell is done. The work of every run is the **config**: reading the user's data and
expressing it in that JSON. Reach for shell edits only when the data needs a display the shell has no
kind for.

### Step 1 — copy the shell into the workspace

The shell lives at `${CLAUDE_PLUGIN_ROOT}/skills/data-site/template` and stays pristine there. Every
run works on its own copy, so a config written for one dataset never leaks into the next.

```sh
cp -r "${CLAUDE_PLUGIN_ROOT}/skills/data-site/template" ./data-site
cd data-site && npm install
```

PowerShell: `Copy-Item -Recurse "$env:CLAUDE_PLUGIN_ROOT/skills/data-site/template" ./data-site`.

Use **npm**, not pnpm — pnpm holds back the native build scripts Parcel needs and aborts the build
asking for approval.

Done when `data-site/node_modules` exists in the workspace.

### Step 2 — write the config

`src/data/example.json` is the config the shell loads at boot. Overwrite it with the user's data.
Read `template/README.md` (now `data-site/README.md`) for the full field-by-field format before
writing — it is the authority on the schema, including the widget kinds and the icon names.

Mapping data onto it:

- One rail **section** per big concept in the data — the entity types, the top-level buckets.
- One nav **item** per list a user would open inside that concept, each with its own table.
- One **page** per row worth drilling into, linked from the row by `$page`.

Two rules the format enforces: every value is a string, so format numbers, dates and units yourself;
and a `$page` with no matching entry in `pages` fails validation.

Done when every record and field of the source data appears in the config, and
`node -e "JSON.parse(require('fs').readFileSync('src/data/example.json','utf8'))"` is silent.

### Step 3 — build and check

```sh
npm run bundle
```

That writes `bundle.html`, self-contained. Open it and confirm the section, the item and the row
counts match the source data. A red list of `path: message` lines instead of the site means Zod
rejected the config — each line names the JSON path to fix.

Done when the site renders the data, including one detail page opened from a row.

### Step 4 — deliver

Send `bundle.html` to the user. Say which parts of their data became sections, tables and pages, so
they can tell you what to move.

### Extending the shell

Reach here only when the data needs something the config cannot express.

- A new list view kind: add a member to `viewSchema` in `src/lib/schema.ts`, render it in
  `src/components/AppShell.tsx`.
- A new detail-page widget kind: add a member to `widgetSchema`, render it in
  `src/components/WidgetCard.tsx`.
- More icons: add to the registry in `src/lib/icons.ts` — an unknown name silently falls back to a
  box, so a missing icon is a registry entry, not a config error.

`README.md` in the copy records the two build constraints that break the artifact silently when
broken: how `zod` must be imported, and why the bundle is inlined by `scripts/inline.cjs` rather than
`html-inline`. Read it before touching the build.
