"""care_roster -- local-first coordination for a care team.

A small, dependency-free toolkit for rostering and auditing home-care shifts:

* :mod:`care_roster.models` -- the record types (``Person``, ``CareEvent``,
  ``Task``, ``ShiftHandoff``) and their ISO-8601 time helpers.
* :mod:`care_roster.roster` -- group events into a weekly :class:`Roster` and
  spot double-bookings (:func:`detect_overlaps`).
* :mod:`care_roster.coverage` -- sweep-line coverage-gap detection: which person
  is under-covered and for how long (:func:`compute_coverage`,
  :func:`ensure_coverage`).
* :mod:`care_roster.accountability` -- per-caregiver hour totals and overtime,
  also importable as :mod:`care_roster.accounting`.
* :mod:`care_roster.store` -- an append-only, replayable JSONL audit store
  (:class:`Store`).

Everything is standard-library only; nothing here touches the network or a
clock. Records validate themselves in ``__post_init__`` and flatten to / build
from plain ``dict`` for the JSONL logs.
"""
from __future__ import annotations

from .accountability import (
    DEFAULT_WEEKLY_CAP_HOURS,
    AccountabilityReport,
    CaregiverHours,
    account_hours,
    summarize_report,
)
from .coverage import (
    DEFAULT_THRESHOLD_MINUTES,
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    DEFAULT_WEEK_CAP_MINUTES,
    CoverageReport,
    Gap,
    Window,
    compute_coverage,
    default_window,
    ensure_coverage,
)
from .models import (
    CATEGORY_VALUES,
    EVENT_TYPES,
    RECURRENCE_VALUES,
    ROLE_VALUES,
    CareEvent,
    Person,
    ShiftHandoff,
    Task,
    as_record_dict,
    from_record_dict,
    format_iso,
    parse_iso,
    parse_time,
)
from .roster import (
    Overlap,
    Roster,
    build_weekly_roster,
    detect_overlaps,
    event_days,
    events_in_range,
    sort_events,
    week_range,
)
from .store import (
    EVENTS_FILENAME,
    SNAPSHOTS_DIR,
    TASKS_FILENAME,
    Store,
    StoreData,
    StoreError,
)

__all__ = [
    # accountability / accounting
    "CaregiverHours",
    "AccountabilityReport",
    "account_hours",
    "summarize_report",
    "DEFAULT_WEEKLY_CAP_HOURS",
    "DEFAULT_WEEK_CAP_HOURS",
    # coverage
    "Window",
    "default_window",
    "Gap",
    "CoverageReport",
    "compute_coverage",
    "ensure_coverage",
    "DEFAULT_THRESHOLD_MINUTES",
    "DEFAULT_WINDOW_START",
    "DEFAULT_WINDOW_END",
    "DEFAULT_WEEK_CAP_MINUTES",
    # models
    "parse_iso",
    "format_iso",
    "parse_time",
    "as_record_dict",
    "from_record_dict",
    "Person",
    "CareEvent",
    "Task",
    "ShiftHandoff",
    "ROLE_VALUES",
    "EVENT_TYPES",
    "RECURRENCE_VALUES",
    "CATEGORY_VALUES",
    # roster
    "Overlap",
    "Roster",
    "sort_events",
    "event_days",
    "week_range",
    "events_in_range",
    "detect_overlaps",
    "build_weekly_roster",
    # store
    "Store",
    "StoreData",
    "StoreError",
    "EVENTS_FILENAME",
    "TASKS_FILENAME",
    "SNAPSHOTS_DIR",
]

__version__ = "1.0.0"

# Backward-compatible alias from the historical "accounting" name.
from .accounting import DEFAULT_WEEK_CAP_HOURS  # noqa: E402,F401
