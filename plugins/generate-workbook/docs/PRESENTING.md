# Presenting a run to the user

Two vendored references carry the general rules, and this file carries only where this plugin departs from
them. Where they disagree, this file wins.

- `${CLAUDE_PLUGIN_ROOT}/vendor/communication-style/SKILL.md` — how output is shaped: the four-part order,
  the brevity rewrites, the anti-patterns. Read it once at the start of a run.
- `${CLAUDE_PLUGIN_ROOT}/vendor/mermaid-diagrams/SKILL.md` — how a diagram is drawn: which type to pick, the
  syntax, and the parse errors worth avoiding. Read it when you are about to draw one.

## The reader

A Customer Service person mid-run, not a developer and not an executive reading a finished document. They are
deciding whether 412 documents landed on the right substances, and they will act on your answer immediately.

**The jargon test:** a term they use with customers is a term you can use — item, code, SKU, raw material, SDS,
CoA, batch. A term that belongs to the database is one you replace — foreign key, join, tidy data, schema,
nullable, cardinality. When one is unavoidable, define it in five words on first use and then just use it.

## Where the vendored voice bends

`communication-style` optimises for a developer scanning terminal history, which is the wrong trade in exactly
two places.

**Full sentences in the opening overview.** Its rule 1 ("fragments over full sentences", "sacrifice grammar for
concision") applies from the main content down. The 2–3 sentence overview at the top is the part a
non-technical reader leans on to orient, and a fragment there reads as curt rather than efficient. Everything
below the overview stays fragments, tables and bullets.

**Questions are asked, not listed.** Its rule 4 has unresolved questions as a bullet list above the action
steps. Here they go through `AskUserQuestion` instead — a list of questions in prose invites one prose reply
covering some of them, which is how a run loses an answer.

## Asking

`AskUserQuestion` is the plugin's decision surface. It is the one visual affordance that works in the terminal,
where a diagram does not, and its answers come back attached to the question rather than needing to be parsed
out of a paragraph.

| Where | Shape |
|---|---|
| Preflight, tooling missing | One question, install or carry on without those file types |
| Which customer, which app | One question once you have candidate repos; free text before that |
| The mapping's target entities | `multiSelect` where one pile of data feeds more than one entity |
| The tree reading, branch by branch | One question per branch, `preview` carrying the real folder names |
| The exception pile | One question per unresolved document, its file name and folder in the description |
| Artifact approval | Approve, iterate, or stop |

Two to four options each, and put your recommendation first with `(Recommended)` on the label — you did the
digging, so bring an answer rather than a menu. Never add an "Other" option; it is supplied. Reach for `preview`
whenever the choice is between two concrete things the user should see side by side — two readings of a branch,
two candidate identifier columns, two sample rows.

Ask when the answer changes what gets built. Decide for yourself when a careful colleague would, and say what
you decided.

## Showing

Match the thing to the surface that can actually draw it:

| To show | Use | Where |
|---|---|---|
| The shape of some data, mid-conversation | A small markdown table | Terminal |
| A choice | `AskUserQuestion` | Terminal |
| A structure — entities, a folder tree, a lifecycle | A mermaid diagram | A `.md` artifact |
| The whole reading, for approval | A `.md` artifact | Published, private by default |

Artifacts are published as **markdown**, not HTML. A ```` ```mermaid ```` fence renders in a `.md` artifact; in
an `.html` file the same fence is literal text, which is how a diagram silently ships as a code block.

Artifacts need a paid plan and an authenticated session. Where publishing is refused, write the same content to
`.workflow/active/${sessionId}/` as a markdown file and walk the user through it in the terminal — the approval
gate still has to happen.

## The diagram brake

`mermaid-diagrams` is written to suggest diagrams proactively, which is right for its author and too eager
here. A run draws a diagram in three places and no others: the app's entities (`erDiagram`), the folder tree
(`flowchart TD`), and the upload lifecycle (`stateDiagram-v2`). Everything else is a table.

Two rules on top of that reference:

- **Label every edge out of a decision.** An unlabelled branch out of a `{diamond}` is the one thing a diagram
  of decisions cannot afford — the reader cannot tell which way is which.
- **The headline is the takeaway, not the topic.** Above each diagram, one sentence saying what to conclude:
  not "Folder tree" but "Every document resolves to a raw material code except the 14 under `Misc/`."
