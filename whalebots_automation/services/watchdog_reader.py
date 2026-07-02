"""
watchdog_reader.py - read a specific account's ACTIVITY LOG from the
"Rise of Kingdoms Bot" (ROKBot) GUI.

Why OCR-by-text instead of fixed coordinates?
  The ROKBot window is fully custom-drawn (no child controls) and its layout is
  dynamic - the account list auto-sizes/scrolls, so the tabs and rows move. We
  therefore CAPTURE the window, OCR it to get the *bounding boxes* of the text we
  need (account name, "ACTIVITY LOG" tab, log lines), and click those boxes.
  Because we only ever click where we actually SEE the expected text, this also
  guards against mis-clicks when another window occludes ROKBot (if occluded,
  OCR won't find the target -> we skip rather than click the wrong window).

Flow for one account:
  1. find + foreground + set topmost + resize (both panels visible)
  2. OCR -> locate the account name in the left list -> click it (select)
     (scroll + retry if not currently visible)
  3. OCR -> locate the "ACTIVITY LOG" tab -> click it
  4. OCR -> read timestamped lines from the right (log) panel
     -> latest timestamp + recent lines + bad-state flags

Requires: pywin32, Pillow, winsdk (Windows built-in OCR).
MUST run elevated (ROKBot runs as administrator).
"""
from __future__ import annotations

import asyncio
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import ctypes
import win32api
import win32con
import win32gui
from ctypes import windll
from PIL import Image, ImageGrab

try:
    import pythoncom  # pywin32 - to COM-init worker threads (winsdk OCR needs it)
except Exception:  # pragma: no cover
    pythoncom = None


def _com_init() -> bool:
    """Initialize COM (MTA) on the CURRENT thread so WinRT/winsdk OCR works.

    asyncio.to_thread pool threads are NOT COM-initialized, and winsdk's async
    OCR hangs on an uninitialized thread - which leaks the pool thread and
    eventually freezes the whole sweep. Returns True if we initialized it so the
    caller can balance with _com_uninit().
    """
    if pythoncom is None:
        return False
    try:
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        return True
    except Exception:
        return False


def _com_uninit() -> None:
    if pythoncom is None:
        return
    try:
        pythoncom.CoUninitialize()
    except Exception:
        pass


def set_thread_dpi_aware():
    """Make the CURRENT THREAD DPI-aware (per-monitor v2) so win32 coords,
    ImageGrab capture, and SetCursorPos share one physical-pixel space.

    On a scaled display (e.g. 125%) a DPI-unaware caller gets *virtualized*
    coordinates from ClientToScreen (divided by the scale factor) while ImageGrab
    captures real physical pixels -> OCR'd click targets land ~scale-factor off.

    THREAD-scoped (not process-wide) on purpose: the rest of the bot process
    (start/stop GUI automation) is calibrated for the process default DPI mode.
    Returns the previous context (pass to restore_thread_dpi) or None. Requires
    Windows 10 1607+.
    """
    try:
        fn = windll.user32.SetThreadDpiAwarenessContext
        fn.restype = ctypes.c_void_p
        fn.argtypes = [ctypes.c_void_p]
        prev = fn(ctypes.c_void_p(-4))      # PER_MONITOR_AWARE_V2
        if not prev:
            prev = fn(ctypes.c_void_p(-3))  # PER_MONITOR_AWARE (v1) fallback
        return prev
    except Exception:
        return None


def restore_thread_dpi(prev) -> None:
    """Restore a thread's DPI context saved from set_thread_dpi_aware().

    Critical: watchdog reads run on asyncio.to_thread *pool* threads that are
    reused for other GUI work (start/stop). If a pool thread were left
    DPI-aware, those callers would get physical coords and mis-click. Always
    restore after a read.
    """
    if not prev:
        return
    try:
        fn = windll.user32.SetThreadDpiAwarenessContext
        fn.restype = ctypes.c_void_p
        fn.argtypes = [ctypes.c_void_p]
        fn(ctypes.c_void_p(prev))
    except Exception:
        pass

TITLE_SUBSTR = "Rise of Kingdoms Bot"

# ---------------------------------------------------------------------------
# Layout metrics - scale with the monitor the ROKBot window is on.
#
# The ROKBot UI renders proportionally larger on scaled displays: whatever
# ROKBot's own DPI-awareness mode is, the on-screen (physical-pixel) content
# ends up multiplied by the monitor's scale factor - either it renders at that
# DPI itself or DWM bitmap-stretches it there. Our thread is per-monitor-v2
# aware, so all coords here are physical pixels. Every pixel constant is
# therefore expressed at a 100% (96 DPI) baseline and multiplied by the
# window's monitor factor at runtime. (Originally calibrated at 125% on
# 2560x1440, where e.g. the window was forced to 900x720 = 720x576 * 1.25.)
# ---------------------------------------------------------------------------

# Window size we force so BOTH panels (ACTIVITIES | ACTIVITY LOG) are visible.
BASE_WIN_W, BASE_WIN_H = 720, 576
# The account list sits at the TOP of the window; its rows are above this y
# (tabs row is just below). Kept just under the tab row so a bottom row that's
# scrolled to the edge still counts.
BASE_LIST_Y_MAX = 146
# Activity-log text is in the right panel (right of this x).
BASE_LOG_MIN_X = 296
# The account name lives in the left column; this keeps matching off the
# status / resource columns (and the ACTIVITIES checklist below the list).
BASE_NAME_MAX_X = 160
# A point over the account list to wheel-scroll it.
BASE_LIST_SCROLL = (120, 72)
# A point over the right-hand ACTIVITY LOG panel to wheel-scroll it to newest.
BASE_LOG_SCROLL = (576, 320)
# Words within this y-distance belong to the same log row (~22px pitch at 100%).
BASE_ROW_TOL = 6.5


@dataclass
class Metrics:
    """All layout values for one read, computed from the monitor scale factor."""
    scale: float                     # monitor scale (1.0 = 96 DPI, 1.25 = 125%)
    win_w: int
    win_h: int
    list_y_max: int
    log_min_x: int
    name_max_x: int
    list_scroll: Tuple[int, int]
    log_scroll: Tuple[int, int]
    row_tol: int
    ocr_scale: int                   # OCR upscale factor for this text size


def metrics_for(scale: float) -> Metrics:
    s = max(0.5, float(scale))
    # OCR needs an effective (scale * upscale) of ~2.5x the 96-DPI text size to
    # resolve the [HH:MM:SS] timestamps: 2x was calibrated at 125% (=2.5x
    # effective); at 100% that same text is 20% smaller, so upscale 3x instead.
    ocr = max(2, math.ceil(2.5 / s))
    return Metrics(
        scale=s,
        win_w=round(BASE_WIN_W * s),
        win_h=round(BASE_WIN_H * s),
        list_y_max=round(BASE_LIST_Y_MAX * s),
        log_min_x=round(BASE_LOG_MIN_X * s),
        name_max_x=round(BASE_NAME_MAX_X * s),
        list_scroll=(round(BASE_LIST_SCROLL[0] * s), round(BASE_LIST_SCROLL[1] * s)),
        log_scroll=(round(BASE_LOG_SCROLL[0] * s), round(BASE_LOG_SCROLL[1] * s)),
        row_tol=max(4, round(BASE_ROW_TOL * s)),
        ocr_scale=ocr,
    )


def _window_scale(hwnd) -> float:
    """Scale factor of the monitor the window is on (1.0 = 96 DPI).

    Uses GetDpiForMonitor(MDT_EFFECTIVE_DPI) on the window's monitor - NOT
    GetDpiForWindow(hwnd), which returns 96 for a DPI-unaware target window
    even on a scaled monitor. Explicit argtypes because a bare 64-bit HWND
    silently truncates through ctypes' default int marshaling.
    """
    try:
        u = windll.user32
        u.MonitorFromWindow.restype = ctypes.c_void_p
        u.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        mon = u.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        sh = windll.shcore
        sh.GetDpiForMonitor.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                        ctypes.POINTER(ctypes.c_uint),
                                        ctypes.POINTER(ctypes.c_uint)]
        dx, dy = ctypes.c_uint(), ctypes.c_uint()
        if sh.GetDpiForMonitor(mon, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0:
            return dx.value / 96.0  # MDT_EFFECTIVE_DPI
    except Exception:
        pass
    try:
        # Fallback (pre-Win8.1): system DPI. Thread is DPI-aware, so this is
        # the real value, just not per-monitor.
        hdc = windll.user32.GetDC(0)
        try:
            return windll.gdi32.GetDeviceCaps(hdc, 88) / 96.0  # LOGPIXELSX
        finally:
            windll.user32.ReleaseDC(0, hdc)
    except Exception:
        return 1.0

TS_RE = re.compile(r"\[(\d{1,2}):(\d{2}):(\d{2})\]")

# Substrings (lowercase) in recent log lines that indicate a stuck / bad state.
BAD_STATES = (
    "offline", "disconnected", "reconnect", "connecting",
    "preparing", "initializing", "game is loading",
    "logged in from another device", "failed", "error",
)


@dataclass
class Word:
    text: str
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> int:
        return int(self.x + self.w / 2)

    @property
    def cy(self) -> int:
        return int(self.y + self.h / 2)


@dataclass
class LogReading:
    account: str
    ok: bool
    latest_ts: Optional[str] = None          # "HH:MM:SS"
    lines: List[str] = field(default_factory=list)
    bad_states: List[str] = field(default_factory=list)
    error: Optional[str] = None


# --------------------------------------------------------------------------
# OCR via Windows built-in engine (winsdk) - no external binary needed.
# --------------------------------------------------------------------------
async def _ocr_async(png_path: str) -> Tuple[List[Word], List[dict]]:
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage import StorageFile, FileAccessMode

    f = await StorageFile.get_file_from_path_async(png_path)
    stream = await f.open_async(FileAccessMode.READ)
    decoder = await BitmapDecoder.create_async(stream)
    bmp = await decoder.get_software_bitmap_async()
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError("No OCR language pack installed (Windows OCR unavailable)")
    result = await engine.recognize_async(bmp)

    words: List[Word] = []
    lines: List[dict] = []
    for line in result.lines:
        lw: List[Word] = []
        for w in line.words:
            r = w.bounding_rect
            word = Word(w.text, int(r.x), int(r.y), int(r.width), int(r.height))
            words.append(word)
            lw.append(word)
        lines.append({
            "text": " ".join(x.text for x in lw),
            "x": min((x.x for x in lw), default=0),
            "y": min((x.y for x in lw), default=0),
        })
    return words, lines


def ocr_image(img, scale: int = 2) -> Tuple[List[Word], List[dict]]:
    """Run Windows OCR on a PIL image; returns (words, lines) in ORIGINAL pixels.

    The image is upscaled `scale`x before OCR so small text (the [HH:MM:SS]
    timestamps especially) resolves reliably; coordinates are scaled back.

    Runs the OCR on a FRESH thread that we COM-initialize as MTA. WinRT OCR
    under asyncio.run hangs on an STA thread (e.g. the process main thread, which
    pywin32 puts in STA), so we never run it on the caller's thread. The fresh
    thread also gets a hard timeout so a stuck call can't wedge anything.
    """
    if scale != 1:
        try:
            img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
        except Exception:
            scale = 1
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path)
    box = {}

    def _worker():
        com = _com_init()  # fresh thread -> MTA succeeds -> WinRT OCR works
        try:
            box["result"] = asyncio.run(asyncio.wait_for(_ocr_async(path), timeout=20))
        except BaseException as e:  # noqa: BLE001 - propagate to caller below
            box["error"] = e
        finally:
            if com:
                _com_uninit()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=25)
    try:
        os.remove(path)
    except OSError:
        pass
    if "result" not in box:
        raise box.get("error", RuntimeError("OCR thread timed out"))
    words, lines = box["result"]
    if scale != 1:
        words = [Word(w.text, w.x // scale, w.y // scale, w.w // scale, w.h // scale)
                 for w in words]
        lines = [{"text": ln["text"], "x": ln["x"] // scale, "y": ln["y"] // scale}
                 for ln in lines]
    return words, lines


# --------------------------------------------------------------------------
# ROKBot window control
# --------------------------------------------------------------------------
class ROKWindow:
    def __init__(self):
        self.hwnd = None
        self._orig = None  # (x, y, w, h, was_topmost) captured in prepare()
        self.m = metrics_for(1.0)  # replaced with the real monitor scale in prepare()

    def find(self) -> bool:
        res = []

        def cb(h, _):
            if win32gui.IsWindowVisible(h) and TITLE_SUBSTR in win32gui.GetWindowText(h):
                res.append(h)

        win32gui.EnumWindows(cb, None)
        self.hwnd = res[0] if res else None
        return self.hwnd is not None

    def prepare(self) -> None:
        """Topmost + resize so both panels are visible and ABOVE other windows.

        Uses pywin32 wrappers (not raw ctypes) so the HWND marshals correctly on
        64-bit Python - otherwise SetWindowPos/SetForegroundWindow silently no-op
        and the window stays occluded.
        """
        if win32gui.IsIconic(self.hwnd):
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
        # Size everything for the monitor this window actually lives on.
        self.m = metrics_for(_window_scale(self.hwnd))
        # Remember the window's current placement so we can put it back afterward
        # (the existing start/stop automation relies on the user's window size).
        try:
            l, t, r, b = win32gui.GetWindowRect(self.hwnd)
            ex = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
            self._orig = (l, t, r - l, b - t, bool(ex & win32con.WS_EX_TOPMOST))
        except Exception:
            self._orig = None
        # Raise above everything (BlueStacks / terminal) and resize to show both panels.
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, 0, 0,
                              self.m.win_w, self.m.win_h, win32con.SWP_NOMOVE)
        try:
            win32gui.SetForegroundWindow(self.hwnd)
        except Exception:
            pass
        time.sleep(0.6)

    def release_topmost(self) -> None:
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    def restore_placement(self) -> None:
        """Restore the pre-prepare position/size/z-order so the existing
        start/stop GUI automation (calibrated for the user's window size) keeps
        working when it runs between watchdog reads."""
        o = self._orig
        if not o:
            self.release_topmost()
            return
        x, y, w, h, was_topmost = o
        z = win32con.HWND_TOPMOST if was_topmost else win32con.HWND_NOTOPMOST
        try:
            win32gui.SetWindowPos(self.hwnd, z, x, y, w, h, 0)
        except Exception:
            pass

    def scroll_to_top(self) -> None:
        """Reset the list to the first account (deterministic start).

        Measured: positive wheel = UP, negative = DOWN; one notch ~= 1-2 rows.
        Over-scrolls up well past the list length; scrolling up at the top is a
        harmless no-op, so this lands on the top from anywhere.
        """
        self.scroll(*self.m.list_scroll, 30, settle=0.25)

    def capture(self):
        l, t = win32gui.ClientToScreen(self.hwnd, (0, 0))
        cr = win32gui.GetClientRect(self.hwnd)
        return ImageGrab.grab(bbox=(l, t, l + cr[2], t + cr[3]))

    def click_client(self, cx: int, cy: int) -> None:
        sx, sy = win32gui.ClientToScreen(self.hwnd, (int(cx), int(cy)))
        win32api.SetCursorPos((sx, sy))
        time.sleep(0.08)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.06)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.05)

    def scroll(self, cx: int, cy: int, notches: int, settle: float = 0.3) -> None:
        """Wheel-scroll the list by `notches` (positive = UP, negative = DOWN
        for this app). One wheel event per notch so it advances a row or two at a
        time (never skipping a page). `settle` is the pause before the next read.
        """
        sx, sy = win32gui.ClientToScreen(self.hwnd, (int(cx), int(cy)))
        win32api.SetCursorPos((sx, sy))
        time.sleep(0.03)
        step = 120 if notches >= 0 else -120
        for _ in range(abs(notches)):
            win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, step, 0)
            time.sleep(0.04)
        time.sleep(settle)


# --------------------------------------------------------------------------
# OCR-locate helpers
# --------------------------------------------------------------------------
def _norm(s: str) -> str:
    """Lowercase + strip non-alphanumerics so OCR punctuation/spacing noise
    (e.g. 'Duc.', 'New Mida5') doesn't defeat a match."""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _edit_dist(a: str, b: str) -> int:
    """Levenshtein distance (small strings)."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if not la:
        return lb
    if not lb:
        return la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[lb]


def _find_name(words: List[Word], name: str, m: Metrics) -> Optional[Word]:
    """Find an account name in the list's name column, tolerant of OCR noise
    (OCR routinely garbles a character, e.g. 'Duc' -> 'ouc', 'MinHe' -> 'Mir,He')."""
    t = _norm(name)
    n = len(t)
    cands = [w for w in words
             if w.cy <= m.list_y_max and w.cx < m.name_max_x
             and any(c.isalpha() for c in w.text)]

    # 1) exact (normalized)
    for w in cands:
        if _norm(w.text) == t:
            return w
    # 2) prefix (>=3) / substring (>=4) - OCR clipping/merging
    for w in cands:
        wt = _norm(w.text)
        if wt and ((n >= 3 and wt.startswith(t)) or (n >= 4 and t in wt)):
            return w
    # 3) fuzzy: closest by edit distance, within tolerance and UNambiguously best
    tol = 1 if n <= 5 else max(1, n // 4)
    best = best_w = None
    best_d = second_d = 99
    for w in cands:
        wt = _norm(w.text)
        if not wt or abs(len(wt) - n) > tol:
            continue
        d = _edit_dist(t, wt)
        if d < best_d:
            second_d, best_d, best_w = best_d, d, w
        elif d < second_d:
            second_d = d
    if best_w is not None and best_d <= tol and best_d < second_d:
        return best_w
    return None


def _find_log_tab(words: List[Word], m: Metrics) -> Optional[Tuple[int, int]]:
    """Locate the 'ACTIVITY LOG' tab (right side)."""
    # "ACTIVITY" (the log tab) is distinct from "ACTIVITIES" (left tab), so an
    # exact match uniquely identifies the right-panel log tab.
    act = [w for w in words if w.text.upper() == "ACTIVITY"]
    log = [w for w in words if w.text.upper() == "LOG"]
    if act and log:
        return ((act[0].cx + log[0].cx) // 2, (act[0].cy + log[0].cy) // 2)
    if act:
        return (act[0].cx + round(22 * m.scale), act[0].cy)
    return None


def _has_anchors(words: List[Word]) -> bool:
    """True if the window looks like ROKBot (not fully occluded)."""
    txts = {w.text.upper() for w in words}
    return "ACTIVITIES" in txts or ("ACTIVITY" in txts and "LOG" in txts)


def _log_lines_from_words(words: List[Word], m: Metrics) -> List[str]:
    """Reconstruct ACTIVITY LOG lines from RIGHT-panel words only, grouped into
    rows by y.

    The OCR groups text by physical row, so a single OCR line mixes the left
    ACTIVITIES column and the right LOG column. We therefore drop everything left
    of the log panel and rebuild each log row from the remaining words.
    """
    log_words = sorted((w for w in words if w.x >= m.log_min_x), key=lambda w: (w.cy, w.x))
    rows: List[Tuple[int, List[str]]] = []
    for w in log_words:
        if rows and abs(w.cy - rows[-1][0]) <= m.row_tol:   # same log row
            rows[-1][1].append(w.text)
        else:
            rows.append((w.cy, [w.text]))
    out = []
    for _cy, texts in rows:
        line = " ".join(texts)
        if TS_RE.search(line):
            out.append(line)
    return out


def _latest_ts(lines: List[str]) -> Optional[str]:
    best = None
    for ln in lines:
        for m in TS_RE.finditer(ln):
            h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
            key = (h, mi, s)
            if best is None or key > best[0]:
                best = (key, f"{h:02d}:{mi:02d}:{s:02d}")
    return best[1] if best else None


# --------------------------------------------------------------------------
# Main entry: read one account's log
# --------------------------------------------------------------------------
def read_account_log(name: str, win: Optional[ROKWindow] = None,
                     keep_topmost: bool = False) -> LogReading:
    prev_dpi = set_thread_dpi_aware()
    win = win or ROKWindow()
    if not win.find():
        restore_thread_dpi(prev_dpi)
        return LogReading(name, False, error="ROKBot window not found")
    prepared = False
    try:
        win.prepare()
        prepared = True

        # 1) select the account. ALWAYS reset to the top first (the list may have
        #    been left scrolled anywhere by an interleaved start/stop), then page
        #    DOWN a couple of rows at a time until we find it or hit the bottom.
        win.scroll_to_top()
        m = win.m                # layout metrics for this window's monitor scale
        selected = False
        last_keys = None
        seen = set()             # every list-row word seen (for diagnosis if not found)
        for _ in range(18):      # ~18 pages * ~2-4 rows >> max account count
            words, _lines = ocr_image(win.capture(), scale=m.ocr_scale)
            if not _has_anchors(words):
                return LogReading(name, False, error="window occluded (no ROKBot anchors visible)")
            for w in words:
                if w.cy <= m.list_y_max and len(w.text) >= 2:
                    seen.add(w.text)
            nm = _find_name(words, name, m)
            if nm:
                win.click_client(nm.cx, nm.cy)
                time.sleep(0.4)
                selected = True
                break
            keys = frozenset(_norm(w.text) for w in words
                             if w.cy <= m.list_y_max and w.cx < m.name_max_x and any(c.isalpha() for c in w.text))
            if last_keys is not None and keys == last_keys:
                break            # view didn't change after scrolling -> bottom reached
            last_keys = keys
            win.scroll(*m.list_scroll, -2)   # page down ~2-4 rows (overlap, no skip)
        if not selected:
            try:
                win.capture().save(rf"C:\Users\binlo\rok_notfound_{name}.png")
            except Exception:
                pass
            name_like = sorted({w for w in seen if any(c.isalpha() for c in w)})
            sample = ", ".join(name_like[:60])
            return LogReading(name, False,
                              error=f"account '{name}' not found in list "
                                    f"(png saved). names seen: {sample}")

        # 2) ensure ACTIVITY LOG tab is active
        words, _lines = ocr_image(win.capture(), scale=m.ocr_scale)
        tab = _find_log_tab(words, m)
        if tab:
            win.click_client(*tab)
            time.sleep(0.5)

        # 3) read the log panel. Rebuild log rows from RIGHT-panel words only
        #    (the OCR merges the left ACTIVITIES column onto the same rows).
        words, _lines = ocr_image(win.capture(), scale=m.ocr_scale)
        log_lines = _log_lines_from_words(words, m)
        if not log_lines:
            return LogReading(name, False, error="no log lines read (panel empty or occluded)")

        latest = _latest_ts(log_lines)
        recent = log_lines[-6:]
        bad = sorted({s for s in BAD_STATES
                      if any(s in l.lower() for l in recent)})
        return LogReading(name, True, latest_ts=latest, lines=log_lines, bad_states=bad)
    finally:
        # Always restore the window to how we found it (size/pos/z-order) so the
        # serialized start/stop ops that interleave between reads aren't disrupted,
        # and restore this thread's DPI context (pool threads are reused).
        if prepared:
            try:
                win.restore_placement()
            except Exception:
                pass
        restore_thread_dpi(prev_dpi)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", help="account/emulator display name to read")
    ap.add_argument("--dump", action="store_true",
                    help="prepare window + scroll to top + print ALL OCR words (no clicks)")
    args = ap.parse_args()

    if args.dump:
        set_thread_dpi_aware()
        w = ROKWindow()
        if not w.find():
            print("ROKBot window not found"); raise SystemExit(1)
        w.prepare()
        cap = w.capture()
        cap.save(r"C:\Users\binlo\rok_ocr_dump.png")
        words, lines = ocr_image(cap, scale=w.m.ocr_scale)
        heights = sorted(wd.h for wd in words) if words else []
        med_h = heights[len(heights) // 2] if heights else 0
        out = r"C:\Users\binlo\rok_ocr_dump.txt"
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(f"monitor scale: {w.m.scale:.2f}  | metrics: {w.m}\n")
            fh.write(f"client capture size: {cap.size}  | median text height: {med_h}px "
                     f"(original pixels; OCR upscaled {w.m.ocr_scale}x)\n")
            fh.write(f"--- {len(words)} words (text @ client cx,cy, h=height) ---\n")
            for wd in sorted(words, key=lambda z: (z.cy, z.cx)):
                fh.write(f"  ({wd.cx:>4},{wd.cy:>4}) h={wd.h:>2}  '{wd.text}'\n")
        print(f"scale {w.m.scale:.2f}, {len(words)} words, client {cap.size}, "
              f"median text height {med_h}px; wrote {out} (+ .png)")
        w.release_topmost()
        raise SystemExit(0)

    if not args.account:
        ap.error("--account is required (or use --dump)")
    r = read_account_log(args.account, keep_topmost=False)
    print(f"account   : {r.account}")
    print(f"ok        : {r.ok}")
    print(f"latest_ts : {r.latest_ts}")
    print(f"bad_states: {r.bad_states}")
    print(f"error     : {r.error}")
    print("--- lines ---")
    for ln in r.lines:
        print(" ", ln)
