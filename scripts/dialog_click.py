"""Find the ROKBot 'Do you want to terminate this emulator?' confirm dialog
(standard Win32 #32770) and click a button by its EXACT window text. Run
ELEVATED (the dialog belongs to the elevated ROKBot process).

    .venv\\Scripts\\python.exe scripts\\dialog_click.py Yes
    .venv\\Scripts\\python.exe scripts\\dialog_click.py No
"""
import ctypes
import sys
import time
from ctypes import windll

import win32gui
import win32api
import win32con

want = (sys.argv[1] if len(sys.argv) > 1 else "Yes").strip().lower()

fn = windll.user32.SetThreadDpiAwarenessContext
fn.restype = ctypes.c_void_p
fn.argtypes = [ctypes.c_void_p]
fn(ctypes.c_void_p(-4))


def find_dialog():
    """The terminate-confirm dialog: class #32770, title exactly 'Rise of
    Kingdoms Bot', with Yes/No button children."""
    hits = []

    def cb(h, _):
        if (win32gui.IsWindowVisible(h)
                and win32gui.GetClassName(h) == "#32770"
                and win32gui.GetWindowText(h) == "Rise of Kingdoms Bot"):
            hits.append(h)
    win32gui.EnumWindows(cb, None)
    return hits[0] if hits else None


h = find_dialog()
if not h:
    print("no confirm dialog open"); sys.exit(0)

btn = None
def kids(c, _):
    global btn
    if (win32gui.GetClassName(c) == "Button"
            and win32gui.GetWindowText(c).strip().lower() == want):
        btn = c
win32gui.EnumChildWindows(h, kids, None)
if not btn:
    print(f"'{want}' button not found on dialog - not clicking"); sys.exit(1)

l, t, r, b = win32gui.GetWindowRect(btn)
cx, cy = (l + r) // 2, (t + b) // 2
try:
    win32gui.SetForegroundWindow(h)
except Exception:
    pass
time.sleep(0.2)
win32api.SetCursorPos((cx, cy))
time.sleep(0.15)
win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
time.sleep(0.06)
win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
time.sleep(0.6)
print(f"clicked '{want}' button at ({cx},{cy})")
print("dialog gone:", not win32gui.IsWindow(h) or not win32gui.IsWindowVisible(h))
