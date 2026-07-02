"""
schedule_service.py - persistent one-shot schedules for start/stop commands.

Users can defer a start/stop to a UTC wall-clock time, e.g.:
    start MinHe 13:00      -> start MinHe at the next 13:00 UTC
    stop all 14:30         -> stop all the user's emulators at 14:30 UTC

Jobs are persisted to data/schedules.json so they survive a bot restart or an
auto-update (the updater preserves data/). The bot polls due jobs on a
tasks.loop and executes them through the same queued start/stop path as manual
commands.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pytz

# Accepts H:MM or HH:MM, 24-hour (00:00-23:59).
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def parse_hhmm_to_next_utc(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Parse 'HH:MM' as a UTC wall-clock time and return the NEXT occurrence
    (today if still in the future, otherwise tomorrow). None if not a time."""
    m = TIME_RE.match(text.strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    now = now or datetime.now(pytz.UTC)
    cand = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cand <= now:
        cand += timedelta(days=1)
    return cand


@dataclass
class ScheduledJob:
    id: str
    user_id: str
    user_name: str
    channel_id: int
    action: str                 # 'start' | 'stop'
    target: Optional[str]       # emulator name, 'all', or None (user's default/first)
    when_utc: str               # ISO 8601, UTC
    created_at: str

    @property
    def when_dt(self) -> datetime:
        dt = datetime.fromisoformat(self.when_utc)
        return dt if dt.tzinfo else pytz.UTC.localize(dt)

    def describe_target(self) -> str:
        if self.target == "all":
            return "all emulators"
        return self.target or "your emulator"


class ScheduleService:
    """Persistent store of one-shot scheduled start/stop jobs.

    Single-event-loop access (Discord bot), so no locking is needed; writes are
    atomic (os.replace) so a crash mid-write can't corrupt the file."""

    def __init__(self, data_dir: str = "data", filename: str = "schedules.json"):
        self.path = Path(data_dir) / filename
        self._jobs: List[ScheduledJob] = self._load()

    def _load(self) -> List[ScheduledJob]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except Exception as e:
            print(f"[SCHEDULE] could not read {self.path}: {e} - starting empty")
            return []
        jobs = []
        for item in raw:
            try:
                jobs.append(ScheduledJob(**item))
            except Exception:
                continue
        return jobs

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps([asdict(j) for j in self._jobs], indent=2),
                           encoding="utf-8")
            os.replace(tmp, self.path)
        except Exception as e:
            print(f"[SCHEDULE] failed to save {self.path}: {e}")

    def add(self, user_id: str, user_name: str, channel_id: int, action: str,
            target: Optional[str], when_utc: datetime) -> ScheduledJob:
        job = ScheduledJob(
            id=uuid.uuid4().hex[:6],
            user_id=user_id,
            user_name=user_name,
            channel_id=int(channel_id),
            action=action,
            target=target,
            when_utc=when_utc.astimezone(pytz.UTC).isoformat(),
            created_at=datetime.now(pytz.UTC).isoformat(),
        )
        self._jobs.append(job)
        self._save()
        return job

    def for_user(self, user_id: str) -> List[ScheduledJob]:
        return sorted((j for j in self._jobs if j.user_id == user_id),
                      key=lambda j: j.when_dt)

    def all_jobs(self) -> List[ScheduledJob]:
        return sorted(self._jobs, key=lambda j: j.when_dt)

    def remove(self, job_id: str, user_id: Optional[str] = None) -> bool:
        """Remove a job by id. If user_id is given, only removes it when it
        belongs to that user (so one user can't cancel another's schedule)."""
        before = len(self._jobs)
        self._jobs = [j for j in self._jobs
                      if not (j.id == job_id and (user_id is None or j.user_id == user_id))]
        changed = len(self._jobs) != before
        if changed:
            self._save()
        return changed

    def pop_due(self, now: Optional[datetime] = None) -> List[ScheduledJob]:
        """Return and REMOVE every job whose time has arrived (<= now). Removing
        as we hand them out guarantees each fires exactly once."""
        now = now or datetime.now(pytz.UTC)
        due = [j for j in self._jobs if j.when_dt <= now]
        if due:
            due_ids = {j.id for j in due}
            self._jobs = [j for j in self._jobs if j.id not in due_ids]
            self._save()
        return sorted(due, key=lambda j: j.when_dt)
