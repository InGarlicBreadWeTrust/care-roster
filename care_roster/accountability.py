"""Caregiver-hours accounting.

Sums how long each caregiver worked over a period, produces a per-caregiver
summary, and flags overtime against a configurable weekly cap. The "hours"
concept maps onto care coverage: an event's length is its contribution to a
caregiver's account.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import parse_iso

DEFAULT_WEEKLY_CAP_HOURS = 40.0


@dataclass
class CaregiverHours:
    """Total care hours attributed to a single caregiver."""
    caregiver_id: str
    total_minutes: int = 0
    event_count: int = 0
    overtime_minutes: int = 0
    overtime: bool = False

    @property
    def total_hours(self) -> float:
        return round(self.total_minutes / 60.0, 2)

    @property
    def overtime_hours(self) -> float:
        return round(self.overtime_minutes / 60.0, 2)

    def as_dict(self) -> dict:
        """A JSON-ready flat view of these totals."""
        return {
            "caregiver_id": self.caregiver_id,
            "total_hours": self.total_hours,
            "total_minutes": self.total_minutes,
            "event_count": self.event_count,
            "overtime_minutes": self.overtime_minutes,
            "overtime": self.overtime,
        }


@dataclass
class AccountabilityReport:
    """Per-caregiver hour totals with an aggregated overtime view."""
    per_caregiver: list = field(default_factory=list)
    weekly_cap_hours: float = DEFAULT_WEEKLY_CAP_HOURS
    total_minutes: int = 0

    @property
    def total_hours(self) -> float:
        return round(self.total_minutes / 60.0, 2)

    def caregiver(self, caregiver_id: str):
        """The :class:`CaregiverHours` for one caregiver, or None if absent."""
        for c in self.per_caregiver:
            if c.caregiver_id == caregiver_id:
                return c
        return None


def account_hours(events, weekly_cap_hours: float = DEFAULT_WEEKLY_CAP_HOURS,
                  start=None, end=None):
    """Account care hours per caregiver over a period.

    Events outside [start, end) are ignored when a range is given.
    Overtime is any caregiver total beyond ``weekly_cap_hours``.
    """

    events = list(events)
    if start is not None:
        lo = parse_iso(start) if isinstance(start, str) else start
        events = [e for e in events if e.start_dt >= lo]
    if end is not None:
        hi = parse_iso(end) if isinstance(end, str) else end
        events = [e for e in events if e.start_dt < hi]

    cap_minutes = int(round(weekly_cap_hours * 60))
    totals = {}
    for e in sorted(events, key=lambda x: (x.start_dt, x.caregiver_id)):
        cid = e.caregiver_id or "(unassigned)"
        t = totals.get(cid)
        if t is None:
            t = CaregiverHours(caregiver_id=cid)
            totals[cid] = t
        t.total_minutes += e.duration_minutes
        t.event_count += 1

    report_total = 0
    for cid in sorted(totals):
        t = totals[cid]
        if t.total_minutes > cap_minutes:
            t.overtime_minutes = t.total_minutes - cap_minutes
            t.overtime = True
        report_total += t.total_minutes

    per = [totals[cid] for cid in sorted(totals)]
    return AccountabilityReport(per_caregiver=per,
                                weekly_cap_hours=weekly_cap_hours,
                                total_minutes=report_total)


def summarize_report(report: AccountabilityReport, people: dict = None) -> str:
    """A short human-readable hours summary, including overtime figures."""
    lines = ["Caregiver hours", "==============="]
    for c in report.per_caregiver:
        who = people.get(c.caregiver_id) if people else None
        who = who.name if who else c.caregiver_id or "(unassigned)"
        suffix = "    (overtime +%.2f h)" % c.overtime_hours if c.overtime else ""
        lines.append("    %s ... %s h%s" % (who, c.total_hours, suffix))
    lines.append("Total: %.2f h (overtime cap %.1f h)"
                 % (report.total_hours, report.weekly_cap_hours))
    return "\n".join(lines) + "\n"
