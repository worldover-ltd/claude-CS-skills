---
name: verify-document-skills-requirements
description: "Preflight Anthropic's official document skills (xlsx, docx, pdf) before a run depends on them — install them when absent, then probe every tool they require on this machine. Triggers on \"verify-document-skills-requirements\", when a run is about to read or write spreadsheets, Word documents or PDFs, or when another skill needs the document tooling confirmed before it starts."
allowed-tools: Agent, Skill, Read, Glob, Grep, Bash
---

### Goal

Reach the point where the official document skills are installed **and** every tool they depend on
has been shown to work on this machine — or the user knows exactly what is missing and who can fix it.

### Where this runs

This work belongs in a **sub agent**. Getting to a verdict means reading every installed document
skill, following their internal pointers, and running a probe per requirement — dozens of file reads
and command runs whose output matters only until the verdict is reached. A sub agent absorbs all of
it and hands back the verdict alone, leaving the calling run's context for the work the user cares
about.

So dispatch one sub agent to carry out the process below, and pass it the whole of it. When this skill
is already running inside a sub agent, carry out the process directly rather than delegating again.

Either way the verdict comes back in the shape given in "# Step 4", which is what the caller reads.

### Why probe rather than read

Those skills are written for Anthropic's managed environment, where their tooling ships preinstalled.
They say so in their own text: *"openpyxl, pandas and markitdown are preinstalled — do not run
`pip install` first"*. On a laptop that sentence describes the sandbox, not this machine.

So each requirement is settled by a **probe** — a command that actually runs and either succeeds or
fails. A requirement the skill claims is present, and which no probe has confirmed, counts as unknown.

### The user

The person running this is usually on the Customer Service team and does not install developer
tooling. Report in terms of what works and what does not, and route anything needing installation to
the engineering team rather than handing over commands to run.

### Process

# Step 1 — install the document skills

`claude plugin list` shows what is present. The skills come as the `document-skills` plugin from
Anthropic's own marketplace:

```sh
claude plugin marketplace add anthropics/skills
claude plugin install document-skills@anthropic-agent-skills
```

Adding a marketplace that is already configured, or installing a plugin already installed, is
harmless — run them when `claude plugin list` does not already show `document-skills`.

Where the `claude` command is not on this system's PATH, or installing is refused, the user can do it
themselves in the session by typing `/plugin marketplace add anthropics/skills` and then
`/plugin install document-skills`. Hand them those two lines and wait, rather than treating it as
unavailable.

Reading the installed files works immediately. Invoking the skills through the `Skill` tool needs a
restart of Claude Code, so mention that to the user at the end of the run if anything will invoke them.

Done when `claude plugin list` shows `document-skills` installed.

# Step 2 — read what the skills require

Find the installed skills on disk by asking the installation where it put them, rather than assuming a
layout. Claude Code records it in `plugins/installed_plugins.json` inside its config directory — the
`.claude` folder in the user's home directory, or wherever `CLAUDE_CONFIG_DIR` points when that is set.
The entry keyed `document-skills@anthropic-agent-skills` carries an `installPath`, and each skill sits
at `<installPath>/skills/<skill>/SKILL.md`.

Where that file or key is not there, `Glob` for `**/skills/*/SKILL.md` beneath the plugins directory
and pick out the document skills by name. Either route beats hardcoding a path: install scope, cache
layout and config location all vary between machines.

Read each one and harvest every dependency it names: Python libraries it imports, npm packages it
requires, command-line binaries it invokes, and anything it tells you to `pip install` or
`npm install` as a fallback. Some skills point at further files of their own — a reference or forms
document — and name tools only there, so follow those pointers before calling the list finished.

Build the list as one row per requirement: which skill needs it, what kind of thing it is, and what it
is used for. Requirements change as Anthropic updates these skills, which is why the list is read
fresh here rather than carried in this file.

Done when every installed document skill has been read, its own pointers followed, and each named
dependency appears in the list with the skill that needs it.

# Step 3 — probe every requirement

A probe **exercises** the capability. It does not load it and assume the rest.

The distinction is the whole point of this step, because the commonest failure passes an import and
dies on first use: a wrapper library around a system binary installs cleanly, imports cleanly, and
raises the moment it is asked to do anything, because the binary behind it was never there. Importing
such a library proves only that the wrapper exists.

So per row, run the smallest thing that would fail if the capability were absent — ask the tool for its
version through the wrapper, convert a scratch file, render one page. A row settled by an import alone
is unproven, and belongs in the report as such rather than as a pass.

Where a probe fails, say so in the verdict. Installing the fix is a separate decision:

- **A system binary** needs administrator rights the user does not have. Mark the row failed and leave
  it to the engineering team.
- **A Python library or npm package** could be installed here, so put it to the user first — name the
  package, the file types it unblocks, and that it changes the Python or Node setup on their machine.
  Install on a yes, into this system's own interpreter, and probe again. Install nothing globally with
  npm.

Asking costs one exchange and keeps a shared machine's environment the user's decision. A skill can
declare a dozen dependencies, and a verify run that installs each one it finds has quietly rebuilt
somebody's Python.

Where the user says yes and the install is still refused as an externally-managed environment — the
normal answer from a Linux or macOS Python that the operating system or a package manager put there —
that is the row failing. Getting past it needs a virtual environment or a different Python, which is
engineering's call.

Done when every row carries a pass or a fail from a command that exercised the capability, no row rests
on an import alone, and each fail is marked as declined, installed-and-passing, or still missing.

# Step 4 — return the verdict

A sub agent's final text is what the caller receives, so the verdict is that text — not a message to a
person. Return it in three parts:

1. **Covered file types** — the extensions that can be read right now, one line.
2. **Blocked file types** — one line each: the extension, what is missing, and the document skill that
   needed it. Frame it by consequence: "scanned PDFs — no OCR tool" says something a bare package name
   does not.
3. **Restart needed** — whether `document-skills` was installed during this run, since invoking those
   skills through the `Skill` tool needs Claude Code restarted.

Where a skill's own documented route is dead but the capability is reachable another way, both facts
belong in the verdict — the route that failed, and the one that works. A skill written for a managed
environment can prescribe a tool chain that never installs on a laptop while a pure-library route sits
right there, and the caller can only pick it up if the verdict names it.

Anything the user declined is reported as blocked, alongside the offer they turned down, so a later run
can raise it again rather than rediscovering it.

A partial pass is a normal result, not a failure: the covered types are usable immediately, and the
caller decides whether that is enough to continue.

Where anything is blocked on a system binary, the calling run tells the user — in the same plain terms
— that installing it needs someone from the engineering team.

Done when all three parts are present, and every probe that failed appears under a blocked file type.
