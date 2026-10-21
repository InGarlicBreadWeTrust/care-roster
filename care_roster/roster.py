"""Weekly roster construction and rendering.

Turns a flat list of :class:`~care_roster.models.CareEvent` into a grouped,
sorted schedule and renders it as a text table. Two structural helpers are
exposed: :func:`sort_events` (deterministic ordering) and :func:`detect_overlaps`
(which finds same-person or same-carer events that collide in time -- how you
spot a double-booking).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from .models import CareEvent, parse_iso

    # NOTE: the lines below are inside module level; keep a 4-space body.


@dataclass
class Overlap:
    """Two care events that collide on a shared axis (person or caregiver)."""
    axis: str              # "person" or "caregiver"
    key: str               # the person/caregiver id the two events share
    first: CareEvent
    second: CareEvent
    overlap_minutes: int

    @property
    def overlap_start(self) -> datetime:
        return max(self.first.start_dt, self.second.start_dt)

    @property
    def overlap_end(self) -> datetime:
        return min(self.first.end_dt, self.second.end_dt)


def sort_events(events) -> list:
    """Return events ordered by start, then caregiver, then person (stable)."""
    return sorted(events,
                  key=lambda e: (e.start_dt, e.caregiver_id, e.person_id))


def event_days(events) -> list:
    """The calendar days on which at least one event starts, ascending."""
    return sorted({e.start_dt.date() for e in events})


def week_range(week: str) -> tuple:
    """Return the ``[start, end)`` datetimes for an ISO week like ``2026-W42``.

     The week runs Monday 00:00 through the following Monday 00:00, naive UTC.
     """
    m = re.match(r"^(\d{4})-W(\d{1,2})$", str(week).strip().upper())
    if not m:
        raise ValueError("week must look like 'YYYY-Www', got %r" % (week,))
    year = int(m.group(1))
    wk = int(m.group(2))
    if not (1 <= wk <= 53):
        raise ValueError("week number out of range: %d" % wk)
    monday = date.fromisocalendar(year, wk, 1)
    start = datetime.combine(monday, time.min)
    return start, start + timedelta(days=7)


def events_in_range(events, start, end) -> list:
    """Return the events that start within ``[start, end)`` (strings or dt)."""
    lo = parse_iso(start) if isinstance(start, str) else start
    hi = parse_iso(end) if isinstance(end, str) else end
    return [e for e in events if lo <= e.start_dt < hi]


def detect_overlaps(events, by: str = "caregiver") -> list:
    """Find overlapping care events, grouped by ``by`` ('person' or 'caregiver').

     Every overlapping pair is reported (not just the first), so a busy day with
     many collisions is fully surfaced as a stably-ordered list.
     """
    if by not in ("person", "caregiver"):
        raise ValueError("by must be 'person' or 'caregiver'")
    axis = "caregiver" if by == "caregiver" else "person"
    key_of = lambda e: e.caregiver_id if by == "caregiver" else e.person_id
    groups = {}
    for e in events:
        groups.setdefault(key_of(e), []).append(e)

    overlaps = []
    for key in sorted(groups):
        evs = sorted(groups[key], key=lambda e: (e.start_dt, e.end_dt))
        for i in range(len(evs)):
            for j in range(i + 1, len(evs)):
                a, b = evs[i], evs[j]
                if b.start_dt < a.end_dt:
                    om = round((min(a.end_dt, b.end_dt) - max(a.start_dt, b.start_dt))
                                .total_seconds() / 60.0)
                    overlaps.append(Overlap(axis, key, a, b, om))
    overlaps.sort(key=lambda o: (o.axis, o.key, o.first.start_dt,
                                 o.second.start_dt))
    return overlaps


@dataclass
class Roster:
    """A grouping of care events with per-day / per-person view helpers."""
    events: list = field(default_factory=list)
    people: dict = field(default_factory=dict)    # id -> Person
    day_range: tuple = None                        # (start, end) datetimes

    def name(self, pid: str) -> str:
        """Friendly name for ``pid`` (falls back to the id itself)."""
        person = self.people.get(pid)
        return person.name if person else pid

    def days(self) -> list:
        """Calendar days spanning the roster (from ``day_range`` if present)."""
        if self.day_range:
            out = []
            d = self.day_range[0].date()
            last = self.day_range[1].date()
            while d <= last:
                out.append(d)
                d += timedelta(days=1)
            return out
        return event_days(self.events)

    def events_for(self, person_id=None, day=None) -> list:
        """Events optionally filtered by ``person_id`` and/or calendar day."""
        evs = self.events
        if person_id is not None:
            evs = [e for e in evs if e.person_id == person_id]
        if day is not None:
            target = day if isinstance(day, date) else parse_iso(day)
            target = target.date() if isinstance(target, datetime) else target
            evs = [e for e in evs if e.start_dt.date() == target]
        return sort_events(evs)

    def overlaps(self, by: str = "caregiver") -> list:
        """Overlapping events across the roster, as :class:`Overlap` records."""
        return detect_overlaps(self.events, by=by)

    def render(self, person=None) -> str:
        """A per-day, per-person text schedule, returned as a string."""
        lines = []
        person_ids = ([person] if person
                       else sorted({e.person_id for e in self.events}))
        for day in self.days():
            lines.append("%s" % day.strftime("%A %Y-%m-%d"))
            any_on_day = False
            for pid in person_ids:
                day_events = self.events_for(pid, day)
                if not day_events:
                    continue
                any_on_day = True
                lines.append("   %s" % self.name(pid))
                for e in day_events:
                    lines.append("     %-5s  %-8s  %-10s  %s"
                                 % (e.type, self.name(e.caregiver_id),
                                    e.note or "-",
                                    e.start_dt.strftime("%H:%M-%H:%M")))
            if not any_on_day:
                lines.append("   (no care events)")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def build_weekly_roster(events, people: dict = None, week: str = None,
                        start=None, end=None) -> Roster:
    """Build a :class:`Roster` for a calendar week or an explicit range.

     With ``week='YYYY-Www'`` the roster spans that ISO week; otherwise it spans
     ``[start, end)`` (defaulting to the events' own calendar span).
     """
    if week is not None:
        start, end = week_range(week)
    elif start is None or end is None:
        if not events:
            today = date.today()
            start = datetime.combine(today, time.min)
            end = start + timedelta(days=1)
        else:
            lo = min(e.start_dt for e in events).replace(
                hour=0, minute=0, second=0, microsecond=0)
            hi = max(e.end_dt for e in events).replace(
                hour=0, minute=0, second=0, microsecond=0)
            start, end = lo, hi + timedelta(days=1)
    else:
        start = parse_iso(start) if isinstance(start, str) else start
        end = parse_iso(end) if isinstance(end, str) else end
    filtered = events_in_range(events, start, end)
    return Roster(events=sort_events(filtered),
                  people=people or {}, day_range=(start, end))
