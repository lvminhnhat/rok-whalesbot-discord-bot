"""
Measure how far the account list scrolls per wheel notch (and which sign is
'down'), so the finder can page through without skipping rows. Run ELEVATED:

    .venv\\Scripts\\python.exe scripts\\wd_scroll_calib.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32api  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402
from whalebots_automation.services.watchdog_reader import (  # noqa: E402
    ROKWindow, ocr_image, set_thread_dpi_aware, _com_init, _com_uninit,
)


def raw_scroll(win, delta):
    sx, sy = win32gui.ClientToScreen(win.hwnd, win.m.list_scroll)
    win32api.SetCursorPos((sx, sy))
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, int(delta), 0)
    time.sleep(0.35)


def names(win):
    words, _ = ocr_image(win.capture(), scale=win.m.ocr_scale)
    rows = [w for w in words
            if w.cy <= win.m.list_y_max and w.cx < win.m.name_max_x
            and any(c.isalpha() for c in w.text)]
    rows.sort(key=lambda w: w.cy)
    return [w.text for w in rows]


set_thread_dpi_aware()
_com_init()
win = ROKWindow()
if not win.find():
    print("ROKBot window not found")
    sys.exit(1)
win.prepare()
try:
    print("START :", names(win))
    for i in range(5):
        raw_scroll(win, 120)   # one notch, "positive"
        print(f"+120 #{i+1}:", names(win))
    for i in range(5):
        raw_scroll(win, -120)  # one notch, "negative"
        print(f"-120 #{i+1}:", names(win))
finally:
    win.restore_placement()
    _com_uninit()
