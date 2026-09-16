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

## Never read a data file into the conversation

Not a manifest, not a spreadsheet, not a folder listing, not a document. Run a script that prints counts
and anomalies, or send a sub agent that reads it and reports a short answer.

On that same run, five `Read` calls were 426,538 tokens — **57% of everything the conversation ever took
in** — and every one was a file a script could have summarised in twenty lines. The sub agent channel was
already disciplined by comparison: 342 calls returning 279 tokens each, because a sub agent's brief
already tells it to report rather than recite.

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

A conversation that launches passes and relays what they print is not exercising judgement; the judgement
lives in the steps where a person answers something. A run costs about five times less on a mid-sized
model than on the largest one, for identical answers, and the user chooses that before a run starts.
