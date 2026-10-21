"""Caregiver-hours accounting (alias of :mod:`care_roster.accountability`).

Some users refer to this as "accounting"; import from here or from
``accountability`` -- they are the same module.
"""
from __future__ import annotations

from .accountability import (
    CaregiverHours,
    AccountabilityReport,
    account_hours,
    summarize_report,
    DEFAULT_WEEKLY_CAP_HOURS,
)

# ``accounting`` exposes the same names.
__all__ = [
    "CaregiverHours",
    "AccountabilityReport",
    "account_hours",
    "summarize_report",
    "DEFAULT_WEEKLY_CAP_HOURS",
    "DEFAULT_WEEK_CAP_HOURS",
]


# A backward-compatible alias name.
DEFAULT_WEEK_CAP_HOURS = DEFAULT_WEEKLY_CAP_HOURS
