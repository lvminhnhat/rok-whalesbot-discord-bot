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
  1. find + foreground + set topmost (window size/position are NEVER changed;
     panel regions are derived per read from the OCR'd tabs-row anchors)
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
# Layout handling - no resizing, no fixed regions.
#
# We never touch the ROKBot window's size or position: resizing proved fragile
# (a crashed/overlapping read can capture an already-resized window as the
# "original" and the user's layout is lost). Instead the panel regions are
# derived per read from OCR anchors - the tabs row ("ACTIVITIES" / "ACTIVITY
# LOG") marks both where the account list ends (y) and where the log panel
# starts (x) - so any window size that shows both panels works as-is.
#
# The few remaining pixel constants are about TEXT size, which is independent
# of window size but proportional to the monitor's scale factor: whatever
# ROKBot's own DPI-awareness mode is, its on-screen (physical-pixel) content is
# multiplied by that factor - either it renders at that DPI itself or DWM
# bitmap-stretches it there. Our thread is per-monitor-v2 aware, so all coords
# here are physical pixels. Constants are a 100% (96 DPI) baseline scaled at
# runtime (originally calibrated at 125% on 2560x1440).
# ---------------------------------------------------------------------------

# The account name is the leftmost column of the list; words starting right of
# this are the status / resource columns. The list columns are left-anchored,
# so this tracks text size (DPI), not window width.
BASE_NAME_MAX_X = 160
# x of the per-row start/stop checkbox (leftmost column, before the name).
BASE_CHECKBOX_X = 16
# Words within this y-distance belong to the same log row (~22px pitch at 100%).
BASE_ROW_TOL = 6.5


@dataclass
class Metrics:
    """Text-size-dependent values, computed from the monitor scale factor."""
    scale: float                     # monitor scale (1.0 = 96 DPI, 1.25 = 125%)
    name_max_x: int
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
        name_max_x=round(BASE_NAME_MAX_X * s),
        row_tol=max(4, round(BASE_ROW_TOL * s)),
        ocr_scale=ocr,
    )


@dataclass
class Anchors:
    """Window-size-dependent regions, located from OCR of the tabs row."""
    list_y_max: int                  # account-list rows are above this y
    log_min_x: int                   # ACTIVITY LOG panel text is right of this x
    list_scroll: Tuple[int, int]     # a point over the account list to wheel-scroll


def _find_anchors(words: List[Word], m: Metrics) -> Optional[Anchors]:
    """Derive the panel regions from the 'ACTIVITY LOG' tab's position.

    'ACTIVITY' (exact) only occurs as the log tab ('ACTIVITIES' is the left
    tab), and both tabs sit on one row between the account list above and the
    panels below - so its top-left corner gives us both boundaries at any
    window size. Returns None if the tab isn't visible (window occluded or too
    small to show the log panel).
    """
    act = [w for w in words if w.text.upper() == "ACTIVITY"]
    if not act:
        return None
    a = act[0]
    pad = round(8 * m.scale)
    list_y_max = max(0, a.y - pad)
    # Scroll point: over the name column, vertically inside the list (its
    # midpoint, but no lower than a couple of rows down from the top).
    sx = round(m.name_max_x * 0.6)
    sy = max(round(16 * m.scale), list_y_max // 2)
    return Anchors(list_y_max=list_y_max, log_min_x=max(0, a.x - pad),
                   list_scroll=(sx, sy))


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
    running: Optional[bool] = None           # GUI checkbox state (None = not determined)


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
        self._was_topmost = False  # captured in prepare()
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
        """Raise the window topmost so nothing occludes the capture. The
        window's SIZE and POSITION are never touched - panel regions are
        OCR-anchored per read (see _find_anchors), so any user layout works.

        Uses pywin32 wrappers (not raw ctypes) so the HWND marshals correctly on
        64-bit Python - otherwise SetWindowPos/SetForegroundWindow silently no-op
        and the window stays occluded.
        """
        if win32gui.IsIconic(self.hwnd):
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
        # Size text-dependent values for the monitor this window actually lives on.
        self.m = metrics_for(_window_scale(self.hwnd))
        try:
            ex = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
            self._was_topmost = bool(ex & win32con.WS_EX_TOPMOST)
        except Exception:
            self._was_topmost = False
        # Raise above everything (BlueStacks / terminal) - z-order only.
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        try:
            win32gui.SetForegroundWindow(self.hwnd)
        except Exception:
            pass
        time.sleep(0.6)

    def release_topmost(self) -> None:
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    def restore_placement(self) -> None:
        """Undo prepare(): drop the temporary topmost bit (unless the window
        was topmost to begin with). Size/position were never changed."""
        if not self._was_topmost:
            try:
                self.release_topmost()
            except Exception:
                pass

    def scroll_to_top(self, at: Tuple[int, int]) -> None:
        """Reset the list to the first account (deterministic start). `at` is
        a point over the account list (from the OCR anchors).

        Measured: positive wheel = UP, negative = DOWN; one notch ~= 1-2 rows.
        Over-scrolls up well past the list length; scrolling up at the top is a
        harmless no-op, so this lands on the top from anywhere.
        """
        self.scroll(*at, 30, settle=0.25)

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


# OCR-confusable glyph classes, folded to one canonical member. '1' vs 'l' is
# the killer: they're near-identical in this font at ANY magnification, so
# 'Piltong1' chronically reads as 'Piltongl' and stays edit-distance 1 from
# Piltong1/2/3 alike - unmatchable under the strict roster gate. Folding is
# applied to BOTH sides of every comparison, so target, sibling and OCR word
# all land in the same space and only REAL differences (like the 2 in
# Piltong2) count. (7 and 9 don't fold together, so KatFruit87 vs KatFruit89
# still can't cross-match.)
_CONFUSABLE = str.maketrans({"l": "1", "i": "1", "o": "0", "s": "5",
                             "b": "8", "z": "2", "g": "9"})


def _fold(s: str) -> str:
    """_norm + confusable-glyph folding: the string space all name-match
    comparisons happen in."""
    return _norm(s).translate(_CONFUSABLE)


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


def _tol(n: int) -> int:
    """Edit-distance tolerance for a target of normalized length n."""
    return 1 if n <= 5 else max(1, n // 4)


def _other_names(name: str, roster: Optional[List[str]]) -> List[str]:
    """Folded roster names EXCLUDING the target."""
    t = _fold(name)
    return [nr for r in (roster or []) if (nr := _fold(r)) and nr != t]


def _roster_gate(word_norm: str, d_target: int, others: List[str]) -> bool:
    """True if no OTHER account's name explains this OCR word at least as well
    as the target does.

    This is what makes matching safe with sibling accounts: looking for
    'KatFruit87' while 'KatFruit89' is on screen, the word 'katfruit89' is
    distance 1 from the target but distance 0 from the other roster name, so
    it is rejected (it IS that other account). Requires a STRICTLY better fit
    for the target."""
    return all(_edit_dist(word_norm, o) > d_target for o in others)


def _find_name(words: List[Word], name: str, m: Metrics, a: Anchors,
               roster: Optional[List[str]] = None) -> Optional[Word]:
    """Find an account name in the list's name column, tolerant of OCR noise
    (OCR routinely garbles a character, e.g. 'Duc' -> 'ouc', 'MinHe' -> 'Mir,He').

    `roster` is the full list of real account names; every match rule is gated
    on the word not fitting some OTHER account at least as well (see
    _roster_gate). Without it, near-identical names can cross-match. All
    comparisons happen in _fold space so OCR-confusable glyphs (1/l, 0/o, ...)
    can't defeat a match OR fake one."""
    t = _fold(name)
    n = len(t)
    others = _other_names(name, roster)
    cands = [w for w in words
             if w.cy <= a.list_y_max and w.cx < m.name_max_x
             and any(c.isalpha() for c in w.text)]

    # 1) exact (folded)
    for w in cands:
        wt = _fold(w.text)
        if wt == t and _roster_gate(wt, 0, others):
            return w
    # 2) prefix (>=3) / substring (>=4) - OCR clipping/merging
    for w in cands:
        wt = _fold(w.text)
        if wt and ((n >= 3 and wt.startswith(t)) or (n >= 4 and t in wt)):
            if _roster_gate(wt, _edit_dist(t, wt), others):
                return w
    # 3) fuzzy: closest by edit distance, within tolerance and UNambiguously best
    tol = _tol(n)
    best_w = None
    best_d = second_d = 99
    for w in cands:
        wt = _fold(w.text)
        if not wt or abs(len(wt) - n) > tol:
            continue
        d = _edit_dist(t, wt)
        if d < best_d:
            second_d, best_d, best_w = best_d, d, w
        elif d < second_d:
            second_d = d
    if (best_w is not None and best_d <= tol and best_d < second_d
            and _roster_gate(_fold(best_w.text), best_d, others)):
        return best_w
    return None


def _checkbox_state(img, cy: int, m: Metrics) -> Optional[bool]:
    """Read the start/stop checkbox of the row at `cy` from pixels: True =
    ticked (instance running), False = unticked, None = ambiguous (callers
    must not act on None).

    Samples only the checkbox INTERIOR so a selected row's blue highlight
    around the box can't skew the reading. Calibrated on real captures:
    ticked interiors are a bright/saturated fill (bright >= 0.21, sat >= 0.48
    measured), unticked interiors are uniformly dark (0.00/0.00) - the
    thresholds sit far from both clusters."""
    cx = round(BASE_CHECKBOX_X * m.scale)
    half = max(4, round(5 * m.scale))
    box = img.crop((max(0, cx - half), max(0, cy - half), cx + half, cy + half))
    raw = box.convert("RGB").tobytes()
    px = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
    if not px:
        return None
    n = len(px)
    bright = sum(1 for r, g, b in px if r + g + b > 380) / n
    sat = sum(1 for r, g, b in px if max(r, g, b) - min(r, g, b) > 40) / n
    if bright >= 0.10 or sat >= 0.15:
        return True
    if bright <= 0.04 and sat <= 0.06:
        return False
    return None


def _verify_row(img, w: Word, name: str, m: Metrics,
                roster: Optional[List[str]] = None) -> bool:
    """Confirm a matched row really shows the target name before it is acted
    on: crop just that row's name cell and re-OCR it at double magnification.

    Defends against one-shot OCR misreads (a digit read wrong at normal scale
    usually resolves correctly when magnified). A verification failure means
    "treat as not found" - callers must never click an unverified row."""
    pad = round(6 * m.scale)
    box = (0, max(0, w.y - pad),
           min(img.width, m.name_max_x + pad),
           min(img.height, w.y + w.h + pad))
    try:
        words2, _lines = ocr_image(img.crop(box), scale=min(8, m.ocr_scale * 2))
    except Exception:
        return False
    t = _fold(name)
    others = _other_names(name, roster)
    tol = _tol(len(t))
    for w2 in words2:
        wt = _fold(w2.text)
        if not wt:
            continue
        d = _edit_dist(t, wt)
        if d <= tol and _roster_gate(wt, d, others):
            return True
    return False


def _locate_row(win: ROKWindow, name: str, m: Metrics, a: Anchors,
                roster: Optional[List[str]] = None):
    """Page through the account list from the top until the target row is
    found AND verified (see _verify_row).

    Besides the gated primary match, NEAR-MISS candidates (within edit-distance
    tolerance but failing the roster gate) are given a second look: the roster
    gate rejects an OCR word that fits a sibling account equally well (e.g.
    'Piltongl' misread from 'Piltong1' is distance 1 from Piltong1/2/3 alike),
    so the high-magnification re-OCR in _verify_row - where the garbled digit
    usually resolves - makes the final, still-gated decision. Without this,
    sibling sets whose distinguishing digit misreads would be "not found".

    Returns (word, img, seen, error): `word` is the verified name-cell Word or
    None; `img` is the capture it was found in; `seen` is every list-row word
    encountered (diagnostics); `error` is a fatal reason (occlusion) or None."""
    t = _fold(name)
    tol = _tol(len(t))
    win.scroll_to_top(a.list_scroll)
    last_keys = None
    seen = set()
    for _ in range(18):      # ~18 pages * ~2-4 rows >> max account count
        img = win.capture()
        words, _lines = ocr_image(img, scale=m.ocr_scale)
        if not _has_anchors(words):
            return None, None, seen, "window occluded (no ROKBot anchors visible)"
        for w in words:
            if w.cy <= a.list_y_max and sum(c.isalpha() for c in w.text) >= 3:
                seen.add(w.text)   # >=3 letters: keep resource numbers out of diagnostics
        # candidates, best first: the gated match, then near-misses by distance
        cands: List[Word] = []
        nm = _find_name(words, name, m, a, roster)
        if nm is not None:
            cands.append(nm)
        near = []
        for w in words:
            if (w is not nm and w.cy <= a.list_y_max and w.cx < m.name_max_x
                    and any(c.isalpha() for c in w.text)):
                wt = _fold(w.text)
                if wt and abs(len(wt) - len(t)) <= tol:
                    d = _edit_dist(t, wt)
                    if d <= tol:
                        near.append((d, w.cy, w))
        near.sort(key=lambda x: (x[0], x[1]))
        cands.extend(w for _d, _cy, w in near[:3])
        for cand in cands:
            if _verify_row(img, cand, name, m, roster):
                return cand, img, seen, None
        if cands:
            print(f"[READER] {len(cands)} candidate(s) for '{name}' on this page "
                  f"failed high-scale verification - not clicking; continuing")
        keys = frozenset(_norm(w.text) for w in words
                         if w.cy <= a.list_y_max and w.cx < m.name_max_x
                         and any(c.isalpha() for c in w.text))
        if last_keys is not None and keys == last_keys:
            break            # view didn't change after scrolling -> bottom reached
        last_keys = keys
        win.scroll(*a.list_scroll, -2)   # page down ~2-4 rows (overlap, no skip)
    return None, None, seen, None


def _find_log_tab(words: List[Word], m: Metrics) -> Optional[Tuple[int, int]]:
    """Locate the 'ACTIVITY LOG' tab (right side) as a clickable point."""
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


def _log_lines_from_words(words: List[Word], m: Metrics, a: Anchors) -> List[str]:
    """Reconstruct ACTIVITY LOG lines from RIGHT-panel words only, grouped into
    rows by y.

    The OCR groups text by physical row, so a single OCR line mixes the left
    ACTIVITIES column and the right LOG column. We therefore drop everything left
    of the log panel and rebuild each log row from the remaining words.
    """
    log_words = sorted((w for w in words if w.x >= a.log_min_x), key=lambda w: (w.cy, w.x))
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
# Shared setup + main entries
# --------------------------------------------------------------------------
def _prepare_window(win: ROKWindow):
    """OCR the freshly prepared window and locate the layout anchors.
    Returns (anchors, error): anchors is None when error is set."""
    m = win.m                # text metrics for this window's monitor scale
    words, _lines = ocr_image(win.capture(), scale=m.ocr_scale)
    if not _has_anchors(words):
        return None, "window occluded (no ROKBot anchors visible)"
    anch = _find_anchors(words, m)
    if anch is None:
        return None, "ACTIVITY LOG tab not visible - enlarge the ROKBot window"
    return anch, None


def _not_found_error(name: str, seen) -> str:
    name_like = sorted({w for w in seen if any(c.isalpha() for c in w)})
    sample = ", ".join(name_like[:60])
    return f"account '{name}' not found/verified in list. names seen: {sample}"


def read_account_log(name: str, win: Optional[ROKWindow] = None,
                     keep_topmost: bool = False,
                     roster: Optional[List[str]] = None) -> LogReading:
    """Read one account's ACTIVITY LOG. `roster` (all real account names)
    hardens the name matching against sibling accounts - always pass it when
    available."""
    prev_dpi = set_thread_dpi_aware()
    win = win or ROKWindow()
    if not win.find():
        restore_thread_dpi(prev_dpi)
        return LogReading(name, False, error="ROKBot window not found")
    prepared = False
    try:
        win.prepare()
        prepared = True
        m = win.m
        anch, err = _prepare_window(win)
        if err:
            return LogReading(name, False, error=err)

        # 1) select the account: page from the top until the row is found AND
        #    verified, then click its NAME cell (selects the account).
        nm, img, seen, err = _locate_row(win, name, m, anch, roster)
        if err:
            return LogReading(name, False, error=err)
        if nm is None:
            try:
                win.capture().save(rf"C:\Users\binlo\rok_notfound_{name}.png")
            except Exception:
                pass
            return LogReading(name, False,
                              error=_not_found_error(name, seen) + " (png saved)")
        # The GUI checkbox is the truth about whether this instance is running.
        # If it's unticked, the state file that sent us here is out of sync -
        # report running=False and DON'T select/read (its log is naturally
        # stale and would only produce false freeze alerts).
        running = _checkbox_state(img, nm.cy, m)
        if running is False:
            return LogReading(name, False, running=False,
                              error="instance is NOT running (checkbox unticked) - "
                                    "state file out of sync with GUI")
        win.click_client(nm.cx, nm.cy)
        time.sleep(0.4)

        # 2) ensure ACTIVITY LOG tab is active
        words, _lines = ocr_image(win.capture(), scale=m.ocr_scale)
        tab = _find_log_tab(words, m)
        if tab:
            win.click_client(*tab)
            time.sleep(0.5)

        # 3) read the log panel. Rebuild log rows from RIGHT-panel words only
        #    (the OCR merges the left ACTIVITIES column onto the same rows).
        words, _lines = ocr_image(win.capture(), scale=m.ocr_scale)
        log_lines = _log_lines_from_words(words, m, anch)
        if not log_lines:
            return LogReading(name, False, error="no log lines read (panel empty or occluded)")

        latest = _latest_ts(log_lines)
        recent = log_lines[-6:]
        bad = sorted({s for s in BAD_STATES
                      if any(s in l.lower() for l in recent)})
        return LogReading(name, True, latest_ts=latest, lines=log_lines,
                          bad_states=bad, running=running)
    finally:
        # Drop the temporary topmost bit (window size/pos were never touched)
        # and restore this thread's DPI context (pool threads are reused).
        if prepared:
            try:
                win.restore_placement()
            except Exception:
                pass
        restore_thread_dpi(prev_dpi)


def click_account_checkbox(name: str, roster: Optional[List[str]] = None,
                           win: Optional[ROKWindow] = None,
                           dry_run: bool = False,
                           ensure: Optional[str] = None) -> dict:
    """Locate an account row by NAME and click its start/stop checkbox.

    This is the name-anchored replacement for the old fixed-coordinate
    start/stop clicking (y = base + step*index + scroll notches), which could
    silently hit the wrong row: the list's row pitch varies with display
    scaling, one wheel notch scrolls 1-2 rows (not exactly 1), and the
    process-wide DPI-awareness call it relied on silently failed. Here the row
    is found by OCR (roster-gated), re-verified at high magnification, and
    only then clicked - if the name can't be found and verified, we return an
    error and click NOTHING.

    `ensure` ('checked' for start, 'unchecked' for stop) makes the toggle
    direction-safe: if the checkbox already shows the desired end state (the
    state file was out of sync with the GUI), we DON'T click - a blind toggle
    would flip a running instance off / a stopped one on. After a real click
    the checkbox is re-read to confirm it reached the desired state.

    Returns {'success', 'error', 'matched_text', 'clicked_at', 'noop',
    'checkbox'}. With dry_run=True everything runs except the click.
    """
    res = {"success": False, "error": None, "matched_text": None,
           "clicked_at": None, "noop": False, "checkbox": None}
    prev_dpi = set_thread_dpi_aware()
    win = win or ROKWindow()
    if not win.find():
        restore_thread_dpi(prev_dpi)
        return {**res, "error": "ROKBot window not found"}
    prepared = False
    try:
        win.prepare()
        prepared = True
        m = win.m
        anch, err = _prepare_window(win)
        if err:
            return {**res, "error": err}
        nm, img, seen, err = _locate_row(win, name, m, anch, roster)
        if err:
            return {**res, "error": err}
        if nm is None:
            try:
                win.capture().save(rf"C:\Users\binlo\rok_notfound_{name}.png")
            except Exception:
                pass
            return {**res, "error": _not_found_error(name, seen) + " (png saved)"}
        res["matched_text"] = nm.text
        cur = _checkbox_state(img, nm.cy, m)
        res["checkbox"] = cur
        cb = (round(BASE_CHECKBOX_X * m.scale), nm.cy)
        if ensure == "checked" and cur is True:
            return {**res, "success": True, "noop": True,
                    "error": None}   # already running per GUI - clicking would STOP it
        if ensure == "unchecked" and cur is False:
            return {**res, "success": True, "noop": True,
                    "error": None}   # already stopped per GUI - clicking would START it
        if dry_run:
            return {**res, "success": True, "clicked_at": cb}
        win.click_client(*cb)
        time.sleep(0.5)
        res["clicked_at"] = cb
        # Post-click confirmation: the checkbox must now show the desired state.
        if ensure in ("checked", "unchecked"):
            after = _checkbox_state(win.capture(), nm.cy, m)
            res["checkbox"] = after
            want = (ensure == "checked")
            if after is not None and after != want:
                return {**res, "error": f"clicked, but checkbox reads "
                        f"{'ticked' if after else 'unticked'} instead of "
                        f"{'ticked' if want else 'unticked'} - inspect the GUI"}
        return {**res, "success": True}
    finally:
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
    ap.add_argument("--locate", metavar="NAME",
                    help="locate NAME's row with roster-gated matching + high-scale "
                         "verification, print where the checkbox click WOULD land "
                         "(no click)")
    ap.add_argument("--accounts-json",
                    default=r"C:\Program Files (x86)\Whalebots\Apps\rise-of-kingdoms-bot"
                            r"\Settings\Accounts.json",
                    help="Accounts.json to load the roster from (for --locate)")
    args = ap.parse_args()

    if args.locate:
        import json as _json
        roster = []
        try:
            _data = _json.loads(open(args.accounts_json, encoding="utf-8-sig").read())
            roster = [a.get("emuInfo", {}).get("name", "") for a in _data]
            roster = [r for r in roster if r]
        except Exception as e:
            print(f"(roster unavailable: {e} — matching without roster gate)")
        print(f"roster ({len(roster)}): {roster}")
        res = click_account_checkbox(args.locate, roster=roster, dry_run=True)
        cb = res.get("checkbox")
        print(f"success     : {res['success']}")
        print(f"matched_text: {res['matched_text']}")
        print(f"would click : {res['clicked_at']}")
        print(f"checkbox    : {cb} ({'RUNNING' if cb else 'NOT running' if cb is False else 'unknown'})")
        print(f"error       : {res['error']}")
        raise SystemExit(0 if res["success"] else 1)

    if args.dump:
        set_thread_dpi_aware()
        w = ROKWindow()
        if not w.find():
            print("ROKBot window not found"); raise SystemExit(1)
        w.prepare()
        cap = w.capture()
        cap.save(r"C:\Users\binlo\rok_ocr_dump.png")
        words, lines = ocr_image(cap, scale=w.m.ocr_scale)
        anch = _find_anchors(words, w.m)
        heights = sorted(wd.h for wd in words) if words else []
        med_h = heights[len(heights) // 2] if heights else 0
        out = r"C:\Users\binlo\rok_ocr_dump.txt"
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(f"monitor scale: {w.m.scale:.2f}  | metrics: {w.m}\n")
            fh.write(f"anchors: {anch}\n")
            fh.write(f"client capture size: {cap.size}  | median text height: {med_h}px "
                     f"(original pixels; OCR upscaled {w.m.ocr_scale}x)\n")
            fh.write(f"--- {len(words)} words (text @ client cx,cy, h=height) ---\n")
            for wd in sorted(words, key=lambda z: (z.cy, z.cx)):
                fh.write(f"  ({wd.cx:>4},{wd.cy:>4}) h={wd.h:>2}  '{wd.text}'\n")
        print(f"scale {w.m.scale:.2f}, anchors {anch}, {len(words)} words, "
              f"client {cap.size}, median text height {med_h}px; wrote {out} (+ .png)")
        w.restore_placement()
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
