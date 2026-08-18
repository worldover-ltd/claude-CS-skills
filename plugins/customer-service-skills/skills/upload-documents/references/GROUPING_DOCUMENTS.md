# Grouping the documents by form

How the step between extraction and classification turns a folder of documents into a handful of *forms*,
each with a title and a description a person has confirmed. See `docs/adr/0004` for why it exists and why
it is shaped this way.

A **form** is the blank stationery a document is printed on. It is not a *document template* — it says
what the paper is, not what the app calls it. Nothing here picks a document template, and no agent in this
step is shown the app's list.

## The three passes

### Group — a script, no agents

```sh
<interpreter> "${CLAUDE_PLUGIN_ROOT}/skills/upload-documents/lib/grouping/group_documents.py" ".workflow/active/${sessionId}"
```

Reads `DOCUMENTS.json` and `EXTRACTED.json`, writes `FORMS.json`. The unit is the **document**, not the
file: copies share a sha and are grouped once, per ADR-0001.

It reports how many forms it found, how strongly their members joined, and the wording each form shares.
Two settings decide the outcome and both are recorded in the output so a form can be explained later:

- `--floor-fraction` (0.025) — a word must appear on this share of the folder to count as printed on a
  form rather than typed into one.
- `--threshold` (0.55) — how much of their form wording two documents must share to be one form.

Those defaults come from one real folder of 1,887 scanned documents, where they put 98.4% of documents in
a form whose members all turned out to be the same type. **They are a starting point, not a constant.**
`--sweep` reports what other settings do to the same folder and writes nothing:

```sh
<interpreter> ".../lib/grouping/group_documents.py" ".workflow/active/${sessionId}" --sweep
```

There is no ground truth in a real run, so the sweep reports *shape* — how many forms, how big the largest
is, how many documents end up alone — rather than accuracy. Nothing turns it into a judgement: the step
that asked a person went with `docs/adr/0007`, so treat the defaults as the measurement and leave them
where it put them.

**A folder under about forty documents is skipped**, and `FORMS.json` says so in `skipped`. Read those one
at a time; "a word most documents share" means nothing at that size.

### Name — one agent per form

```sh
<interpreter> ".../lib/grouping/plan_naming.py" ".workflow/active/${sessionId}"
```

Writes one task per form under `naming/`, each carrying up to five members' **structure view** — their own
text with everything the form does not repeat blanked out, counted inside that form. Send them the same
way as the classification fan-out: one agent per task, one file path each, twenty at a time, on
`claude-haiku-4-5`.

The prompt. Substitute the task's input and output paths; nothing else changes between forms.

```
Read the JSON file at <task input path>. It holds `samples` — several documents that are printed on the
same blank form, with everything typed into them blanked out as `_`. What is left is the form itself: its
title, its field labels, its column headings.

Say what this form is. Not what one of these documents is about — what the blank form is for, and what
somebody fills in on it.

Write your answer to <task output path> as JSON:

{"formId": "<the formId from the input, copied exactly>",
 "title": "…",
 "description": "…"}

`title` names the form as somebody in the industry would name it, at most 120 characters. Example:
"Specifications and Analytical Report for Raw Materials".

`description` says what the form is for and what it carries, at most 600 characters. Name the fields and
sections you can actually see. Example: "A controlled quality document template used to define the
required specifications for a raw material and to record the corresponding analytical or inspection
results. It may include test parameters, test methods, units of measure, acceptance criteria, results,
conformity status, approvals, and revision history."

Three things to hold to:

- **Describe the form, not one filled-in copy of it.** The top few lines are shown exactly as they were
  read, because that is where the title is — so a material name, a supplier or a document number can
  appear there. Compare the samples: whatever differs between them is somebody's answer, not the form.
- **Do not guess at a document type the app might have.** You have not been shown the app's list and you
  are not choosing from it. Say what the paper is.
- Where the samples do not look like one form at all, say so in the description and keep the title
  general. That is a useful answer, and somebody checks it next.

Reply with the title you wrote and nothing else.
```

Then count who answered, in code rather than by eye:

```sh
<interpreter> ".../lib/grouping/collect_names.py" ".workflow/active/${sessionId}"
```

Writes `NAMED.json`, trims anything over the limits, drops an answer that names a form it was not shown,
and lists the forms to send again. The roll call is counted against `NAMING.json` — never against what an
agent said it did. On the run this work came out of, six batches reported one fewer answer than they held
and every one was complete.

## Splitting a form by hand

A run no longer shows the forms to anybody — `docs/adr/0007` says why, and what that costs. Everything
below still runs; nothing calls it. `references/REVIEWING_BY_EYE.md` and `lib/review/` describe the page
that used to feed it, kept for the next thing this skill needs eyes on.

```sh
<interpreter> ".../lib/grouping/apply_marks.py" ".workflow/active/${sessionId}"
```

Reads `REVIEW_RESULT.json` and writes `SPLIT_RULES.json`, which every later step still honours. Write
either file by hand to reach one of four outcomes per form:

- **Few marks, grouping held** — the form stands and the marked documents are taken out of it, into
  `readOneAtATime`.
- **Failing, and the marks separate** — the wording that tells them apart becomes a rule. Run
  `group_documents.py` again to apply it, then name the new forms.
- **Failing, and nothing separates them** — the form **dissolves**. Every member goes to
  `readOneAtATime`, which is how this skill behaved before grouping existed.
- **Split by value** — the person said these are the same paper and the app still calls them different
  things. Not a failure and not repairable: no wording can separate them, because what separates them is
  what was typed in. The form stands whole and its members are read one at a time, carrying whatever the
  person said it splits into. See `docs/adr/0005`.

Where nothing separates them and somebody can describe the difference in words, that description becomes
wording in the rules file by hand. **It never becomes a change to the script.** The script is the
same script on every folder, which is what makes a form reproducible and lets you tell a customer *why*
their documents were grouped the way they were. A pipeline that rewrites itself per customer is what the
run this came out of actually did, and it silently removed every guard the pipeline had.

Dissolving always terminates, so the loop cannot spin. It is also the right answer more often than it
sounds — the one genuinely contested form on the original folder had no separating wording at all, because
the disagreement was about what to *call* it rather than which documents belonged.

## Held up against the app's list

```sh
<interpreter> ".../lib/grouping/check_vocabulary.py" ".workflow/active/${sessionId}"
```

Every form's title against every document template the app has. Writes `VOCABULARY_GAP.json`, decides
nothing, and reports the forms nothing fits with the number of documents behind each.

This only works because the titles were written **before** any agent saw the app's list. A form named
after seeing `Questionnaire` is called `Questionnaire`, its title matches, and the gap disappears — which
is exactly the failure the step exists to catch. It is also why naming and classification stay two agents
rather than one; see `docs/adr/0005`.

## What the classification step gets

**The form is what gets classified, not its documents.** One agent per form, given the form's own title
and description and the app's list, and its answer covers every member — `docs/adr/0005` has the
arithmetic. Four kinds of document are still read one at a time, and between them they are the whole of
what a per-document batch now carries:

- members of a form marked **split by value** — same paper, and the app calls them different things
  because the difference was typed in;
- documents in `readOneAtATime`, from a dissolved form or a mark on a form that otherwise held;
- forms of one document, where per-form and per-document are the same thing;
- every document in a folder too small to group, exactly as before this step existed.

## Files

| File | Holds |
| --- | --- |
| `FORMS.json` | one entry per form: members, how strongly each joined, shared wording, and the settings used |
| `naming/f01.json` | one naming task: the form's id, its size, and up to five structure views |
| `NAMING.json` | the tasks, with the input and output path of each |
| `named/f01.json` | one agent's answer |
| `NAMED.json` | title and description per form, plus who did not answer and what was trimmed |
| `REVIEW_RESULT.json` | the person's verdict per form, and the documents they marked |
| `SPLIT_RULES.json` | the rules to apply, the forms that dissolved or split by value, and the documents to read alone |
| `VOCABULARY_GAP.json` | which forms the app has a template for, which it does not, and how many documents ride on each |
| `form_templates/f01.json` | one form-classification task: the form's name, its samples, and the app's list for its tables |
| `FORM_CLASSIFICATION.json` | those tasks, and the forms deliberately not asked here |
| `FORM_TEMPLATES.json` | the template each form turned out to be, and how many documents that answer stands for |
