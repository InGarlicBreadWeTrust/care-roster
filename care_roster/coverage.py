"""Coverage-gap detection for a care roster.

For each person, on each day within a range, asks whether they are cared for
across the whole required window. Uncovered sub-intervals are surfaced as
:class:`Gap` objects, and every gap longer than a threshold (default 30 minutes)
is *flagged* as an actionable gap.

The coverage level is computed with a sweep line so the ``minimum_caregivers``
requirement is honoured exactly: at a requirement of 1 a gap is any instant with
zero caregivers; at a requirement of N it is any instant with fewer than N
caregivers. The result is deterministic: identical inputs yield an identical,
stably-sorted report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as _date, datetime, time, timedelta

from .models import parse_time


DEFAULT_THRESHOLD_MINUTES = 30
DEFAULT_WINDOW_START = "08:00"
DEFAULT_WINDOW_END = "20:00"
DEFAULT_WEEK_CAP_MINUTES = 40 * 60


@dataclass
class Window:
    """A daily required-coverage window ``[start, end)`` on the wall clock."""

    start: time
    end: time

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ValueError("Window.start (%s) must be before end (%s)"
                             % (self.start, self.end))

    @property
    def duration_minutes(self) -> int:
        """Length of the window in whole minutes."""
        return round((self.end - self.start).total_seconds() / 60.0)

    @classmethod
    def from_hm(cls, start_hm: str, end_hm: str) -> "Window":
        """Build a window from two clock strings like ``'08:00'`` / ``'20:00'``."""
        return cls(parse_time(start_hm), parse_time(end_hm))

    @classmethod
    def from_string(cls, spec: str) -> "Window":
        """Parse a window from a string like ``'08:00-20:00'``."""
        m = re.match(r"^\s*([01]?\d|2[0-3]):([0-5]\d)\s*[-\u2013]\s*"
                     r"([01]?\d|2[0-3]):([0-5]\d)\s*$", str(spec).strip())
        if not m:
            raise ValueError("coverage window must look like "
                             "'HH:MM-HH:MM', got %r" % (spec,))
        start = time(int(m.group(1)), int(m.group(2)))
        end = time(int(m.group(3)), int(m.group(4)))
        return cls(start, end)

    def datetimes_for(self, day: _date) -> tuple:
        """Absolute naive datetimes for this window on the given calendar day."""
        return datetime.combine(day, self.start), datetime.combine(day, self.end)


def default_window() -> Window:
    """The standard all-day care window: 08:00 to 20:00."""
    return Window.from_hm(DEFAULT_WINDOW_START, DEFAULT_WINDOW_END)


@dataclass
class Gap:
    """An under-covered slot for one person on one day."""

    person_id: str
    start: datetime
    end: datetime
    duration_minutes: int

    def exceeds(self, threshold: int = DEFAULT_THRESHOLD_MINUTES) -> bool:
        """True when the gap is longer than ``threshold`` minutes."""
        return self.duration_minutes > threshold

    @property
    def is_flagged(self, threshold: int = DEFAULT_THRESHOLD_MINUTES) -> bool:
        """True when the gap is longer than the threshold (default 30 min)."""
        return self.duration_minutes > threshold

    def day(self) -> _date:
        """The calendar day the gap falls on."""
        return self.start.date()


@dataclass
class CoverageReport:
    """The outcome of a coverage computation over a range of windows."""

    gaps: list = field(default_factory=list)
    total_minutes_uncovered: int = 0
    threshold_minutes: int = DEFAULT_THRESHOLD_MINUTES

    @property
    def flagged(self) -> list:
        """Gaps longer than the threshold, stably ordered (person, start, end)."""
        ordered = sorted(self.gaps, key=lambda g: (g.person_id, g.start, g.end))
        return [g for g in ordered if g.duration_minutes > self.threshold_minutes]

    @property
    def is_complete(self) -> bool:
        """True when no person has any uncovered minute."""
        return self.total_minutes_uncovered == 0


def _undercovered_intervals(day_start, day_end, event_iterable, minimum) -> list:
    """Sub-intervals where fewer than ``minimum`` events overlap, via a sweep.

    Within ``[day_start, day_end)`` this returns the sub-intervals on which the
    concurrent number of overlapping events falls below ``minimum``. At a shared
    boundary an ending and a starting event are applied together (ends sort
    before starts), so a clean handoff at exactly an hour makes no spurious
    zero-minute gap.
    """
    changes = []
    for e in event_iterable:
        s = e.start_dt if e.start_dt > day_start else day_start
        en = e.end_dt if e.end_dt < day_end else day_end
        if en <= s:
            continue
        changes.append((s, 1))
        changes.append((en, -1))
    changes.sort(key=lambda c: (c[0], c[1]))

    intervals = []
    cursor = day_start
    count = 0
    for t, delta in changes:
        if count < minimum and t > cursor:
            intervals.append((cursor, t))
        count += delta
        cursor = t
    if count < minimum and day_end > cursor:
        intervals.append((cursor, day_end))
    return intervals


def compute_coverage(windows, events, start, end,
                     threshold_minutes: int = DEFAULT_THRESHOLD_MINUTES,
                     minimum_caregivers: int = 1) -> CoverageReport:
    """Uncovered slots per person across every day in ``[start, end)``.

    ``windows`` maps ``person_id`` to a :class:`Window`; a gap is reported when
    the concurrent caregiver count falls below ``minimum_caregivers`` and is
    *flagged* when its length exceeds ``threshold_minutes`` (strictly greater).
    """
    if minimum_caregivers < 1:
        raise ValueError("minimum_caregivers must be >= 1")
    if end <= start:
        return CoverageReport(gaps=[], total_minutes_uncovered=0,
                              threshold_minutes=threshold_minutes)

    by_person = {pid: [] for pid in windows}
    for e in events:
        if e.person_id in by_person:
            by_person[e.person_id].append(e)

    gaps = []
    total = 0
    day = start.date()
    last_day = (end - timedelta(days=1)).date()
    while day <= last_day:
        for pid in sorted(windows):
            day_start, day_end = windows[pid].datetimes_for(day)
            for a, b in _undercovered_intervals(
                    day_start, day_end, by_person[pid], minimum_caregivers):
                dur = round((b - a).total_seconds() / 60.0)
                if dur > 0:
                    gaps.append(Gap(pid, a, b, dur))
                    total += dur
        day += timedelta(days=1)

    gaps.sort(key=lambda g: (g.person_id, g.start, g.end))
    return CoverageReport(gaps=gaps, total_minutes_uncovered=total,
                          threshold_minutes=threshold_minutes)


def _span_of(events) -> tuple:
    """Infer ``[start, end)`` from the events' calendar span (defaults today)."""
    if not events:
        today = _date.today()
        return datetime.combine(today, time.min), \
            datetime.combine(today + timedelta(days=1), time.min)
    lo = min(e.start_dt for e in events).replace(
        hour=0, minute=0, second=0, microsecond=0)
    hi = max(e.end_dt for e in events).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return lo, hi + timedelta(days=1)


def ensure_coverage(events, per_person_window, minimum_caregivers: int = 1,
                    start=None, end=None,
                    threshold_minutes: int = DEFAULT_THRESHOLD_MINUTES,
                    people=None) -> CoverageReport:
    """Validate that no single person is left uncovered.

    ``per_person_window`` is a single :class:`Window` broadcast to every person,
    or a mapping ``person_id -> Window``. ``start``/``end`` default to the
    calendar span of ``events``. Returns a :class:`CoverageReport`; check
    ``report.is_complete`` to see whether coverage holds for every person.
    """
    if per_person_window is None:
        return CoverageReport(gaps=[], total_minutes_uncovered=0,
                              threshold_minutes=threshold_minutes)
    if start is None or end is None:
        start, end = _span_of(events)
    if isinstance(per_person_window, Window):
        if people is None:
            people = sorted({e.person_id for e in events})
        windows = {pid: per_person_window for pid in people}
    else:
        windows = dict(per_person_window)
    return compute_coverage(windows, events, start, end,
                            threshold_minutes, minimum_caregivers)
