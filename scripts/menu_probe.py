"""
SAFE probe v4: select the account row (verified name-anchored click), then
RIGHT-CLICK the row to open its context menu; capture + OCR it; dismiss with
Esc. Clicks NO menu item. Run ELEVATED:

    .venv\\Scripts\\python.exe scripts\\menu_probe4.py BinhCuuHoa

Saves C:\\Users\\binlo\\rok_menu4.png + rok_menu4.txt.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32api  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402

from whalebots_automation.services.watchdog_reader import (  # noqa: E402
    ROKWindow, ocr_image, set_thread_dpi_aware,
    _prepare_window, _locate_row, _checkbox_state,
)

ACCOUNTS_JSON = (r"C:\Program Files (x86)\Whalebots\Apps\rise-of-kingdoms-bot"
                 r"\Settings\Accounts.json")
name = sys.argv[1] if len(sys.argv) > 1 else "BinhCuuHoa"

roster = []
try:
    data = json.loads(open(ACCOUNTS_JSON, encoding="utf-8-sig").read())
    roster = [a.get("emuInfo", {}).get("name", "") for a in data if a.get("emuInfo", {}).get("name")]
except Exception as e:
    print(f"(roster unavailable: {e})")

set_thread_dpi_aware()
win = ROKWindow()
if not win.find():
    print("ROKBot window not found"); sys.exit(1)
win.prepare()
try:
    m = win.m
    anch, err = _prepare_window(win)
    if err:
        print(err); sys.exit(1)
    nm, img, seen, err = _locate_row(win, name, m, anch, roster)
    if err or nm is None:
        print(err or f"'{name}' not found/verified"); sys.exit(1)
    cb = _checkbox_state(img, nm.cy, m)
    print(f"'{nm.text}' at ({nm.cx},{nm.cy}), checkbox={cb}")
    baseline = {w.text for w in ocr_image(img, scale=m.ocr_scale)[0]}

    # 1) select the row (left-click the name - the proven selection click)
    win.click_client(nm.cx, nm.cy)
    time.sleep(0.5)

    # 2) RIGHT-click the same spot on the row -> context menu (opens to the
    #    right of the cursor per user)
    sx, sy = win32gui.ClientToScreen(win.hwnd, (nm.cx, nm.cy))
    win32api.SetCursorPos((sx, sy))
    time.sleep(0.15)
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    time.sleep(0.08)
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

    for delay_i, wait in enumerate((0.4, 0.8)):
        time.sleep(wait if delay_i == 0 else wait - 0.4)
        cap = win.capture()
        cap.save(rf"C:\Users\binlo\rok_menu4_{delay_i}.png")
        words, _ = ocr_image(cap, scale=m.ocr_scale)
        new = sorted({w.text for w in words} - baseline)
        print(f"t={wait}s: {len(new)} new words: {new[:20]}")
        with open(rf"C:\Users\binlo\rok_menu4_{delay_i}.txt", "w", encoding="utf-8") as fh:
            for w in sorted(words, key=lambda z: (z.cy, z.cx)):
                mark = "  NEW" if w.text in new else ""
                fh.write(f"  ({w.cx:>4},{w.cy:>4}) {w.text!r}{mark}\n")

    # dismiss with Esc, never with a click
    win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.3)
    print("Esc sent")
finally:
    win.restore_placement()
print("done")
