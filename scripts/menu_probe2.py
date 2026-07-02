"""
SAFE probe v2: try several 3-dot X offsets / hover styles and capture at
several instants after each click to find what opens the row menu.
Clicks NO menu item; sends Esc after each attempt. Run ELEVATED:

    .venv\\Scripts\\python.exe scripts\\menu_probe2.py BinhCuuHoa

Saves C:\\Users\\binlo\\rok_menu2_<attempt>_<delay>.png and prints which
captures contain NEW words (vs the pre-click baseline) - menu items show up
as new words.
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
    _prepare_window, _locate_row,
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


def esc():
    win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.3)


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
    cw, ch = win32gui.GetClientRect(win.hwnd)[2:]
    print(f"row '{nm.text}' at ({nm.cx},{nm.cy}); client {cw}x{ch}; scale {m.scale}")

    base_words, _ = ocr_image(win.capture(), scale=m.ocr_scale)
    baseline = {w.text for w in base_words}
    print(f"baseline words: {len(baseline)}")

    offsets = [round(16 * m.scale), round(20 * m.scale), round(12 * m.scale),
               round(24 * m.scale)]
    for i, off in enumerate(offsets):
        x = cw - off
        # hover first (350ms), then click
        sx, sy = win32gui.ClientToScreen(win.hwnd, (x, nm.cy))
        win32api.SetCursorPos((sx, sy))
        time.sleep(0.35)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.06)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        found_new = False
        for delay_i, delay in enumerate((0.2, 0.6, 1.2)):
            time.sleep(delay if delay_i == 0 else delay - (0.2, 0.6, 1.2)[delay_i - 1])
            cap = win.capture()
            cap.save(rf"C:\Users\binlo\rok_menu2_{i}_{delay_i}.png")
            words, _ = ocr_image(cap, scale=m.ocr_scale)
            new = sorted({w.text for w in words} - baseline)
            print(f"attempt {i} x={x} (+{off} from right) t={delay}s: "
                  f"{len(new)} new words: {new[:12]}")
            if new:
                found_new = True
                for w in sorted(words, key=lambda z: (z.cy, z.cx)):
                    if w.text in new:
                        print(f"    NEW ({w.cx:>4},{w.cy:>4}) {w.text!r}")
        esc()
        if found_new:
            print(">>> menu (or state change) detected on this attempt - stopping here")
            break
finally:
    win.restore_placement()
print("done")
