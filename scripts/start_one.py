"""Start one account by name via the direction-safe checkbox click. ELEVATED.
    .venv\\Scripts\\python.exe scripts\\start_one.py BinhCuuHoa
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from whalebots_automation.services.watchdog_reader import click_account_checkbox  # noqa: E402

name = sys.argv[1]
ACCOUNTS_JSON = (r"C:\Program Files (x86)\Whalebots\Apps\rise-of-kingdoms-bot"
                 r"\Settings\Accounts.json")
roster = []
try:
    data = json.loads(open(ACCOUNTS_JSON, encoding="utf-8-sig").read())
    roster = [a.get("emuInfo", {}).get("name", "") for a in data if a.get("emuInfo", {}).get("name")]
except Exception as e:
    print(f"(roster unavailable: {e})")
print(click_account_checkbox(name, roster=roster, ensure="checked"))
