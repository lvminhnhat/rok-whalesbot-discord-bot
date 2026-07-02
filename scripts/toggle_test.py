"""
End-to-end test of the name-anchored start/stop click path.

Stops the given account (real checkbox click, located by name), waits, then
starts it again - exercising exactly the code path the Discord bot uses
(WhaleBots.stop/start -> _click_account_row -> click_account_checkbox).
Run ELEVATED:

    .venv\\Scripts\\python.exe scripts\\toggle_test.py --account KRFillers
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whalebots_automation.whalesbot import WhaleBots  # noqa: E402

WHALEBOTS_PATH = r"C:\Program Files (x86)\Whalebots"

ap = argparse.ArgumentParser()
ap.add_argument("--account", required=True)
ap.add_argument("--settle", type=float, default=15.0,
                help="seconds to wait between stop and start")
args = ap.parse_args()

wb = WhaleBots(WHALEBOTS_PATH)
states = wb.state_manager.get_emulator_states()
target = next((s for s in states if s.emulator_info.name == args.account), None)
if target is None:
    print(f"account '{args.account}' not found in Accounts.json")
    sys.exit(1)
print(f"target: {target.emulator_info.name} (index {target.index}), "
      f"active={target.is_active}")

if not target.is_active:
    print("account is not running - doing START then STOP instead")
    first, second = wb.start, wb.stop
else:
    first, second = wb.stop, wb.start

t0 = time.time()
print(f"\n--- {first.__name__.upper()} {args.account} ---")
first(target.index)
print(f"{first.__name__} completed in {time.time() - t0:.1f}s")

print(f"waiting {args.settle:.0f}s ...")
time.sleep(args.settle)

t0 = time.time()
print(f"\n--- {second.__name__.upper()} {args.account} ---")
second(target.index)
print(f"{second.__name__} completed in {time.time() - t0:.1f}s")

state = wb.state_manager.get_emulator_state_by_index(target.index)
print(f"\nfinal state: active={state.is_active} (expected {target.is_active})")
print("TOGGLE_TEST_DONE")
