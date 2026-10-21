"""Tests for the care_roster package.

Pure standard-library, deterministic: no network, no wall clock.
"""
from __future__ import annotations

import os
import tempfile

import care_roster as c


# --- time helpers ---------------------------------------------------------------

def test_parse_iso_accepts_trailing_z():
    dt = c.parse_iso("2026-10-01T08:00:00Z")
    assert dt.hour == 8 and dt.tzinfo is None  # made naive UTC


def test_parse_iso_makes_aware_naive():
    import datetime
    dt = c.parse_iso("2026-10-01T12:00:00+02:00")
    assert dt.hour == 10  # 12:00 +02:00 == 10:00 UTC


def test_parse_time_and_format_iso():
    assert c.parse_time("08:30").hour == 8 and c.parse_time("08:30").minute == 30
    import datetime
    assert c.format_iso(datetime.datetime(2026, 10, 1, 8, 0, 0)) == "2026-10-01T08:00:00"


# --- model validation -----------------------------------------------------------

def test_person_rejects_bad_role():
    import pytest
    with pytest.raises(ValueError):
        c.Person(id="p1", name="Pat", role="wizard")


def test_care_event_requires_end_after_start():
    import pytest
    with pytest.raises(ValueError):
        c.CareEvent(start="2026-10-01T10:00:00", end="2026-10-01T09:00:00",
                    caregiver_id="cg", person_id="p1")


def test_care_event_rejects_bad_type():
    import pytest
    with pytest.raises(ValueError):
        c.CareEvent(start="2026-10-01T08:00:00", end="2026-10-01T09:00:00",
                    caregiver_id="cg", person_id="p1", type="teleport")


def test_care_event_duration():
    e = c.CareEvent(start="2026-10-01T08:00:00", end="2026-10-01T12:00:00",
                    caregiver_id="cg", person_id="p1")
    assert e.duration_minutes == 240


def test_task_validation_and_default():
    t = c.Task(name="meds", due="2026-10-02T09:00:00")
    assert t.category == "general" and t.recurrence == "none" and t.is_done is False
    t.done = True
    assert t.is_done is True


def test_shift_handoff_requires_caregivers():
    import pytest
    with pytest.raises(ValueError):
        c.ShiftHandoff(from_caregiver="", to_caregiver="cg",
                       person_id="p1", when="2026-10-01T08:00:00")


# --- coverage -------------------------------------------------------------------

def _two_shifts():
    return [
        c.CareEvent(start="2026-10-01T08:00:00", end="2026-10-01T12:00:00",
                    caregiver_id="cg1", person_id="p1", type="bathing"),
        c.CareEvent(start="2026-10-01T10:00:00", end="2026-10-01T14:00:00",
                    caregiver_id="cg2", person_id="p1", type="bathing"),
    ]


def test_coverage_gap_detected():
    rep = c.ensure_coverage(_two_shifts(), c.default_window())
    # 08:00-20:00 window, covered 08:00-14:00 -> 14:00-20:00 = 360 min gap
    assert rep.total_minutes_uncovered == 360
    assert len(rep.flagged) == 1
    assert rep.flagged[0].is_flagged is True


def test_coverage_complete_when_filled():
    evs = _two_shifts() + [
        c.CareEvent(start="2026-10-01T14:00:00", end="2026-10-01T20:00:00",
                    caregiver_id="cg3", person_id="p1", type="general"),
    ]
    rep = c.ensure_coverage(evs, c.default_window())
    assert rep.is_complete is True and rep.total_minutes_uncovered == 0


def test_coverage_threshold_flagging():
    # A 15-minute gap should NOT be flagged at the default 30-minute threshold
    evs = [
        c.CareEvent(start="2026-10-01T08:00:00", end="2026-10-01T19:45:00",
                    caregiver_id="cg", person_id="p1", type="general"),
    ]
    rep = c.ensure_coverage(evs, c.default_window())
    assert rep.total_minutes_uncovered == 15
    assert rep.flagged == []


def test_coverage_min_caregivers_two():
    # Two people needed, only one present -> the whole window is under-covered
    evs = [c.CareEvent(start="2026-10-01T08:00:00", end="2026-10-01T20:00:00",
                        caregiver_id="cg", person_id="p1", type="general")]
    rep = c.ensure_coverage(evs, c.default_window(), minimum_caregivers=2)
    assert rep.total_minutes_uncovered == 720  # full 12h window


def test_compute_coverage_rejects_bad_minimum():
    import pytest
    with pytest.raises(ValueError):
        c.compute_coverage({}, [], "2026-10-01T00:00:00", "2026-10-01T01:00:00",
                            minimum_caregivers=0)


# --- accountability / overtime --------------------------------------------------

def test_overtime_under_cap():
    evs = [c.CareEvent(start="2026-10-01T08:00:00", end="2026-10-01T12:00:00",
                        caregiver_id="cg", person_id="p1")]
    rep = c.account_hours(evs, weekly_cap_hours=40.0)
    cg = rep.caregiver("cg")
    assert cg.total_hours == 4.0 and cg.overtime is False and cg.overtime_minutes == 0


def test_overtime_over_cap():
    evs = [
        c.CareEvent(start="2026-10-01T00:00:00", end="2026-10-02T00:00:00",
                    caregiver_id="cg", person_id="p1", type="general"),
        c.CareEvent(start="2026-10-02T00:00:00", end="2026-10-02T18:00:00",
                    caregiver_id="cg", person_id="p1", type="general"),
    ]
    rep = c.account_hours(evs, weekly_cap_hours=40.0)
    cg = rep.caregiver("cg")
    assert cg.total_hours == 42.0
    assert cg.overtime_minutes == 120 and cg.overtime is True


def test_accounting_alias_module():
    import care_roster.accounting as acc
    assert acc.DEFAULT_WEEK_CAP_HOURS == c.DEFAULT_WEEKLY_CAP_HOURS


def test_summarize_report_is_text():
    rep = c.account_hours([c.CareEvent(start="2026-10-01T08:00:00",
                                       end="2026-10-01T12:00:00",
                                       caregiver_id="cg", person_id="p1")], 40.0)
    out = c.summarize_report(rep)
    assert "Caregiver hours" in out and "Total:" in out


# --- roster / overlaps / weeks --------------------------------------------------

def test_detect_overlaps_person():
    ov = c.detect_overlaps(_two_shifts(), by="person")
    assert len(ov) == 1 and ov[0].overlap_minutes == 120


def test_detect_overlaps_caregiver_disjoint():
    # Two events, same caregiver but non-overlapping -> no overlap
    evs = [
        c.CareEvent(start="2026-10-01T08:00:00", end="2026-10-01T09:00:00",
                    caregiver_id="cg", person_id="p1", type="general"),
        c.CareEvent(start="2026-10-01T10:00:00", end="2026-10-01T11:00:00",
                    caregiver_id="cg", person_id="p2", type="general"),
    ]
    assert c.detect_overlaps(evs, by="caregiver") == []


def test_week_range_is_monday_start():
    start, end = c.week_range("2026-W42")
    assert start.weekday() == 0       # Monday
    assert (end - start).days == 7
    assert end.month == 10 and end.day == 19  # 2026-W42 is 2026-10-12..10-18


def test_build_weekly_roster_groups():
    evs = _two_shifts() + [
        c.CareEvent(start="2026-10-01T08:00:00", end="2026-10-01T08:30:00",
                    caregiver_id="cg1", person_id="p2", type="meds"),
    ]
    roster = c.build_weekly_roster(evs, week="2026-W40")
    days = roster.days()
    text = roster.render()
    assert isinstance(text, str) and len(text) > 0
    assert len(roster.events) == 3


# --- store ----------------------------------------------------------------------

def test_store_roundtrip_and_snapshot():
    with tempfile.TemporaryDirectory() as d:
        st = c.Store(d)
        ev = c.CareEvent(start="2026-10-01T08:00:00", end="2026-10-01T09:00:00",
                         caregiver_id="cg", person_id="p1")
        st.append_event(ev)
        st.append_task(c.Task(name="meds", due="2026-10-02T09:00:00", category="med"))

        data = st.load()
        assert len(data.events) == 1 and len(data.tasks) == 1
        assert isinstance(data.events[0], c.CareEvent)
        assert data.tasks[0].name == "meds"

        target = st.save_snapshot("week", {"ok": True})
        assert os.path.exists(target)
        assert st.load_snapshot("week") == {"ok": True}


def test_store_is_append_only_replayable():
    with tempfile.TemporaryDirectory() as d:
        st = c.Store(d)
        for i in range(3):
            st.append_event(c.CareEvent(start=f"2026-10-01T0{i}:00:00",
                                        end=f"2026-10-01T0{i+1}:00:00",
                                        caregiver_id="cg", person_id="p1"))
        # A fresh handle replays the full append-only log
        assert len(c.Store(d).load_events()) == 3


def test_store_rejects_corrupt_log():
    with tempfile.TemporaryDirectory() as d:
        st = c.Store(d)
        with open(st.events_path, "a", encoding="utf-8") as f:
            f.write("{ this is not json\n")
        import pytest
        with pytest.raises(c.StoreError):
            st.load_events()
