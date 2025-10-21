"""
Window controller module for WhaleBots automation platform.

This module provides a SOLID-designed window automation system with proper
error handling, logging, and security validation for UI operations.
"""
# === Lenient JSON utilities (auto-injected) ==================================
# Purpose: allow reading large/irregular JSON files WITHOUT modifying the files.
# - Handles UTF-8 BOM
# - Strips // line comments and /* block comments */
# - Removes trailing commas before "]" or "}"
# - Falls back to JSON Lines (one JSON per line) if standard parse still fails
# Usage:
#   data = load_json_lenient("/path/to/file.json")
#   subset = select_keys(data, {"emuInfo": {"name", "deviceId", "vmName"}})
#
# Injected on: 2025-10-21T16:49:25.857689

import re as _re_json_utils
import json as _json_json_utils
from pathlib import Path as _Path_json_utils
from typing import Any as _Any_json_utils, Mapping as _Mapping_json_utils

def _strip_bom(s: str) -> str:
    return s.lstrip("\ufeff")

def _strip_comments(s: str) -> str:
    res = []
    i, n = 0, len(s)
    in_str = False
    str_ch = ''
    in_line_comment = False
    in_block_comment = False
    while i < n:
        ch = s[i]
        nxt = s[i+1] if i+1 < n else ''
        if in_line_comment:
            if ch == '\n':
                in_line_comment = False
                res.append(ch)
            i += 1
            continue
        if in_block_comment:
            if ch == '*' and nxt == '/':
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_str:
            res.append(ch)
            if ch == '\\':
                if i+1 < n:
                    res.append(s[i+1])
                    i += 2
                    continue
            elif ch == str_ch:
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            res.append(ch)
            i += 1
            continue
        if ch == '/' and nxt == '/':
            in_line_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '*':
            in_block_comment = True
            i += 2
            continue
        res.append(ch)
        i += 1
    return ''.join(res)

def _strip_trailing_commas(s: str) -> str:
    return _re_json_utils.sub(r',\s*([}\]])', r'\1', s)

def _try_json_lines(text: str):
    arr = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            arr.append(_json_json_utils.loads(ln))
        except Exception:
            return None
    return arr

def load_json_lenient(path: str | _Path_json_utils) -> _Any_json_utils:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        raw = f.read()
    text = _strip_bom(raw)
    cleaned = _strip_trailing_commas(_strip_comments(text))
    try:
        return _json_json_utils.loads(cleaned)
    except Exception:
        jl = _try_json_lines(text)
        if jl is not None:
            return jl
        return _json_json_utils.loads(cleaned)  # will raise

def select_keys(data: _Any_json_utils, schema: _Mapping_json_utils[str, _Any_json_utils] | None) -> _Any_json_utils:
    if schema is None:
        return data
    if isinstance(data, list):
        return [select_keys(x, schema) for x in data]
    if isinstance(data, dict):
        out = {}
        if isinstance(schema, set):
            for k in schema:
                if k in data:
                    out[k] = data[k]
            return out
        if isinstance(schema, dict):
            for k, sub in schema.items():
                if k in data:
                    out[k] = select_keys(data[k], sub)
            return out
    return data

# =============================================================================


import re
import time
import ctypes
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

try:
    import win32con
    import win32gui
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

try:
    from ..config import UIConfiguration
    from ..exceptions import (
        WindowError, WindowNotFoundError, UICoordinateError,
        DependencyError, TimeoutError, SecurityError
    )
    from ..logger import get_logger, log_performance
except ImportError:
    # Fallback for running tests directly
    from whalebots_automation.config import UIConfiguration
    from whalebots_automation.exceptions import (
        WindowError, WindowNotFoundError, UICoordinateError,
        DependencyError, TimeoutError, SecurityError
    )
    from whalebots_automation.logger import get_logger, log_performance


@dataclass
class WindowInfo:
    """Container for window information."""
    hwnd: int
    title: str
    window_rect: Tuple[int, int, int, int]
    client_rect: Tuple[int, int, int, int]
    is_visible: bool = True
    is_minimized: bool = False


# ============ INTERFACES ============

class IWindowFinder(ABC):
    """Interface for window finding operations."""

    @abstractmethod
    def find(self, pattern: str) -> List[int]:
        """
        Find windows matching the given pattern.

        Args:
            pattern: Regular expression pattern to match window titles

        Returns:
            List of window handles (hwnd)
        """
        pass


class IClickHandler(ABC):
    """Interface for click operations."""

    @abstractmethod
    def click(self, hwnd: int, x: int, y: int) -> bool:
        """
        Perform a click at the specified coordinates.

        Args:
            hwnd: Window handle
            x: X coordinate (client-relative)
            y: Y coordinate (client-relative)

        Returns:
            True if click was successful, False otherwise
        """
        pass


class IScrollHandler(ABC):
    """Interface for scroll operations."""

    @abstractmethod
    def scroll(self, hwnd: int, x: int, y: int, up: int, down: int) -> bool:
        """
        Perform scrolling at the specified coordinates.

        Args:
            hwnd: Window handle
            x: X coordinate (client-relative)
            y: Y coordinate (client-relative)
            up: Number of scroll-up operations
            down: Number of scroll-down operations

        Returns:
            True if scroll was successful, False otherwise
        """
        pass


# ============ IMPLEMENTATIONS ============

class RegexWindowFinder(IWindowFinder):
    """Window finder using regex pattern matching."""

    def __init__(self, config: UIConfiguration):
        """
        Initialize regex window finder.

        Args:
            config: UI configuration
        """
        if not WIN32_AVAILABLE:
            raise DependencyError("win32gui modules")

        self.config = config
        self.logger = get_logger(f"{__name__}.RegexWindowFinder")

    @log_performance()
    def find(self, pattern: str) -> List[int]:
        """
        Find windows matching regex pattern.

        Args:
            pattern: Regular expression pattern

        Returns:
            List of matching window handles

        Raises:
            WindowError: If window search fails
        """
        try:
            results = []

            def callback(hwnd, _):
                """Callback function for EnumWindows."""
                try:
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if title and re.search(pattern, title, re.IGNORECASE):
                            results.append(hwnd)
                            self.logger.debug(f"Found window: {title} (hwnd: {hex(hwnd)})")
                except Exception as e:
                    self.logger.warning(f"Error checking window {hwnd}: {e}")

            win32gui.EnumWindows(callback, None)

            self.logger.info(f"Found {len(results)} windows matching pattern: {pattern}")
            return results

        except Exception as e:
            raise WindowError(f"Failed to search for windows: {e}")


class HybridClickHandler(IClickHandler):
    """
    Click handler that tries message-based clicking first,
    then falls back to mouse-based clicking.
    """

    def __init__(self, config: UIConfiguration, security_config=None):
        """
        Initialize hybrid click handler.

        Args:
            config: UI configuration
            security_config: Security configuration (optional)
        """
        if not WIN32_AVAILABLE:
            raise DependencyError("win32api modules")

        self.config = config
        self.security_config = security_config
        self.logger = get_logger(f"{__name__}.HybridClickHandler")

    def _validate_coordinates(self, x: int, y: int) -> None:
        """
        Validate click coordinates for security.

        Args:
            x: X coordinate
            y: Y coordinate

        Raises:
            UICoordinateError: If coordinates are invalid
        """
        # Use security config if available, otherwise skip validation
        if (self.security_config and
            hasattr(self.security_config, 'validate_coordinates') and
            self.security_config.validate_coordinates):

            if not (self.security_config.min_coordinate_value <= x <= self.security_config.max_coordinate_value):
                raise UICoordinateError(
                    f"X coordinate out of bounds: {x}",
                    x=x, y=y
                )
            if not (self.security_config.min_coordinate_value <= y <= self.security_config.max_coordinate_value):
                raise UICoordinateError(
                    f"Y coordinate out of bounds: {y}",
                    x=x, y=y
                )

    @log_performance()
    def click(self, hwnd: int, x: int, y: int) -> bool:
        """
        Perform click using hybrid approach.

        Args:
            hwnd: Window handle
            x: X coordinate (client-relative)
            y: Y coordinate (client-relative)

        Returns:
            True if click was successful, False otherwise

        Raises:
            UICoordinateError: If coordinates are invalid
            WindowError: If click operation fails
        """
        self._validate_coordinates(x, y)

        self.logger.debug(f"Attempting click at ({x}, {y}) on window {hex(hwnd)}")

        # Try message-based click first (more reliable and less intrusive)
        if self._try_message_click(hwnd, x, y):
            self.logger.debug(f"Message-based click successful at ({x}, {y})")
            return True

        # Fall back to mouse-based click
        if self._try_mouse_click(hwnd, x, y):
            self.logger.debug(f"Mouse-based click successful at ({x}, {y})")
            return True

        raise WindowError(f"All click methods failed for window {hex(hwnd)} at ({x}, {y})")

    def _try_message_click(self, hwnd: int, x: int, y: int) -> bool:
        """
        Try message-based clicking with SendMessage.

        NOTE: Message-based clicks often DON'T WORK for emulator/game windows.
        Can be controlled via config.use_message_based_click.

        Args:
            hwnd: Window handle
            x: X coordinate
            y: Y coordinate

        Returns:
            True if successful, False otherwise
        """
        # Check config to see if message-based click should be used
        if not self.config.use_message_based_click or self.config.force_physical_mouse:
            self.logger.debug(f"Message-based click disabled by config (force_physical_mouse={self.config.force_physical_mouse})")
            return False
        
        # Try SendMessage (for Windows applications like WhaleBots control panel)
        try:
            lparam = win32api.MAKELONG(x, y)
            win32api.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(self.config.click_delay)
            win32api.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            self.logger.debug(f"SendMessage click attempted at ({x}, {y})")
            return True
        except Exception as e:
            self.logger.debug(f"SendMessage click failed: {e}")
            return False

    def _try_mouse_click(self, hwnd: int, x: int, y: int) -> bool:
        """
        Try mouse-based clicking using physical mouse events.
        This is the most reliable method for emulator/game windows.

        Args:
            hwnd: Window handle
            x: X coordinate (client-relative)
            y: Y coordinate (client-relative)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Bring window to front and ensure it's active
            self._bring_to_front(hwnd)
            time.sleep(0.15)  # Wait for window to come to front (increased delay)

            # Verify window is in foreground (critical for emulators)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    foreground = win32gui.GetForegroundWindow()
                    if foreground == hwnd:
                        break
                    
                    self.logger.debug(f"Window not in foreground (attempt {attempt+1}/{max_retries}), retrying...")
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.1)
                except Exception as e:
                    self.logger.debug(f"SetForegroundWindow failed: {e}")
                    if attempt == max_retries - 1:
                        self.logger.warning(f"Could not bring window to foreground, continuing anyway...")

            # Convert client coordinates to screen coordinates
            sx, sy = win32gui.ClientToScreen(hwnd, (x, y))
            
            self.logger.debug(f"Client coords: ({x}, {y}) -> Screen coords: ({sx}, {sy})")

            # Set cursor position
            win32api.SetCursorPos((sx, sy))
            time.sleep(self.config.click_delay)

            # Perform click with physical mouse events
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(self.config.click_delay)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

            self.logger.debug(f"Mouse click completed at screen ({sx}, {sy})")
            return True

        except Exception as e:
            self.logger.error(f"Mouse-based click failed: {e}")
            return False

    @staticmethod
    def _bring_to_front(hwnd: int) -> None:
        """
        Bring window to front safely.

        Args:
            hwnd: Window handle
        """
        try:
            # Restore window if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            time.sleep(0.05)

            # Set as foreground window
            win32gui.SetForegroundWindow(hwnd)

        except Exception:
            # Some windows resist being brought to front, which is normal
            pass


class MouseScrollHandler(IScrollHandler):
    def _send_scroll_direct(self, hwnd: int, x: int, y: int, amount: int) -> bool:
        """Send scroll directly using SendInput."""
        try:
            import ctypes
            from ctypes import wintypes




            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [
                    ("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
                ]

            class INPUT(ctypes.Structure):
                class _INPUT(ctypes.Union):
                    _fields_ = [("mi", MOUSEINPUT)]
                _anonymous_ = ("_input",)
                _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]

            INPUT_MOUSE = 0
            MOUSEEVENTF_WHEEL = 0x0800

            scroll_input = INPUT(
                type=INPUT_MOUSE,
                _input=INPUT._INPUT(mi=MOUSEINPUT(
                    dx=0, dy=0, mouseData=amount,
                    dwFlags=MOUSEEVENTF_WHEEL,
                    time=0, dwExtraInfo=None
                ))
            )

            size = ctypes.sizeof(INPUT)
            result = ctypes.windll.user32.SendInput(1, ctypes.byref(scroll_input), size)
            return result == 1
        except:
            return False


    """Scroll handler using mouse wheel events."""

    def __init__(self, config: UIConfiguration, security_config=None):
        """
        Initialize mouse scroll handler.

        Args:
            config: UI configuration
            security_config: Security configuration (optional)
        """
        if not WIN32_AVAILABLE:
            raise DependencyError("win32api modules")

        self.config = config
        self.security_config = security_config
        self.logger = get_logger(f"{__name__}.MouseScrollHandler")

    def _validate_coordinates(self, x: int, y: int) -> None:
        """
        Validate scroll coordinates for security.

        Args:
            x: X coordinate
            y: Y coordinate

        Raises:
            UICoordinateError: If coordinates are invalid
        """
        # Use security config if available, otherwise skip validation
        if (self.security_config and
            hasattr(self.security_config, 'validate_coordinates') and
            self.security_config.validate_coordinates):

            if not (self.security_config.min_coordinate_value <= x <= self.security_config.max_coordinate_value):
                raise UICoordinateError(
                    f"X coordinate out of bounds: {x}",
                    x=x, y=y
                )
            if not (self.security_config.min_coordinate_value <= y <= self.security_config.max_coordinate_value):
                raise UICoordinateError(
                    f"Y coordinate out of bounds: {y}",
                    x=x, y=y
                )

    @log_performance()
    def scroll(self, hwnd: int, x: int, y: int, up: int, down: int) -> bool:
        """
        Perform scrolling operations.

        Args:
            hwnd: Window handle
            x: X coordinate (client-relative)
            y: Y coordinate (client-relative)
            up: Number of scroll-up operations
            down: Number of scroll-down operations

        Returns:
            True if scroll was successful, False otherwise

        Raises:
            UICoordinateError: If coordinates are invalid
            WindowError: If scroll operation fails
        """
        self._validate_coordinates(x, y)

        if up <= 0 and down <= 0:
            raise WindowError("No scroll operations specified (up and down both zero)")

        self.logger.debug(f"Scrolling at ({x}, {y}): up={up}, down={down}")

        try:
            # Bring window to front and ensure it's active
            self._bring_to_front(hwnd)
            time.sleep(0.05)

            # Verify window is in foreground
            try:
                foreground = win32gui.GetForegroundWindow()
                if foreground != hwnd:
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.05)
            except:
                pass

            # Convert client coordinates to screen coordinates
            sx, sy = win32gui.ClientToScreen(hwnd, (x, y))

            # Try to set cursor position (with fallback)
            cursor_moved = False
            try:
                win32api.SetCursorPos((sx, sy))
                time.sleep(self.config.scroll_delay)
                cursor_moved = True
            except:
                # If cursor move fails, try direct scroll at window center
                self.logger.debug(f"Failed to move cursor, using direct scroll")

            # Perform scroll-up operations
            for i in range(up):
                if cursor_moved:
                    win32api.mouse_event(
                        win32con.MOUSEEVENTF_WHEEL,
                        0, 0,
                        self.config.scroll_wheel_amount,
                        0
                    )
                else:
                    # Use SendMessage as fallback
                    lparam = win32api.MAKELONG(x, y)
                    win32api.SendMessage(hwnd, win32con.WM_MOUSEWHEEL, 
                                       win32api.MAKELONG(0, self.config.scroll_wheel_amount), 
                                       lparam)
                time.sleep(self.config.scroll_delay)

            # Perform scroll-down operations
            for i in range(down):
                if cursor_moved:
                    win32api.mouse_event(
                        win32con.MOUSEEVENTF_WHEEL,
                        0, 0,
                        -self.config.scroll_wheel_amount,
                        0
                    )
                else:
                    # Use SendMessage as fallback
                    lparam = win32api.MAKELONG(x, y)
                    win32api.SendMessage(hwnd, win32con.WM_MOUSEWHEEL, 
                                       win32api.MAKELONG(0, -self.config.scroll_wheel_amount), 
                                       lparam)
                time.sleep(self.config.scroll_delay)

            self.logger.debug(f"Scrolling completed: up={up}, down={down}")
            return True

        except Exception as e:
            raise WindowError(f"Scroll operation failed: {e}")

    @staticmethod
    def _bring_to_front(hwnd: int) -> None:
        """
        Bring window to front safely.

        Args:
            hwnd: Window handle
        """
        try:
            # Restore window if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            time.sleep(0.05)

            # Set as foreground window
            win32gui.SetForegroundWindow(hwnd)

        except Exception:
            # Some windows resist being brought to front, which is normal
            pass


# ============ CONTROLLER ============

class WindowController:
    """
    Main window controller with SOLID design principles.

    Provides a clean interface for window automation operations with
    proper error handling, logging, and security validation.
    """

    def __init__(
        self,
        finder: IWindowFinder,
        clicker: IClickHandler,
        scroller: IScrollHandler,
        pattern: str,
        config: UIConfiguration
    ):
        """
        Initialize window controller.

        Args:
            finder: Window finder implementation
            clicker: Click handler implementation
            scroller: Scroll handler implementation
            pattern: Window title pattern
            config: UI configuration
        """
        self.finder = finder
        self.clicker = clicker
        self.scroller = scroller
        self.pattern = pattern
        self.config = config
        self.hwnd: Optional[int] = None
        self.logger = get_logger(f"{__name__}.WindowController")

        self.logger.info(f"WindowController initialized with pattern: {pattern}")

    @log_performance()
    def attach(self, index: int = 0, timeout: Optional[float] = None) -> int:
        """
        Find and attach to a window matching the pattern.

        Args:
            index: Index of matching window to select (0 = first match)
            timeout: Timeout in seconds (uses config default if None)

        Returns:
            Window handle

        Raises:
            WindowNotFoundError: If no matching window is found
            TimeoutError: If operation times out
            WindowError: If attachment fails
        """
        timeout = timeout or self.config.operation_timeout
        start_time = time.time()

        self.logger.info(f"Searching for window pattern: {self.pattern} (index: {index})")

        while time.time() - start_time < timeout:
            try:
                matches = self.finder.find(self.pattern)

                if not matches:
                    self.logger.debug(f"No windows found, retrying...")
                    time.sleep(0.5)
                    continue

                if index >= len(matches):
                    raise WindowError(
                        f"Index {index} out of range (found {len(matches)} windows)"
                    )

                self.hwnd = matches[index]
                
                # Restore window if minimized
                if win32gui.IsIconic(self.hwnd):
                    self.logger.info(f"Window is minimized, restoring...")
                    win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                    time.sleep(0.3)  # Wait for window to restore
                
                self.logger.info(f"Attached to window {hex(self.hwnd)} (index: {index})")
                return self.hwnd

            except Exception as e:
                if isinstance(e, (WindowNotFoundError, WindowError)):
                    raise
                self.logger.warning(f"Error during attach attempt: {e}")
                time.sleep(0.5)

        raise TimeoutError("Window attachment", timeout)

    def click(self, x: int, y: int) -> bool:
        """
        Perform click at specified coordinates.

        Args:
            x: X coordinate (client-relative)
            y: Y coordinate (client-relative)

        Returns:
            True if click was successful

        Raises:
            WindowError: If not attached or click fails
        """
        if not self.hwnd:
            raise WindowError("Not attached to any window - call attach() first")

        operation_id = self.logger.log_operation_start(
            "click",
            hwnd=hex(self.hwnd),
            x=x, y=y
        )

        try:
            result = self.clicker.click(self.hwnd, x, y)
            self.logger.log_operation_end(operation_id, success=result)
            return result

        except Exception as e:
            self.logger.log_operation_end(operation_id, success=False)
            raise

    def scroll(self, x: int, y: int, *, up: int = 0, down: int = 0) -> bool:
        """
        Perform scroll at specified coordinates.

        Args:
            x: X coordinate (client-relative)
            y: Y coordinate (client-relative)
            up: Number of scroll-up operations
            down: Number of scroll-down operations

        Returns:
            True if scroll was successful

        Raises:
            WindowError: If not attached or scroll fails
        """
        if not self.hwnd:
            raise WindowError("Not attached to any window - call attach() first")

        operation_id = self.logger.log_operation_start(
            "scroll",
            hwnd=hex(self.hwnd),
            x=x, y=y,
            up=up, down=down
        )

        try:
            result = self.scroller.scroll(self.hwnd, x, y, up, down)
            self.logger.log_operation_end(operation_id, success=result)
            return result

        except Exception as e:
            self.logger.log_operation_end(operation_id, success=False)
            raise

    def get_info(self) -> WindowInfo:
        """
        Get information about the attached window.

        Returns:
            WindowInfo object with window details

        Raises:
            WindowError: If not attached to any window
        """
        if not self.hwnd:
            raise WindowError("Not attached to any window - call attach() first")

        try:
            title = win32gui.GetWindowText(self.hwnd)
            window_rect = win32gui.GetWindowRect(self.hwnd)
            client_rect = win32gui.GetClientRect(self.hwnd)
            is_visible = win32gui.IsWindowVisible(self.hwnd)
            is_minimized = win32gui.IsIconic(self.hwnd)

            return WindowInfo(
                hwnd=self.hwnd,
                title=title,
                window_rect=window_rect,
                client_rect=client_rect,
                is_visible=is_visible,
                is_minimized=is_minimized
            )

        except Exception as e:
            raise WindowError(f"Failed to get window info: {e}")

    def is_attached(self) -> bool:
        """Check if controller is attached to a window."""
        if not self.hwnd:
            return False

        try:
            # Check if window still exists and is valid
            return win32gui.IsWindow(self.hwnd)
        except:
            return False

    def detach(self) -> None:
        """Detach from the current window."""
        if self.hwnd:
            self.logger.info(f"Detaching from window {hex(self.hwnd)}")
            self.hwnd = None

    @staticmethod
    def create(pattern: str, config: Optional[UIConfiguration] = None, security_config=None) -> 'WindowController':
        """
        Factory method to create WindowController with default implementations.

        Args:
            pattern: Window title pattern
            config: UI configuration (uses default if None)
            security_config: Security configuration (optional)

        Returns:
            Configured WindowController instance

        Raises:
            DependencyError: If required dependencies are missing
        """
        if not WIN32_AVAILABLE:
            raise DependencyError("win32gui modules")

        config = config or UIConfiguration()

        # Enable DPI awareness for better coordinate handling
        try:
            # Try modern DPI awareness API first (Windows 10 1703+)
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            ctypes.windll.user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        except:
            try:
                # Fallback to Windows 8.1+ API
                ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
            except:
                try:
                    # Final fallback to old API
                    ctypes.windll.user32.SetProcessDPIAware()
                except:
                    pass

        return WindowController(
            finder=RegexWindowFinder(config),
            clicker=HybridClickHandler(config, security_config),
            scroller=MouseScrollHandler(config, security_config),
            pattern=pattern,
            config=config
        )