"""Live test of the REAL recovery orchestration (_recover_account) through the
actual UIOperationQueue, with real GUI actions, on one account. ELEVATED:

    .venv\\Scripts\\python.exe scripts\\recover_orch_live.py BinhCuuHoa
"""
import asyncio
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord_bot.bot as botmod  # noqa: E402
from discord_bot.services.ui_operation_queue import UIOperationQueue  # noqa: E402

name = sys.argv[1] if len(sys.argv) > 1 else "BinhCuuHoa"
ACCOUNTS_JSON = (r"C:\Program Files (x86)\Whalebots\Apps\rise-of-kingdoms-bot"
                 r"\Settings\Accounts.json")
roster = []
try:
    data = json.loads(open(ACCOUNTS_JSON, encoding="utf-8-sig").read())
    roster = [a.get("emuInfo", {}).get("name", "") for a in data if a.get("emuInfo", {}).get("name")]
    index = next(i for i, a in enumerate(data)
                 if a.get("emuInfo", {}).get("name") == name)
except Exception as e:
    print(f"roster/index error: {e}"); sys.exit(1)


class FakeWD:
    def reset(self, n): print(f"[wd] reset({n})")


async def main():
    shim = types.SimpleNamespace()
    shim.operation_queue = UIOperationQueue(max_concurrent_operations=1)
    shim.watchdog_service = FakeWD()
    shim.recovery_cooldown = 7200
    shim.recovery_settle = 30
    shim._recovery_last = {}
    shim._recovery_busy = set()
    shim._recover_account = botmod.WhaleBotDiscord._recover_account.__get__(shim)

    print(f"recovering {name} (index {index}) through the real queue...")
    r = await shim._recover_account(name, index, roster=roster, manual=True)
    print("RESULT:", r)
    await shim.operation_queue.stop_processor()

asyncio.run(main())
