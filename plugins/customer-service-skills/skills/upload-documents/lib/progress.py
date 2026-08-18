"""How a pass says how far along it is, while it is still running.

The user watching a run is not a developer and cannot see a terminal: what this writes reaches them as
chat, unaltered, so every line is a sentence rather than a counter. `docs/PRESENTING.md` holds the rest
of that rule.

Three lines and one floor:

- the **opener** goes out the moment the pass starts, carrying counts and no time, because nothing has
  been measured yet and an invented estimate is indistinguishable from a real one;
- a **tick** thirty seconds in, the first moment a rate exists to quote, another five minutes later
  while the estimate is still settling, and one every fifteen minutes after that;
- the **close**, always, so a pass that finished under the floor still costs exactly two lines.

Progress goes to stderr and the end-of-run report stays on stdout, so the two can be read apart.
"""

import sys
import time

# The waits before the first ticks, then the one every tick after them keeps to. Front-loaded because the
# early updates are the ones carrying news - an estimate, then a corrected estimate - and the later ones
# only say the pass is still alive.
WAITS = (30.0, 300.0)
FLOOR = 900.0


class Pass:
    """One mechanical script run, counted in a unit of its own.

    `verb` and `unit` build the tick — "Read 4,200 of 30,922 document files" — while the opener and the
    close are the caller's own sentences, since only the caller knows what makes this pass worth
    mentioning.
    """

    def __init__(self, total, unit, verb, clock=time.monotonic, out=None, floor=FLOOR, waits=WAITS):
        self.total = total
        self.unit = unit
        self.verb = verb
        self.clock = clock
        self.out = sys.stderr if out is None else out
        self.floor = floor
        self.waits = waits
        self.done = 0
        self.started = None
        self.spoke_at = None
        self.ticks = 0
        # A Windows console defaults to a codepage that cannot print a customer's file names, and these
        # lines quote them.
        if hasattr(self.out, "reconfigure"):
            self.out.reconfigure(encoding="utf-8", errors="replace")

    def start(self, line):
        self.started = self.spoke_at = self.clock()
        return self._say(line)

    def advance(self, count=1):
        self.done += count
        now = self.clock()
        wait = self.waits[self.ticks] if self.ticks < len(self.waits) else self.floor
        if now - self.spoke_at < wait:
            return None
        self.spoke_at, self.ticks = now, self.ticks + 1
        return self._say(self._tick(now))

    def close(self, line):
        return self._say(line)

    def spent(self):
        """How long this pass took, for the close line to say."""
        seconds = self.clock() - self.started
        if seconds < 10:
            return "a few seconds"
        if seconds < 90:
            return f"{round(seconds)} seconds"
        if seconds < 5400:
            return f"{round(seconds / 60)} minutes"
        return f"{seconds / 3600:.1f} hours"

    def _tick(self, now):
        elapsed = now - self.started
        rate = self.done / elapsed if elapsed > 0 else 0
        counted = f"{self.verb} {self.done:,} of {self.total:,} {self.unit}"
        left = time_left(self.total - self.done, rate)
        return f"{counted}, {left}." if left else f"{counted}."

    def _say(self, line):
        print(line, file=self.out, flush=True)
        return line


def time_left(remaining, rate):
    """What is left to do, in the words a person would use, or nothing where nothing is known yet."""
    if rate <= 0:
        return None
    seconds = remaining / rate
    if seconds < 45:
        return "nearly done"
    if seconds < 90:
        return "about a minute left"
    return f"about {round(seconds / 60)} minutes left"


def guard(main, after="Nothing was written."):
    """Run a pass, and let a death reach the user as one sentence rather than a traceback.

    `SystemExit` is deliberately not caught: a preflight that stops the run has already said why, in
    better words than anything here could add.
    """
    try:
        main()
    except MemoryError:
        raise SystemExit(f"Stopped — this machine ran out of memory. {after}")
    except Exception as error:
        raise SystemExit(f"Stopped — {type(error).__name__}: {error}. {after}")
