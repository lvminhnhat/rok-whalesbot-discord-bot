"""
SAFE probe v3: press-and-HOLD on the 3-dot, capture the menu while the button
is held, slide the cursor to the window title bar, release there (harmless),
then Esc. Never releases over the menu, clicks NO item. Run ELEVATED:

    .venv\\Scripts\\python.exe scripts\\menu_probe3.py BinhCuuHoa

Saves C:\\Users\\binlo\\rok_menu3_held.png + rok_menu3.txt.
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
held = False
try:
    m = win.m
    anch, err = _prepare_window(win)
    if err:
        print(err); sys.exit(1)
    nm, img, seen, err = _locate_row(win, name, m, anch, roster)
    if err or nm is None:
        print(err or f"'{name}' not found/verified"); sys.exit(1)
    cb = _checkbox_state(img, nm.cy, m)
    print(f"health check: '{nm.text}' present, checkbox={cb} "
          f"({'RUNNING' if cb else 'NOT running' if cb is False else 'unknown'})")

    cw, ch = win32gui.GetClientRect(win.hwnd)[2:]
    dots_x = cw - round(16 * m.scale)
    baseline = {w.text for w in ocr_image(win.capture(), scale=m.ocr_scale)[0]}

    sx, sy = win32gui.ClientToScreen(win.hwnd, (dots_x, nm.cy))
    win32api.SetCursorPos((sx, sy))
    time.sleep(0.3)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    held = True
    time.sleep(0.5)

    cap = win.capture()                     # capture WHILE the button is held
    cap.save(r"C:\Users\binlo\rok_menu3_held.png")
    words, _ = ocr_image(cap, scale=m.ocr_scale)
    new = sorted({w.text for w in words} - baseline)
    with open(r"C:\Users\binlo\rok_menu3.txt", "w", encoding="utf-8") as fh:
        fh.write(f"held-capture at dots ({dots_x},{nm.cy}); {len(new)} new words\n")
        for w in sorted(words, key=lambda z: (z.cy, z.cx)):
            mark = " NEW" if w.text in new else ""
            fh.write(f"  ({w.cx:>4},{w.cy:>4}) {w.text!r}{mark}\n")
    print(f"while HELD: {len(new)} new words: {new[:15]}")

    # slide to the title bar (safe), release there, then Esc
    tx, ty = win32gui.ClientToScreen(win.hwnd, (min(300, cw // 2), -12))
    for step in range(8):                   # gradual slide, some UIs track hover
        ix = sx + (tx - sx) * (step + 1) // 8
        iy = sy + (ty - sy) * (step + 1) // 8
        win32api.SetCursorPos((ix, iy))
        time.sleep(0.03)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    held = False
    time.sleep(0.3)
    win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.3)
    print("released on title bar + Esc")
finally:
    if held:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    win.restore_placement()
print("done")
