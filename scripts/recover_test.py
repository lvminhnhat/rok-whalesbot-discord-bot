"""
End-to-end test of the auto-recovery cycle on one account:
  1. close its emulator via the right-click context menu (verified 'Close')
  2. wait for the emulator to shut down
  3. restart it with the direction-safe checkbox click (ensure='checked')
  4. poll until the checkbox reads ticked again

Run ELEVATED:

    .venv\\Scripts\\python.exe scripts\\recover_test.py --account BinhCuuHoa
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whalebots_automation.services.watchdog_reader import (  # noqa: E402
    close_account_via_menu, click_account_checkbox,
)

ACCOUNTS_JSON = (r"C:\Program Files (x86)\Whalebots\Apps\rise-of-kingdoms-bot"
                 r"\Settings\Accounts.json")

ap = argparse.ArgumentParser()
ap.add_argument("--account", required=True)
ap.add_argument("--settle", type=float, default=30.0,
                help="seconds to wait between close and restart")
args = ap.parse_args()

roster = []
try:
    data = json.loads(open(ACCOUNTS_JSON, encoding="utf-8-sig").read())
    roster = [a.get("emuInfo", {}).get("name", "") for a in data if a.get("emuInfo", {}).get("name")]
except Exception as e:
    print(f"(roster unavailable: {e})")

t0 = time.time()
print(f"--- CLOSE {args.account} via context menu ---")
res = close_account_via_menu(args.account, roster=roster)
print(f"close: success={res['success']} matched='{res['matched_text']}' "
      f"closed_confirmed={res['closed_confirmed']}")
if res.get("warning"):
    print(f"WARNING: {res['warning']}")
if not res["success"]:
    print(f"ABORTED: {res['error']}")
    sys.exit(1)
print(f"(close phase took {time.time() - t0:.1f}s)")

print(f"waiting {args.settle:.0f}s for the emulator to fully shut down ...")
time.sleep(args.settle)

t0 = time.time()
print(f"--- RESTART {args.account} via checkbox ---")
r2 = click_account_checkbox(args.account, roster=roster, ensure="checked")
print(f"start: success={r2['success']} noop={r2.get('noop')} "
      f"checkbox={r2.get('checkbox')} clicked_at={r2.get('clicked_at')}")
if not r2["success"]:
    print(f"RESTART FAILED: {r2['error']}")
    sys.exit(1)

# poll until ticked (the click itself is verified, this is belt-and-braces)
for i in range(6):
    time.sleep(5)
    chk = click_account_checkbox(args.account, roster=roster, dry_run=True)
    print(f"  poll {i+1}: checkbox={chk.get('checkbox')}")
    if chk.get("checkbox") is True:
        print("RECOVERY_TEST_DONE: instance is ticked/running again")
        sys.exit(0)
print("RECOVERY_TEST_DONE: restart clicked but checkbox not confirmed ticked - check GUI")
