# Vendored third-party skills

These files are copies of MIT-licensed work by other authors, kept here so a run reaches them through
`${CLAUDE_PLUGIN_ROOT}` without the user installing a second marketplace. They are **references**, not skills:
nothing here is registered in `plugin.json`, so none of it loads a description into context or fires on its own.
A step in a `SKILL.md` points at one when it needs it.

Each copy is upstream text with sections **deleted** and nothing added, so a diff against the source stays
readable and re-vendoring is a fresh copy plus the same cuts. Everything this repo wanted to *change* lives in
`docs/PRESENTING.md` instead, which overrides these files where they disagree.

---

## `communication-style/`

- Upstream: <https://github.com/tzachbon/smart-ralph>, `plugins/ralph-speckit/skills/communication-style/SKILL.md`
- Vendored at commit `b26bb231606391ecf1e2a31ac4bbbf54c59b6429` (2026-07-23), skill version 0.1.0
- Why the 0.1.0 speckit copy and not the 0.2.0 one under `plugins/ralph-specum/`: examples are inline rather
  than in a separate file, and it carries no `user-invocable: false`. The four output rules are identical.

**Deleted:** the `## SpecKit-Specific Guidelines` section — constitution markers (`[C§3.1]`), user story IDs
(`[US1]`, `T001`) and task-description conventions, all of which belong to the Ralph spec-driven workflow.

**Overridden by `docs/PRESENTING.md`:** the "fragments over full sentences" rule, for the opening overview only,
and rule 4 — unresolved questions go through `AskUserQuestion`, not a bullet list.

```
MIT License
Copyright (c) 2025 tzachbon
```

---

## `mermaid-diagrams/`

- Upstream: <https://github.com/ccheney/robust-skills>, `skills/mermaid-diagrams/`
- Vendored at commit `4cc951a6005844c3d779b41fa0ad8f900b6417ad` (2026-07-07)
- Syntax is pinned to Mermaid v11.16. When Mermaid ships a major version, re-vendor — the gotchas list is the
  part that goes stale.

**Deleted from `SKILL.md`:** every diagram type these skills have no use for — sequence, gantt, timeline,
journey, gitGraph, mindmap, pie, xychart, sankey, quadrant, kanban, packet, block, C4, architecture-beta,
treemap and requirement — from both the decision tree and the types table, along with their examples and the
two gotchas that only applied to them. Also deleted: the `npx @mermaid-js/mermaid-cli` validation step, which
needs Node and a first-run Chromium download that a CS person's laptop should not be asked for.

**Kept:** flowchart, `erDiagram`, `classDiagram`, `stateDiagram-v2`. Every type still offered has its reference
file present.

**References vendored:** `FLOWCHARTS.md`, `CLASS-ER.md`, `STATE-JOURNEY.md`, verbatim. The other five upstream
references (`SEQUENCE.md`, `DATA-CHARTS.md`, `ARCHITECTURE.md`, `ADVANCED.md`, `CHEATSHEET.md`) cover the
deleted types and are not here.

```
MIT License
Copyright (c) 2026 robust-skills contributors
```
