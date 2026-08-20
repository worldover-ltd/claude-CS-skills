---
name: ask-worldover
description: "Guide a Customer Success user through getting a customer's data and documents into their Worldmaker app — what the journey is, which screen and control to use, and what to do when a migration or an upload fails. Triggers on \"ask-worldover\", or when the user asks how one of those works, or does not know what to do next."
allowed-tools: Read, Glob, Grep, AskUserQuestion
---

You are: `{LOCAL}`.

Read `${CLAUDE_PLUGIN_ROOT}/skills/ask-worldover/docs/SKILL_GUIDE.md`. It resolves the rest
of the docs against its own folder.

`docs/` is published here from the private worldmaker repository, which is where it is
written. A fix belongs there; a change made here is overwritten by the next publish. This
file is the plugin's own — it names `{LOCAL}`, where worldmaker's names `{WORLDMAKER}`.
