"""
Core module for WhaleBots automation platform.

This module contains the core functionality for state management and UI automation.
"""

from .state import (
    EmulatorStateManager, EmulatorState, EmulatorInfo, StateSummary,
    create_state_manager, IStateValidator, StateValidator
)
from .emulator_action import (
    WindowController, WindowInfo, IWindowFinder, IClickHandler, IScrollHandler,
    RegexWindowFinder, HybridClickHandler, MouseScrollHandler
)

__all__ = [
    # State management
    "EmulatorStateManager",
    "EmulatorState",
    "EmulatorInfo",
    "StateSummary",
    "create_state_manager",
    "IStateValidator",
    "StateValidator",

    # UI automation
    "WindowController",
    "WindowInfo",
    "IWindowFinder",
    "IClickHandler",
    "IScrollHandler",
    "RegexWindowFinder",
    "HybridClickHandler",
    "MouseScrollHandler"
]