"""
Reproduce the BOT's threading model: read each account via asyncio.to_thread
(pool thread), exactly like the live watchdog does. This is where winsdk OCR was
hanging without COM init. Run ELEVATED:

    .venv\\Scripts\\python.exe scripts\\wd_thread_test.py LingMe HieuTrai OldMidas Minnyat
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whalebots_automation.services.watchdog_reader import read_account_log  # noqa: E402


async def main(names):
    for n in names:
        t0 = time.time()
        r = await asyncio.to_thread(read_account_log, n)
        dt = time.time() - t0
        print(f"{n:<12} ok={r.ok}  ts={r.latest_ts}  ({dt:.1f}s)  err={r.error}")


names = sys.argv[1:]
if not names:
    print("usage: wd_thread_test.py <account> [<account> ...]")
    sys.exit(1)
asyncio.run(main(names))
