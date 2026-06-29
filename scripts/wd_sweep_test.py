"""
Manual test: run ONE watchdog sweep over the given accounts and print results.
Run ELEVATED:
    .venv\\Scripts\\python.exe scripts\\wd_sweep_test.py LingMe HieuTrai Minnyat

(First sweep won't report 'frozen' - nothing is stale yet - it just proves each
account is selected and its latest log timestamp is read.)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from discord_bot.services.watchdog_service import WatchdogService  # noqa: E402

names = sys.argv[1:]
if not names:
    print("usage: wd_sweep_test.py <account> [<account> ...]")
    sys.exit(1)

svc = WatchdogService()
print("sweeping:", names)
events = svc.sweep(names)

print("---- events ----")
for ev in events:
    print(f"  {ev.kind}: {ev.name} - {ev.reason} (last {ev.latest_ts})")
if not events:
    print("  (none - expected on a first sweep)")

print("---- per-account state ----")
for n, s in svc.states.items():
    print(f"  {n}: last_ts={s.last_ts}  frozen={s.frozen}  fails={s.consecutive_fail}")
