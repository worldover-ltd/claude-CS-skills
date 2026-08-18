"""The cadence a pass reports on, at the seam that decides it: a clock in, lines out.

The clock is injected rather than slept through, because the thing under test is a 30-second floor and a
test that waited for it would take longer than the pass it is protecting.
"""

import io
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "plugins/customer-service-skills/skills/upload-documents/lib"
sys.path.insert(0, str(LIB))

import progress  # noqa: E402


class FakeClock:
    """A clock the test winds by hand, standing in for `time.monotonic`."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def wind(self, seconds):
        self.now += seconds


def a_pass(clock, out, total=1000, unit="document files", verb="Read"):
    return progress.Pass(total, unit, verb, clock=clock, out=out)


class OpenerTest(unittest.TestCase):
    def test_the_opener_goes_out_immediately(self):
        clock, out = FakeClock(), io.StringIO()
        a_pass(clock, out).start("Reading 1,000 document files.")
        self.assertEqual(out.getvalue(), "Reading 1,000 document files.\n")

    def test_the_opener_is_the_callers_sentence(self):
        clock, out = FakeClock(), io.StringIO()
        a_pass(clock, out).start("842 are scans, so I'm reading the pictures - the slow part.")
        self.assertIn("the slow part", out.getvalue())


class FloorTest(unittest.TestCase):
    def test_nothing_is_said_in_the_first_half_minute(self):
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out)
        run.start("Reading 1,000 document files.")
        clock.wind(20)
        self.assertIsNone(run.advance(400))

    def test_the_first_update_lands_half_a_minute_in(self):
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out)
        run.start("Reading 1,000 document files.")
        clock.wind(30)
        self.assertEqual(run.advance(200), "Read 200 of 1,000 document files, about 2 minutes left.")

    def test_the_waits_lengthen_as_the_news_thins(self):
        """Thirty seconds to the estimate, five minutes to the corrected one, fifteen thereafter."""
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out)
        run.start("Reading 1,000 document files.")
        for wait, expected in ((30, True), (299, False), (1, True), (899, False), (1, True),
                               (899, False), (1, True)):
            clock.wind(wait)
            self.assertEqual(run.advance(1) is not None, expected, f"after winding {wait}s")

    def test_a_pass_shorter_than_the_first_wait_costs_an_opener_and_a_close(self):
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out, total=5)
        run.start("Reading 5 document files.")
        clock.wind(2)
        run.advance(5)
        clock.wind(1)
        run.close("Read 5 document files.")
        self.assertEqual(len(out.getvalue().strip().split("\n")), 2)


class TimeTest(unittest.TestCase):
    def test_the_time_left_is_measured_rather_than_assumed(self):
        """Two passes, same shape, different rates - the number follows what was observed."""
        clock, out = FakeClock(), io.StringIO()
        fast = a_pass(clock, out)
        fast.start("Reading 1,000 document files.")
        clock.wind(30)
        self.assertIn("about a minute left", fast.advance(300))

        clock, out = FakeClock(), io.StringIO()
        slow = a_pass(clock, out)
        slow.start("Reading 1,000 document files.")
        clock.wind(30)
        self.assertIn("about 16 minutes left", slow.advance(30))

    def test_the_last_stretch_claims_no_number(self):
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out)
        run.start("Reading 1,000 document files.")
        clock.wind(30)
        self.assertIn("nearly done", run.advance(980))

    def test_the_three_ways_of_saying_what_is_left(self):
        self.assertEqual(progress.time_left(10, 1), "nearly done")
        self.assertEqual(progress.time_left(60, 1), "about a minute left")
        self.assertEqual(progress.time_left(600, 1), "about 10 minutes left")
        self.assertIsNone(progress.time_left(600, 0))

    def test_a_pass_that_has_read_nothing_yet_claims_no_time(self):
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out)
        run.start("Reading 1,000 document files.")
        clock.wind(30)
        self.assertEqual(run.advance(0), "Read 0 of 1,000 document files.")

    def test_counts_are_written_the_way_a_person_reads_them(self):
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out, total=30922)
        run.start("Reading 30,922 document files.")
        clock.wind(30)
        self.assertIn("4,200 of 30,922", run.advance(4200))


class SpentTest(unittest.TestCase):
    def test_a_long_pass_is_reported_in_minutes(self):
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out)
        run.start("Reading 1,000 document files.")
        clock.wind(1440)
        self.assertEqual(run.spent(), "24 minutes")

    def test_a_pass_nobody_waited_for_claims_no_number(self):
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out)
        run.start("Reading 1,000 document files.")
        clock.wind(0.4)
        self.assertEqual(run.spent(), "a few seconds")

    def test_a_short_pass_is_reported_in_seconds(self):
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out)
        run.start("Reading 1,000 document files.")
        clock.wind(45)
        self.assertEqual(run.spent(), "45 seconds")


class CloseTest(unittest.TestCase):
    def test_the_close_always_goes_out(self):
        clock, out = FakeClock(), io.StringIO()
        run = a_pass(clock, out)
        run.start("Reading 1,000 document files.")
        clock.wind(1)
        run.close("Read 1,000 document files in a minute.")
        self.assertIn("in a minute", out.getvalue())


class GuardTest(unittest.TestCase):
    def test_running_out_of_memory_is_said_in_words(self):
        def die():
            raise MemoryError()

        with self.assertRaises(SystemExit) as stopped:
            progress.guard(die)
        self.assertIn("ran out of memory", str(stopped.exception))

    def test_any_other_death_names_itself_and_what_became_of_the_work(self):
        def die():
            raise ValueError("a page that would not open")

        with self.assertRaises(SystemExit) as stopped:
            progress.guard(die, "Everything read so far is kept.")
        self.assertIn("ValueError: a page that would not open", str(stopped.exception))
        self.assertIn("Everything read so far is kept.", str(stopped.exception))

    def test_a_pass_that_stopped_itself_keeps_its_own_words(self):
        """A preflight failure already says why, better than anything the guard could add."""
        def stop():
            raise SystemExit("uv is not installed")

        with self.assertRaises(SystemExit) as stopped:
            progress.guard(stop)
        self.assertEqual(str(stopped.exception), "uv is not installed")


if __name__ == "__main__":
    unittest.main()
