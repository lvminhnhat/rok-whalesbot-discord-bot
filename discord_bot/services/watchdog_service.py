"""
watchdog_service.py - per-account freeze detection for ROKBot instances.

Pure logic (no Discord) so it can be unit-tested. It drives
whalebots_automation.services.watchdog_reader to read each running account's
ACTIVITY LOG, then decides whether an instance is frozen:

  * STALE  - the latest log timestamp hasn't advanced for STALE_SECONDS of
             wall-clock time (the account stopped doing anything new).
  * BAD    - recent log lines stay in a bad state (Disconnected / OFFLINE /
             Preparing / Game is loading / ...) across several sweeps - i.e.
             a crash/reconnect loop where timestamps move but nothing useful
             happens.

We compare the in-game *timestamp* (not the full line) across sweeps because
it is the stable progress signal, and we measure staleness against WALL-CLOCK
(not in-game time) so midnight wrap / date ambiguity is irrelevant.

sweep() returns a list of WatchEvent for the caller (bot.py) to deliver to
Discord. Alerts are debounced: one "frozen" per episode, periodic
"still_frozen" reminders, and a "recovered" when it resumes.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from whalebots_automation.services.watchdog_reader import (
    ROKWindow,
    LogReading,
    read_account_log,
)

# Default tunables (seconds). Overridable per-deployment via env (read at
# runtime in WatchdogService.__init__, since .env loads after import).
# STALE_SECONDS at 30 min (was 15): with 20-min sweeps a single corrupted
# read that makes the log look ~20 min old could alert on its own (the
# Piltong1 false alert); 30 min means one misread can't clear the bar alone
# while a real freeze is still caught on the first or second sweep after it.
STALE_SECONDS = 30 * 60       # no new log timestamp for this long -> frozen
BAD_STATE_SWEEPS = 3          # consecutive bad-state sweeps -> frozen (loop)
REALERT_SECONDS = 60 * 60     # re-remind about a still-frozen instance this often
READ_FAIL_GRACE = 4           # consecutive unreadable sweeps before we surface it


@dataclass
class AccountState:
    name: str
    last_ts: Optional[str] = None      # last seen in-game "HH:MM:SS"
    last_change: float = 0.0           # wall-clock when last_ts last advanced
    consecutive_bad: int = 0
    consecutive_fail: int = 0
    frozen: bool = False
    last_alert: float = 0.0
    reason: str = ""


@dataclass
class WatchEvent:
    name: str
    kind: str                          # "frozen" | "still_frozen" | "recovered" | "unreadable"
    reason: str
    latest_ts: Optional[str] = None
    recent_lines: List[str] = field(default_factory=list)


def _ts_key(ts: Optional[str]):
    if not ts:
        return None
    try:
        h, m, s = (int(x) for x in ts.split(":"))
        return (h, m, s)
    except Exception:
        return None


def _log_age_seconds(ts: Optional[str], now: float) -> Optional[float]:
    """Age of an in-game "HH:MM:SS" log timestamp vs LOCAL wall-clock, or None
    if unparsable.

    The log clock matches local time, so the timestamp's own age flags a
    frozen instance IMMEDIATELY - the last_change-based tracking below only
    detects staleness that develops while the bot is running, so right after
    a restart an instance that froze an hour ago would look fresh for another
    STALE_SECONDS. Midnight wrap is handled modulo 24h; a timestamp slightly
    AHEAD of the clock (skew) maps to ~24h, which we clamp to fresh."""
    k = _ts_key(ts)
    if k is None:
        return None
    lt = time.localtime(now)
    now_sod = lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec
    ts_sod = k[0] * 3600 + k[1] * 60 + k[2]
    age = (now_sod - ts_sod) % 86400
    if age > 86400 - 600:   # "in the future" by <10 min = clock skew -> fresh
        return 0.0
    return float(age)


class WatchdogService:
    def __init__(self, now_fn: Callable[[], float] = time.time):
        self.states: Dict[str, AccountState] = {}
        self._now = now_fn
        # Read thresholds at runtime so .env overrides apply (handy for testing).
        self.stale_seconds = int(os.getenv("WATCHDOG_STALE_SECONDS", str(STALE_SECONDS)))
        self.bad_sweeps = int(os.getenv("WATCHDOG_BAD_SWEEPS", str(BAD_STATE_SWEEPS)))
        self.realert_seconds = int(os.getenv("WATCHDOG_REALERT_SECONDS", str(REALERT_SECONDS)))
        self.read_fail_grace = int(os.getenv("WATCHDOG_READ_FAIL_GRACE", str(READ_FAIL_GRACE)))

    def reset(self, name: str) -> None:
        self.states.pop(name, None)

    def process_reading(self, name: str, reading: LogReading) -> Optional[WatchEvent]:
        """Feed one account's LogReading into the state machine and return any
        state-change event. This is the unit the live bot drives: it queues each
        account read through the UIOperationQueue (so reads serialize with
        start/stop) and then calls this with the result.
        """
        st = self.states.get(name)
        if st is None:
            st = AccountState(name=name, last_change=self._now())
            self.states[name] = st
        return self._update(st, reading)

    def sweep(self, account_names: List[str]) -> List[WatchEvent]:
        """Synchronous sweep - reads each account (each prepares+restores its own
        window) and updates state. Used by scripts/wd_sweep_test.py. The live bot
        uses the queue-driven path in bot.py so reads serialize with start/stop.
        """
        events: List[WatchEvent] = []
        for name in account_names:
            ev = self.process_reading(name, read_account_log(name))
            if ev:
                events.append(ev)
        return events

    def _update(self, st: AccountState, r: LogReading) -> Optional[WatchEvent]:
        now = self._now()

        # GUI checkbox says the instance is not running at all: nothing to
        # watch (the caller syncs the drifted state file); forget its history
        # so a later start begins with a clean slate.
        if getattr(r, "running", None) is False:
            self.reset(st.name)
            return None

        if not r.ok:
            st.consecutive_fail += 1
            # Transient read failures don't flip freeze state; surface once if persistent.
            if st.consecutive_fail == self.read_fail_grace:
                return WatchEvent(st.name, "unreadable",
                                  r.error or "could not read activity log",
                                  recent_lines=[])
            return None
        st.consecutive_fail = 0

        # progress = latest in-game timestamp advanced since last sweep
        new_key = _ts_key(r.latest_ts)
        old_key = _ts_key(st.last_ts)
        if new_key is not None and new_key != old_key:
            st.last_ts = r.latest_ts
            st.last_change = now

        # Staleness is the WORSE of two signals: how long WE have watched the
        # timestamp not advance, and how old the log timestamp itself is (the
        # latter catches instances that froze before the bot (re)started).
        stale = now - st.last_change
        log_age = _log_age_seconds(r.latest_ts, now)
        if log_age is not None:
            stale = max(stale, log_age)
        st.consecutive_bad = (st.consecutive_bad + 1) if r.bad_states else 0

        reason = ""
        if stale >= self.stale_seconds:
            reason = f"no new activity for {int(stale // 60)} min (last log {r.latest_ts})"
        elif st.consecutive_bad >= self.bad_sweeps:
            reason = f"stuck in bad state: {', '.join(r.bad_states)} (last log {r.latest_ts})"

        frozen = bool(reason)
        st.reason = reason

        if frozen and not st.frozen:
            st.frozen = True
            st.last_alert = now
            return WatchEvent(st.name, "frozen", reason, r.latest_ts, r.lines[-5:])
        if frozen and st.frozen and (now - st.last_alert) >= self.realert_seconds:
            st.last_alert = now
            return WatchEvent(st.name, "still_frozen", reason, r.latest_ts, r.lines[-5:])
        if not frozen and st.frozen:
            st.frozen = False
            return WatchEvent(st.name, "recovered", "activity resumed", r.latest_ts, r.lines[-5:])
        return None
