# care-roster

Local-first, dependency-free coordination for a home-care team.

`care-roster` is a small, standard-library-only toolkit that helps a care team
make sure the right person is covered at the right time, spot double-bookings,
track overtime, and keep an auditable record of who cared for whom and when.

Everything here runs offline; nothing touches a clock or a network. Records
validate themselves, flatten to plain `dict` for the JSONL logs, and rehydrate
on read.

## Features

- **Records** — `Person`, `CareEvent`, `Task`, `ShiftHandoff` with self-
  validating fields (roles, event types, end-after-start).
- **Scheduling** — `Roster` groups events into a Monday-starting ISO week;
   `detect_overlaps` finds two shifts covering the same person or crowding the
  same caregiver.
- **Coverage** — a sweep-line `compute_coverage` / `ensure_coverage` reports the
   uncovered minutes per person and flags gaps over a threshold (default 30 min),
  with a `minimum_caregivers` floor.
- **Accountability** — `account_hours` tallies per-caregiver hours and flags
   overtime past a weekly cap (also importable as `care_roster.accounting`).
- **Audit store** — `Store` keeps append-only, replayable JSONL logs for events
  and tasks, plus point-in-time snapshots.

## Install

Requires Python 3.10 or newer; no third-party runtime dependencies.

```bash
pip install .
# optional: install the test extra
pip install -e .[test]
```

## Usage

```python
import care_roster as c

# Two caregivers, one patient, overlapping shifts.
e1 = c.CareEvent(start="2026-10-01T08:00:00", end="2026-10-01T12:00:00",
                 caregiver_id="cg1", person_id="p1", type="bathing")
e2 = c.CareEvent(start="2026-10-01T10:00:00", end="2026-10-01T14:00:00",
                 caregiver_id="cg2", person_id="p1", type="bathing")

# 08:00-20:00 window: who is uncovered for how long?
report = c.ensure_coverage([e1, e2], c.default_window())
print(report.total_minutes_uncovered, "minutes uncovered today")
print(report.flagged)

# Flag any caregiver over the weekly cap.
hours = c.account_hours([e1, e2, ...], weekly_cap_hours=40.0)
for name, info in hours.by_name.items():
    if info.overtime:
        print(name, "worked", info.overtime_hours, "overtime hours")

# Persist to an append-only, replayable audit log.
store = c.Store("./logs")
store.append_event(e1)
data = store.load()  # rehydrates the full history
```

## Design

- **Pure standard library** — `datetime`, `json`, `pathlib`, `dataclasses`. No
   third-party runtime dependency; the only extra is `pytest` under the `test`
   optional dependency.
- **No network, no wall clock** — all time comes in as ISO-8601 strings; pass an
   explicit period, never a live clock. Nothing here makes a socket call.
- **Self-validating records** — enums and `__post_init__` checks reject bad
   roles, event types, and end-before-start times at construction time.
- **Replayable audit** — the store is append-only: every append is a new JSONL
   line, so a fresh handle replays the complete history deterministically.
- **Tested** — deterministic unit tests under `tests/`; CI is a GitHub Actions
   matrix over Python 3.10 and 3.12 that installs in a clean venv and runs
   `compileall`, an import smoke test, and `pytest`.

## License

MIT — see [LICENSE](LICENSE).
