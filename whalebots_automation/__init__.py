"""
WhaleBots Automation Package

A comprehensive Python interface for managing the WhaleBots gaming automation platform.
Provides emulator detection, state management, process monitoring, and UI automation
with proper error handling, logging, and security validation.
"""

from .whalesbot import WhaleBots, create_whalesbot, ProcessMonitor
from .core.state import (
    EmulatorStateManager, EmulatorState, EmulatorInfo, StateSummary,
    create_state_manager
)
from .core.emulator_action import WindowController, WindowInfo
from .config import (
    WhaleBotsConfiguration, UIConfiguration, FileConfiguration,
    LoggingConfiguration, ProcessConfiguration, SecurityConfiguration,
    load_config, create_default_config
)
from .exceptions import (
    WhaleBotsError, ConfigurationError, FileOperationError, SecurityError,
    EmulatorError, EmulatorNotFoundError, EmulatorStateError,
    EmulatorAlreadyRunningError, EmulatorNotRunningError,
    ProcessError, WindowError, WindowNotFoundError, UICoordinateError,
    DependencyError, TimeoutError, ValidationError
)
from .logger import get_logger, setup_global_logging, WhaleBotsLogger
from .utils import SecureFileHandler, FileCache, BackupManager

# Package version
__version__ = "1.0.0"
__author__ = "WhaleBots Development Team"
__description__ = "WhaleBots Gaming Automation Platform"

# Public API
__all__ = [
    # Main classes
    "WhaleBots",
    "create_whalesbot",
    "ProcessMonitor",

    # State management
    "EmulatorStateManager",
    "EmulatorState",
    "EmulatorInfo",
    "StateSummary",
    "create_state_manager",

    # UI automation
    "WindowController",
    "WindowInfo",

    # Configuration
    "WhaleBotsConfiguration",
    "UIConfiguration",
    "FileConfiguration",
    "LoggingConfiguration",
    "ProcessConfiguration",
    "SecurityConfiguration",
    "load_config",
    "create_default_config",

    # Exceptions
    "WhaleBotsError",
    "ConfigurationError",
    "FileOperationError",
    "SecurityError",
    "EmulatorError",
    "EmulatorNotFoundError",
    "EmulatorStateError",
    "EmulatorAlreadyRunningError",
    "EmulatorNotRunningError",
    "ProcessError",
    "WindowError",
    "WindowNotFoundError",
    "UICoordinateError",
    "DependencyError",
    "TimeoutError",
    "ValidationError",

    # Logging
    "get_logger",
    "setup_global_logging",
    "WhaleBotsLogger",

    # Utilities
    "SecureFileHandler",
    "FileCache",
    "BackupManager",

    # Package info
    "__version__",
    "__author__",
    "__description__"
]