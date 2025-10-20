# -*- coding: utf-8 -*-
"""
WinAppController - Compact SOLID Design

Tập trung vào 3 tính năng chính:
- Tìm cửa sổ theo regex
- Click tại tọa độ
- Scroll tại tọa độ

Ví dụ:
    app = WindowController.create(r".*Notepad.*")
    app.attach()
    app.click(50, 50)
    app.scroll(50, 50, up=5)
"""

import re
import time
import ctypes
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional

import win32con
import win32gui
import win32api


# ============ INTERFACES ============

class IWindowFinder(ABC):
    @abstractmethod
    def find(self, pattern: str) -> List[int]:
        pass


class IClickHandler(ABC):
    @abstractmethod
    def click(self, hwnd: int, x: int, y: int) -> bool:
        pass


class IScrollHandler(ABC):
    @abstractmethod
    def scroll(self, hwnd: int, x: int, y: int, up: int, down: int) -> bool:
        pass


# ============ IMPLEMENTATIONS ============

class RegexWindowFinder(IWindowFinder):
    """Tìm cửa sổ theo regex pattern"""
    
    def find(self, pattern: str) -> List[int]:
        results = []
        
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and re.search(pattern, title, re.IGNORECASE):
                    results.append(hwnd)
        
        win32gui.EnumWindows(callback, None)
        return results


class HybridClickHandler(IClickHandler):
    """Click: thử message trước, fallback sang mouse"""
    
    def __init__(self, delay: float = 0.05):
        self.delay = delay
    
    def click(self, hwnd: int, x: int, y: int) -> bool:
        # Thử message
        try:
            lparam = win32api.MAKELONG(x, y)
            win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            return True
        except:
            pass
        
        # Fallback: mouse
        try:
            self._bring_to_front(hwnd)
            sx, sy = win32gui.ClientToScreen(hwnd, (x, y))
            win32api.SetCursorPos((sx, sy))
            time.sleep(self.delay)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True
        except Exception as e:
            print(f"Click failed: {e}")
            return False
    
    @staticmethod
    def _bring_to_front(hwnd: int):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.05)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except:
            pass


class MouseScrollHandler(IScrollHandler):
    """Scroll bằng mouse event"""
    
    def __init__(self, delay: float = 0.05):
        self.delay = delay
    
    def scroll(self, hwnd: int, x: int, y: int, up: int, down: int) -> bool:
        try:
            self._bring_to_front(hwnd)
            sx, sy = win32gui.ClientToScreen(hwnd, (x, y))
            win32api.SetCursorPos((sx, sy))
            time.sleep(self.delay)
            
            for _ in range(up):
                win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, 120, 0)
                time.sleep(self.delay)
            
            for _ in range(down):
                win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, -120, 0)
                time.sleep(self.delay)
            
            return True
        except Exception as e:
            print(f"Scroll failed: {e}")
            return False
    
    @staticmethod
    def _bring_to_front(hwnd: int):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.05)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except:
            pass


# ============ CONTROLLER ============

class WindowController:
    """Controller chính - tập trung vào 3 tính năng: find, click, scroll"""
    
    def __init__(
        self,
        finder: IWindowFinder,
        clicker: IClickHandler,
        scroller: IScrollHandler,
        pattern: str
    ):
        self.finder = finder
        self.clicker = clicker
        self.scroller = scroller
        self.pattern = pattern
        self.hwnd: Optional[int] = None
    
    def attach(self, index: int = 0) -> int:
        """Tìm và gắn vào cửa sổ. Nếu nhiều cửa sổ match, chọn theo index (mặc định 0)"""
        matches = self.finder.find(self.pattern)
        if not matches:
            raise RuntimeError(f"Không tìm thấy cửa sổ: {self.pattern}")
        if index >= len(matches):
            raise RuntimeError(f"Index {index} vượt quá {len(matches)} cửa sổ")
        
        self.hwnd = matches[index]
        return self.hwnd
    
    def click(self, x: int, y: int) -> bool:
        """Click tại tọa độ client (x, y)"""
        if not self.hwnd:
            raise RuntimeError("Chưa gọi attach()")
        return self.clicker.click(self.hwnd, x, y)
    
    def scroll(self, x: int, y: int, *, up: int = 0, down: int = 0) -> bool:
        """Scroll tại tọa độ client (x, y)"""
        if not self.hwnd:
            raise RuntimeError("Chưa gọi attach()")
        return self.scroller.scroll(self.hwnd, x, y, up, down)
    
    def get_info(self) -> dict:
        """Lấy thông tin cửa sổ"""
        if not self.hwnd:
            raise RuntimeError("Chưa gọi attach()")
        
        title = win32gui.GetWindowText(self.hwnd)
        win_rect = win32gui.GetWindowRect(self.hwnd)
        client_rect = win32gui.GetClientRect(self.hwnd)
        
        return {
            "hwnd": hex(self.hwnd),
            "title": title,
            "window_rect": win_rect,
            "client_rect": client_rect
        }
    
    @staticmethod
    def create(pattern: str, delay: float = 0.05) -> 'WindowController':
        """Factory method tạo controller với config mặc định"""
        # Enable DPI awareness
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass
        
        return WindowController(
            finder=RegexWindowFinder(),
            clicker=HybridClickHandler(delay),
            scroller=MouseScrollHandler(delay),
            pattern=pattern
        )


# ============ USAGE ============

if __name__ == "__main__":
    # Tìm Notepad và tương tác
    app = WindowController.create(r".*Notepad.*")
    app.attach()
    
    print(app.get_info())
    
    # Click tại (50, 50)
    app.click(50, 50)
    
    # Scroll lên 5 lần tại (50, 50)
    app.scroll(50, 50, up=5)
    
    # Scroll xuống 3 lần tại (50, 50)
    app.scroll(50, 50, down=3)