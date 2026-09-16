# The conversation

What a run holds in the chat it is running in, as against what it writes down. Read at the start of a run
alongside `PRESENTING.md`, and applied by every skill in this plugin.

Everything a run knows is under `.workflow/active/${sessionId}/`. The conversation holds no state of its
own. That is what makes it disposable — and what stops a long run paying for its own history on every
turn, because a conversation re-reads everything it holds every time it speaks.

What that costs when nobody watches it, measured on one run of 17,117 documents: **1,844 turns carrying
353,000 tokens each, $1,348 of a $1,463 run.** The sub agents that did the actual reading cost $114, of
which the classifier itself was $60. Coordination cost twelve times the work it coordinated.

Three rules follow.

## Start things, talk to the user, and look at nothing

The conversation starts work and speaks to the person. It does not look at what comes back. The line is
**start** against **look**: a script started is one tool call and a few lines of output, while a result
read is a file sitting in the conversation for every turn after it.

**The conversation does:** take the exported files and the folder, ask what the user wants left out,
run a pass, put a finding or a question to them, hand the workbook over. Anything where the next move is
theirs.

**A sub agent does:** read what a pass produced, say where a run has got to, read the answers, check the
workbook, and carry out whatever the user asks be done to it. Anything whose input is a file this run
wrote.

Where a step needs both — most of them do — the sub agent reads and reports, and the conversation asks.
So a sub agent's brief says to return **the question it owes as well as its findings**: the exception
pile, the proposals to create, the contradiction nobody has settled. It never returns the rows.

Measured on the same run: five `Read` calls were 426,538 tokens, **57% of everything the conversation ever
took in**, and every one was a file a sub agent could have answered in a paragraph. The sub agent channel
was already disciplined by comparison — 342 calls returning 279 tokens each. Of the whole bill, only 18%
was spent speaking to the user; 82% was acting and thinking with a third of a million tokens loaded.

Long passes are the exception that proves the rule: they stay in the conversation, under `Monitor`,
because `ADR-0006` says a pass reports in the user's words and half an hour of silence reads as progress.
Starting one is cheap. Reading what it wrote is not.

`ADR-0010` is the argument, including what it costs: with nothing reading the data end to end, a pass must
report the anomalies and not only the totals, because a total cannot look wrong.

## Compact at the heavy boundaries

Hashing, extraction, grouping and reading each leave a conversation far larger than they found it. At the
end of those steps — each skill says which — ask the user to compact, and say what it is in their words:
it clears what has been said so far and keeps a summary, and nothing is lost because the work is already
saved.

Left alone, a run compacts only when it is nearly full. On the measured run that was four times, twice
after context had passed half a million tokens. Doing it at the boundaries instead costs less than half as
much.

Not every step. Each compaction pays a full pass over the conversation to write its summary, and the
saving flattens quickly — three to five across a run is the shape, placed after the passes that read the
folder or fanned out.

## Keep the judgement in the steps

A conversation that starts passes and relays what they print is not exercising judgement; the judgement
lives in the steps where a person answers something. A run costs about five times less on a mid-sized
model than on the largest one, for identical answers, and the user chooses that before a run starts.

The sub agents this doc sends run on a mid-sized model too. They read files and report; nothing they do
needs the largest one.
