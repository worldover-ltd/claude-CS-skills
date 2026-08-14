# A form is classified once, not its documents

One agent is asked what the app calls each *form*, and its answer is carried to every document printed on
that form. Documents are read one at a time only where they have to be: a form a person marked as *split
by value*, a form that dissolved, a singleton, or a folder too small to group at all.

ADR-0004 said grouping "costs slightly more, not less", because the classification step still read every
document. That was the cautious choice at the time and the measurement since says it was the wrong one.

## Why

Once the folder is grouped, asking per document is asking the same question repeatedly and paying each
time. On the folder both real runs used — 1,887 documents in 17 forms — the arithmetic is:

| | readings |
| --- | ---: |
| per document | 1,887 |
| per form, plus the one form marked split by value | 16 + 68 = **84** |

Twenty-two times cheaper, and cheaper in the dimension that actually hurt: the first run's cost was
context multiplied by turns, not payload size.

It is also more correct, for the reason ADR-0004 already gives. Four supplier-form quotations produced
1,632 contradictory answers in one run — the same header line, read off documents the run then filed as
`Questionnaire`, as `Product Specification`, and as six different proposals. A form answered once cannot
contradict itself.

## What this rests on

The claim is narrow and worth stating exactly: **documents printed on the same stationery are the same
kind of document.** ADR-0004's measurements are what make it safe — a word set separated same-form from
different-form pairs by 28 points where 3-grams managed 5, and at a threshold of 0.55, 98.4% of documents
landed in a form whose members all turned out to be one type.

The 1.6% is why the exception exists.

## Where it does not hold: split by value

Some documents share stationery and are still different documents, because what separates them was typed
in rather than printed. A blank specification and the same sheet with its results filled in are one form
and two document templates.

Measured on the one such form in this folder — 68 members, 45 filed as Product Specification and 23 as
Certificate of Analysis:

```
Certificate of Analysis (CoA)   n= 23   fit mean=0.806  min=0.645  max=1.000
Product Specification           n= 45   fit mean=0.795  min=0.571  max=0.921
```

The grouping cannot see the difference, and that is not a defect in it: the words marking a filled sheet
sit below the mask floor, and their absence from the signature is exactly *why* these documents are one
form. So the split cannot be detected by the same machinery that found the form.

A person declares it, at the review, before anything is classified. They also say what it splits into, in
their own words, and that reaches the reading as data for that form alone — never a rule the skill carries
to the next customer. See ADR-0003 on why named tie-break pairs were rejected.

## Consequences

- **Naming and classification stay two agents, in that order.** The gate between them matches a form's
  title against the app's list, and that only means something if the title was written without the list in
  view. An agent shown `Questionnaire` first would name the form `Questionnaire`, the titles would match,
  and the gate would go quiet on precisely the failure it exists to catch.
- **A row can say where its answer came from.** `viaForm` is set on every document a form answered, and
  `standsFor` records how many documents one answer covers against how many were sampled. Five members
  read, 1,211 carried, and the workbook must not imply otherwise.
- **The quote check is weaker for these rows, and this is the price.** Per document, a quotation is checked
  against what that document's reader was given. Per form, it is checked against the samples the form's
  agent was shown. What holds the other members is the grouping, not a reading.
- **The review becomes load-bearing a third time.** It was already the only calibration the thresholds get
  (ADR-0004) and the only control on anchoring; it is now also the only place a value split can be
  declared. A run where nobody reviews is a run with no check on any of the three.
- **Below the grouping floor nothing changes.** A folder too small to group is read one document at a time,
  exactly as before.
