"""Data models for the care-roster coordination engine.

These are plain, network-free structures: people, scheduled care events,
tasks / reminders, and shift handoffs. Validation lives in ``__post_init__`` so a
malformed record is rejected at construction time rather than being tolerated
downstream. Every model can be flattened to / built from a plain ``dict`` (for the
JSONL audit store) without leaking its computed helpers.

Timezone note
-------------
All datetimes are normalised to *naive* UTC. Aware inputs are converted to UTC
and then stripped of their tzinfo, which keeps every comparison total-ordered
(and immune to the naive/aware TypeError) without importing a wall-clock clock.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, time, timezone
from typing import Any

import re


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------
#: Allowed Person.role values.
ROLE_VALUES = ("caregiver", "recipient", "patient", "admin")

#: Allowed CareEvent.type values.
EVENT_TYPES = ("feeding", "bathing", "meds", "exercise", "transport", "general")

#: Allowed Task.recurrence values.
RECURRENCE_VALUES = ("none", "daily", "weekly")

#: Allowed Task.category values (free text is accepted, these are the defaults).
CATEGORY_VALUES = ("med", "feeding", "bathing", "exercise", "transport", "general")


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------
def parse_iso(value: Any) -> datetime:
    """Parse an ISO-8601 string (or pass through a datetime) to *naive* UTC.

    Accepts a trailing ``Z`` (UTC) even on Python 3.10, where
    ``datetime.fromisoformat`` does not understand it. Aware datetimes are
    converted to UTC and then made naive so that comparisons never raise.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if not s:
            raise ValueError("empty datetime string")
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def format_iso(dt: datetime) -> str:
    """Render a naive datetime as a clean ISO-8601 string."""
    dt = dt.replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_time(hhmm: str) -> time:
    """Parse ``'HH:MM'`` into a :class:`datetime.time`."""
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(hhmm).strip())
    if not m:
        raise ValueError("time must be HH:MM, got %r" % (hhmm,))
    h, mm = int(m.group(1)), int(m.group(2))
    try:
        return time(hour=h, minute=mm)
    except ValueError:
        raise ValueError("invalid HH:MM time %r" % (hhmm,))


# ---------------------------------------------------------------------------
# Record (de)serialisation helpers
# ---------------------------------------------------------------------------
def as_record_dict(obj: Any) -> dict:
    """Flatten a dataclass record to a plain dict of its *declared* fields.

    Computed attributes (e.g. ``CareEvent.start_dt``) are not declared fields
    and are therefore excluded automatically.
    """
    out: dict = {}
    for f in fields(obj):
        out[f.name] = getattr(obj, f.name)
    return out


def from_record_dict(cls: Any, d: dict) -> Any:
    """Build a dataclass from a dict, ignoring unknown keys and filling defaults.

    Only declared fields are passed through, so audit-log records can carry an
    extra ``kind`` discriminator without breaking reconstruction.
    """
    valid = cls.__dataclass_fields__
    kwargs = {k: d[k] for k in valid if k in d}
    return cls(**kwargs)


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------
@dataclass
class Person:
    """A participant in the care network.

    ``role`` is restricted to :data:`ROLE_VALUES`; everything else is a label.
    No PII is required beyond a short ``id`` / ``name``.
    """
    id: str
    name: str
    role: str = "caregiver"

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Person.id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Person.name must be a non-empty string")
        role = self.role if self.role is not None else "caregiver"
        if role not in ROLE_VALUES:
            raise ValueError(
                "Person.role must be one of %s, got %r" % (ROLE_VALUES, self.role))
        self.role = role

    @classmethod
    def from_dict(cls, d: dict) -> "Person":
        return from_record_dict(cls, d)

    def to_dict(self) -> dict:
        return as_record_dict(self)


# ---------------------------------------------------------------------------
# CareEvent
# ---------------------------------------------------------------------------
@dataclass
class CareEvent:
    """A scheduled or logged block of care for one ``person_id`` by one caregiver.

    Times are stored as ISO-8601 strings and also parsed into ``start_dt`` /
    ``end_dt`` (naive UTC) in ``__post_init__`` for cheap comparison.
    """
    start: str
    end: str
    caregiver_id: str
    person_id: str
    type: str = "general"
    note: str = ""

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(
                "CareEvent.type must be one of %s, got %r" % (EVENT_TYPES, self.type))
        for who in ("caregiver_id", "person_id"):
            v = getattr(self, who)
            if not isinstance(v, str) or not v.strip():
                raise ValueError("CareEvent.%s must be a non-empty string" % who)
        self.start_dt = parse_iso(self.start)
        self.end_dt = parse_iso(self.end)
        if not isinstance(self.start_dt, datetime):
            raise ValueError("CareEvent.start is not a valid ISO-8601 time")
        if self.end_dt <= self.start_dt:
            raise ValueError(
                "CareEvent.end (%s) must be after start (%s)" % (self.end, self.start))

    @property
    def duration_minutes(self) -> int:
        return round((self.end_dt - self.start_dt).total_seconds() / 60.0)

    @classmethod
    def from_dict(cls, d: dict) -> "CareEvent":
        return from_record_dict(cls, d)

    def to_dict(self) -> dict:
        return as_record_dict(self)


# ---------------------------------------------------------------------------
# Task (reminder)
# ---------------------------------------------------------------------------
@dataclass
class Task:
    """A reminder / task, optionally recurring, optionally assigned.

    ``done`` is a boolean; ``recurrence`` is one of :data:`RECURRENCE_VALUES`;
    ``category`` defaults to ``general`` (e.g. ``med`` for medication reminders).
    """
    name: str
    due: str
    done: bool = False
    assignee_id: str | None = None
    recurrence: str = "none"
    category: str = "general"
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Task.name must be a non-empty string")
        if not isinstance(self.due, str) or not self.due.strip():
            raise ValueError("Task.due must be a non-empty ISO-8601 string")
        if self.recurrence not in RECURRENCE_VALUES:
            raise ValueError(
                "Task.recurrence must be one of %s, got %r"
                % (RECURRENCE_VALUES, self.recurrence))
        if self.done is None:
            self.done = False
        elif not isinstance(self.done, bool):
            raise ValueError("Task.done must be a bool")
        self.due_dt = parse_iso(self.due)

    @property
    def is_done(self) -> bool:
        return bool(self.done)

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return from_record_dict(cls, d)

    def to_dict(self) -> dict:
        return as_record_dict(self)


# ---------------------------------------------------------------------------
# ShiftHandoff
# ---------------------------------------------------------------------------
@dataclass
class ShiftHandoff:
    """A shift transfer between a finishing and an incoming caregiver.

    ``notes`` is a free-text slot; the richer, computed handoff text lives in
    :mod:`care_roster.handoff`.
    """
    from_caregiver: str
    to_caregiver: str
    person_id: str
    when: str
    notes: str = ""

    def __post_init__(self) -> None:
        for who in ("from_caregiver", "to_caregiver", "person_id"):
            v = getattr(self, who)
            if not isinstance(v, str) or not v.strip():
                raise ValueError("ShiftHandoff.%s must be a non-empty string" % who)
        self.when_dt = parse_iso(self.when)

    @classmethod
    def from_dict(cls, d: dict) -> "ShiftHandoff":
        return from_record_dict(cls, d)

    def to_dict(self) -> dict:
        return as_record_dict(self)
