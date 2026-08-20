# ask-worldover is published here, not written here

`skills/ask-worldover/docs/` is a copy. It is written in the private worldmaker repository, at
`sprite-assets/skills/worldover-ask/docs/`, and published into this repo by a skill that lives there.
Publishing goes one way: nothing in this repo is ever carried back.

The guides answer for two agents — the chat inside a customer's Worldmaker app, and Claude Code on the
user's own machine — and a journey crosses between them repeatedly. One set of guides answering for both
is the point: whichever agent the user is talking to can describe the whole journey and hand over cleanly
at the crossing. Two divergent copies would mean each agent describing the other's half wrongly.

## Why a copy rather than a link

A submodule or a subtree would give a real git relationship, and both were rejected:

- **worldmaker is private.** A submodule pointing at it makes this public repo unusable to anyone without
  access to that one — the clone fails, and the failure is confusing rather than explanatory.
- **A subtree gives push-back.** `git subtree push` from here to there is exactly the capability we did
  not want: worldmaker is the source of truth, and a public repo that can write into a private one is a
  door nobody asked for.
- **Sparse-checkout does not narrow a submodule's history**, only its working tree, so it buys nothing
  here.

So: a vendored copy, the same arrangement `vendor/` already uses for third-party skills, except the
upstream is ours.

## What is owned where

| Path | Owner |
| --- | --- |
| `skills/ask-worldover/docs/` | worldmaker. Overwritten wholesale by each publish. |
| `skills/ask-worldover/SKILL.md` | this repo. It names `{LOCAL}`; worldmaker's names `{WORLDMAKER}`. |
| `CONTEXT.md`, `README.md`, `plugin.json`, `marketplace.json`, `docs/adr/` | this repo. |

Publishing worldmaker's `SKILL.md` over this one would break the plugin: it points at a relative path
that only resolves on a sprite, and it would tell the agent it is the app's assistant when it is Claude
Code on somebody's laptop.

## Consequences

- **A typo fix made here is lost.** The next publish overwrites `docs/` without merging. `SKILL.md` says
  so, at the top, because that is where somebody about to edit the wrong file is looking.
- **The two copies drift between publishes**, and only worldmaker knows by how much. It records the last
  published commit of each repo in `SYNC_STATE.json` beside its own `SKILL.md`; this repo holds no
  equivalent file, because nothing here needs to know.
- **These guides name Worldmaker's screens, controls and internal journeys, on a public repo.** That is
  intended — the plugin is installed by the people those screens belong to, and the guides carry no
  customer data, no credentials and no source.
- **A drifted control name is invisible from here.** The guides answer in click-paths, so a renamed button
  makes them wrong and no test in either repo catches it. The check that does lives in worldmaker's
  publishing skill, which greps every bolded control name against the app's source.
