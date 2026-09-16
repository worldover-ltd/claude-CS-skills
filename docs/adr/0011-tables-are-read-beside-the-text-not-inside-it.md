# Tables are read beside the text, not inside it

A PDF is opened twice. MarkItDown converts it to Markdown as before, and `pdfplumber` is asked separately
for its tables, which are written to `<slug>.tables.md` and pointed at by `tablesFile`. Neither result
replaces the other.

Two finders, two answers. Measured over 150 pages carrying composition signals, sampled at random from
63,686 customer PDFs:

```
only pdfplumber produced a table    54
both produced a table               38
only markitdown produced a table    23
neither produced a table            35
```

MarkItDown clusters words; `pdfplumber` follows ruling lines and alignment. Neither is a superset, and the
54 pages only `pdfplumber` sees are the ones that matter here — a composition is a column of INCI names
against a column of percentages, and where it is not recovered as a table, a *composition reading* is
taken off a page whose columns have been flattened into prose.

Beside rather than inside, because `chars`, `letters` and `kind` are counted on the conversion.
`docs/adr/0006`'s companion rule in this script is that what a document *is* gets decided on what the file
holds; append a wide table to the text and a scan stops looking like a scan, silently, on the
`letters`-per-page floor.

## Consequences

- **Every PDF is opened a second time.** Conversion was half a second a file; this adds to it, and
  `--no-tables` exists for a run where nothing downstream reads a table. Only the first 40 pages are read,
  and a document with more says so in its `note` rather than dropping them quietly.
- **`pdfplumber` is serialised**, on a lock of its own. `pdfminer.six` beneath it interns literals into
  process-wide tables and caches CMaps on the class, neither guarded, and `pdfplumber` declines to claim
  thread safety. So the conversion pool gains a second choke point, alongside the one pdfium already
  imposes on rendering.
- **Three passes read them, through one seam.** `signals.read_text` joins the tables onto the conversion,
  so the shortlist that scores a candidate, the task a sub agent is given and the haystack `verbatim.py`
  checks quotes against all see the same text. Joining anywhere else would fail a correct row: a value
  quoted off a table, checked against text that never held it, is unverifiable.
- **A pass that slices cannot slice the join.** `plan_readings` cuts a window around the composition, and
  the tables sit past the end of any window anchored on a heading. So it windows the body and joins the
  tables on afterwards. Before that, whether a reader saw the tables depended on whether `window` fell
  back to keeping the tail — present on one document and absent on the next.
- **Whether this makes readings better is unmeasured.** The gold set has one confirmed label and it scores
  the same either way.
- **A table wrongly kept is noise; a table wrongly dropped is a composition nobody can see.** So the shape
  is not judged: whatever the extractor found is rendered, and only what cannot be written as a table at
  all — under two filled rows, under two columns — is discarded. That asymmetry is deliberate and will
  put junk in some files.
