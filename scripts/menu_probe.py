"""
SAFE probe: find an account's row (verified, name-anchored), click its 3-dot
menu button, capture + OCR the opened menu, then dismiss it with Esc.
It clicks NO menu item. Run ELEVATED:

    .venv\\Scripts\\python.exe scripts\\menu_probe.py BinhCuuHoa
    .venv\\Scripts\\python.exe scripts\\menu_probe.py BinhCuuHoa 860   # override 3-dot X

Saves to C:\\Users\\binlo\\:
  rok_menu_client.png / rok_menu_screen.png   captures (window client / window+margin)
  rok_menu.txt                                OCR words with coords from both
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32api  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402
from PIL import ImageGrab  # noqa: E402

from whalebots_automation.services.watchdog_reader import (  # noqa: E402
    ROKWindow, ocr_image, set_thread_dpi_aware,
    _prepare_window, _locate_row, _checkbox_state,
)

ACCOUNTS_JSON = (r"C:\Program Files (x86)\Whalebots\Apps\rise-of-kingdoms-bot"
                 r"\Settings\Accounts.json")

name = sys.argv[1] if len(sys.argv) > 1 else "BinhCuuHoa"
dots_x_override = int(sys.argv[2]) if len(sys.argv) > 2 else None

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
    cw = win32gui.GetClientRect(win.hwnd)[2]
    dots_x = dots_x_override if dots_x_override else cw - round(16 * m.scale)
    print(f"found '{nm.text}' at ({nm.cx},{nm.cy}), checkbox={cb}, "
          f"client_w={cw}, scale={m.scale:.2f} -> clicking 3-dot at ({dots_x},{nm.cy})")

    win.click_client(dots_x, nm.cy)      # opens the menu; clicks NO item
    time.sleep(0.8)

    # capture the window client area AND a larger screen region (a popup menu
    # may be its own top-level window outside our client area)
    client_cap = win.capture()
    client_cap.save(r"C:\Users\binlo\rok_menu_client.png")
    l, t = win32gui.ClientToScreen(win.hwnd, (0, 0))
    r_, b_ = win32gui.ClientToScreen(win.hwnd, (cw, win32gui.GetClientRect(win.hwnd)[3]))
    screen_cap = ImageGrab.grab(bbox=(l - 60, t - 60, r_ + 360, b_ + 360), all_screens=True)
    screen_cap.save(r"C:\Users\binlo\rok_menu_screen.png")

    out = r"C:\Users\binlo\rok_menu.txt"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(f"target '{name}' matched '{nm.text}' at ({nm.cx},{nm.cy}); "
                 f"checkbox={cb}; 3-dot click at ({dots_x},{nm.cy}); "
                 f"client_w={cw}; scale={m.scale}\n")
        for label, cap in (("CLIENT", client_cap), ("SCREEN(+margin)", screen_cap)):
            words, _lines = ocr_image(cap, scale=m.ocr_scale)
            fh.write(f"\n--- {label} capture {cap.size}: {len(words)} words ---\n")
            for w in sorted(words, key=lambda z: (z.cy, z.cx)):
                fh.write(f"  ({w.cx:>4},{w.cy:>4}) {w.text!r}\n")
    print(f"saved rok_menu_client.png, rok_menu_screen.png, {out}")

    # dismiss the menu with Esc - never click to dismiss
    win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.3)
    print("sent Esc to dismiss")
finally:
    win.restore_placement()
