# Data site

A shell that renders an app — icon rail, nav panel, list tables, item detail pages — entirely from a
JSON config, bundled into one self-contained HTML file. The config is validated with Zod
(`src/lib/schema.ts`) before anything renders; failures are listed with their JSON path.

`src/data/example.json` is the config the app loads at boot. Replace it with yours.

## Build

```bash
npm install
npm run bundle
```

Produces `bundle.html` (self-contained, ~380K). `npm run dev` serves the app with hot reload while
you iterate on the config.

Use npm, not pnpm: pnpm withholds the native build scripts Parcel depends on and aborts the build
asking for approval.

Two build constraints that break the page silently when broken:

- `npm run bundle` is Parcel plus `scripts/inline.cjs`, which escapes `<script` / `</script` inside
  the JS before inlining it. `html-inline` does not, so React's literal `"<script><\/script>"`
  string ends the inline tag early and the page renders blank with no console error.
- `zod` must be imported as `import * as z from 'zod'`. With `import { z } from 'zod'`, Parcel's
  namespace re-export handling yields an empty namespace and the app dies on
  `z.string is not a function`.

## Config format

```jsonc
{
  "title": "Curtis Health Caps",          // optional, sets document.title
  "sections": [                            // icon rail (leftmost) — one entry per "big concept"
    {
      "id": "library",
      "label": "Library",                  // rail tooltip + label under the active icon
      "icon": "folder",                    // see icon names below
      "panel": {                           // second sidebar for this section
        "title": "Curtis Health Caps",
        "icon": "leaf",
        "groups": [                        // groups of items; label optional (renders as a caption)
          {
            "label": "Library",
            "items": [
              {
                "id": "products",
                "label": "Products",
                "icon": "package",
                "view": {
                  "type": "table",
                  "title": "Products",     // optional, defaults to the item's label
                  "icon": "package",       // optional, defaults to the item's icon
                  "columns": [
                    { "key": "product", "label": "Product", "width": "45%", "align": "left" }
                  ],
                  "rows": [
                    { "product": "Vitamin D3 4000 IU" }
                  ]
                }
              }
            ]
          }
        ]
      }
    }
  ]
}
```

- `columns[].key` selects the row property; missing values render as an em dash.
- `columns[].width` is any CSS width; `align` is `left` | `center` | `right`.
- Row values must be strings.
- `view.type` is a discriminated union — currently `"table"` only, so more view kinds
  can be added to `viewSchema` without touching the callers.

## Item pages

A row becomes clickable by pointing `$page` at a key in the top-level `pages` map. The reserved
`$page` key is never rendered as a column, and Zod rejects a `$page` that has no matching page.

```jsonc
{
  "sections": [ /* ... a row: */ ],
  "pages": {
    "material-silicon-dioxide": {
      "title": "Silicon dioxide (E551)",   // page header, next to the icon
      "icon": "box",
      "widgets": [
        {
          "type": "table",                  // widget 1: a table
          "title": "Composition",
          "span": "full",                   // optional: "half" (default) or "full" width
          "columns": [{ "key": "ingredient", "label": "Ingredient" }],
          "rows": [{ "ingredient": "Silicon dioxide" }]
        },
        {
          "type": "sections",               // widget 2: the workflow style
          "title": "Data",
          "sections": [
            {
              "type": "fields",             // label + read-only string value, two per row
              "label": "Stability, Shelf Life & Storage",
              "fields": [
                { "label": "Shelf Life", "value": "36 months" },
                { "label": "Storage" }      // value omitted -> em dash
              ]
            },
            {
              "type": "items",              // icon + label list
              "label": "Safety Data & Hazard",
              "items": [{ "label": "Safety Data Sheet (SDS)", "icon": "file" }]
            }
          ]
        }
      ]
    }
  }
}
```

Widgets lay out in a two-column grid (one column under 1024px). Field values are display-only.
The example config has pages for three products and three raw materials.

### Icons

`beaker`, `bell`, `book`, `box`, `boxes`, `building`, `clipboard`, `database`, `droplets`,
`factory`, `file`, `flask`, `folder`, `globe`, `layers`, `leaf`, `package`, `pill`, `search`,
`settings`, `shield`, `table`, `tag`, `truck`, `users`, `wrench`.

Unknown or missing names fall back to `box`. Add more in `src/lib/icons.ts` — the registry is
explicit so the bundle only carries the icons it uses.

## Loading a config at runtime

The pill in the bottom-right corner opens a loader: drop a `.json` file, browse for one, or
paste JSON. `src/data/example.json` is the config that ships with the bundle.
