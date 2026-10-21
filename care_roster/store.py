"""Append-only JSONL audit store + lightweight JSON snapshots.

A :class:`Store` lives in a directory and keeps two append-only JSONL logs --
``events.jsonl`` and ``tasks.jsonl`` -- plus a ``snapshots/`` directory for
computed, regenerated state (rosters, coverage reports). The audit logs are
never truncated in place: appends are the only mutation, which makes the store a
genuine, replayable history.

Everything is stdlib ``json`` only. The store path comes from an explicit user
flag (``--store``); the module never opens a path it was not handed.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .models import CareEvent, Task, from_record_dict


EVENTS_FILENAME = "events.jsonl"
TASKS_FILENAME = "tasks.jsonl"
SNAPSHOTS_DIR = "snapshots"


class StoreError(Exception):
    """Raised for malformed or unreadable store state."""


@dataclass
class StoreData:
    """A materialised view of a store: everything that was ever appended."""

    events: list = field(default_factory=list)
    tasks: list = field(default_factory=list)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _append_line(path: str, record: dict) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        _ensure_dir(parent)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True))
        f.write("\n")


def _read_jsonl(path: str) -> list:
    out: list = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, TypeError) as e:
                raise StoreError(
                    "corrupt %s:%d: %s" % (os.path.basename(path), lineno, e)) from e
            if not isinstance(obj, dict):
                raise StoreError(
                    "corrupt %s:%d: expected a JSON object"
                    % (os.path.basename(path), lineno))
            out.append(obj)
    return out


def _load_records(path: str, cls) -> list:
    records = []
    for d in _read_jsonl(path):
        clean = {k: v for k, v in d.items() if k != "kind"}
        records.append(from_record_dict(cls, clean))
    return records


class Store:
    """JSONL append-only store rooted at a directory.

    Parameters
    ----------
    path:
        Directory holding ``events.jsonl``, ``tasks.jsonl`` and a
        ``snapshots/`` subdirectory. Created on first use.
    """

    events_filename = EVENTS_FILENAME
    tasks_filename = TASKS_FILENAME

    def __init__(self, path: str) -> None:
        self.dir = path
        _ensure_dir(path)
        self.events_path = os.path.join(path, self.events_filename)
        self.tasks_path = os.path.join(path, self.tasks_filename)
        self.snapshots_dir = os.path.join(path, SNAPSHOTS_DIR)

    # -- appends (audit trail) --------------------------------------------
    def append_event(self, event: CareEvent) -> None:
        _append_line(self.events_path, {"kind": "event", **event.to_dict()})

    def append_task(self, task: Task) -> None:
        _append_line(self.tasks_path, {"kind": "task", **task.to_dict()})

    def append_events(self, events: list) -> int:
        for e in events:
            self.append_event(e)
        return len(events)

    def append_tasks(self, tasks: list) -> int:
        for t in tasks:
            self.append_task(t)
        return len(tasks)

    # -- loads (replay the log) -------------------------------------------
    def load_events(self) -> list:
        return _load_records(self.events_path, CareEvent)

    def load_tasks(self) -> list:
        return _load_records(self.tasks_path, Task)

    def load(self) -> StoreData:
        return StoreData(events=self.load_events(), tasks=self.load_tasks())

    # -- snapshots (regenerated, disposable) ------------------------------
    def save_snapshot(self, name: str, obj) -> str:
        _ensure_dir(self.snapshots_dir)
        target = os.path.join(self.snapshots_dir, name)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")
        return target

    def load_snapshot(self, name: str):
        target = os.path.join(self.snapshots_dir, name)
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
