# The gold set

One file per document. A label is what a person read **off the page** — an ingredient and the figure
printed beside it — never the Markdown a converter happened to write. Two converters render one fact
differently and both are right, so a label that pinned the rendering would fail on changes that are
correct.

```json
{
  "document": "MiyoAQUA White A2_TDS_v2.pdf",
  "confirmed": true,
  "confirmedBy": "read off the page, 2026-09-16",
  "rows": [{ "ingredient": "Titanium Dioxide", "value": "98.6" }]
}
```

`confirmed: false` until somebody has opened the document and checked every row. Drafts are kept and
never counted — `gold.py --propose` writes them from tables already extracted, which is circular by
construction, so they are a starting point for a person and nothing else.

**The labels live here; the documents do not.** They are customers' files. A run scores whatever labels
have a record in the extraction it is given, and says how many it had to skip.

Choose documents for difficulty rather than at random: a bordered table, a borderless one, two columns,
merged cells, long INCI names, a scan, a spreadsheet. Twenty is enough to see a regression.

```sh
uv run .../lib/gold.py gold --extracted <out>/EXTRACTED.json --propose
uv run .../lib/gold.py gold --extracted <out>/EXTRACTED.json --label "before tables" --history gold/HISTORY.jsonl
```

Two numbers come out. **Recall** is rows recovered with the figure still beside the ingredient — within 200 characters of it
in the document's own text, not in the flattened form used for comparison, because a Markdown table is
mostly punctuation and flattening it would call anything adjacent.
**Misalignment** is both halves present but far apart — the quiet failure, where a reader will happily
quote a percentage that belongs to a different ingredient.
