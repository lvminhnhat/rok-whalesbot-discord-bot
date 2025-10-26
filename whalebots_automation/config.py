"""
Configuration module for WhaleBots automation platform.

This module provides centralized configuration management with validation,
type safety, and environment-specific settings.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def _load_json_with_fallback(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Load JSON data supporting common UTF encodings."""
    path = Path(file_path)
    last_error: Optional[Exception] = None

    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            with open(path, "r", encoding=encoding) as file_obj:
                return json.load(file_obj)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    raise ValueError(f"Could not decode configuration file: {path}") from last_error


@dataclass
class UIConfiguration:
    """Configuration for UI automation settings."""

    # Window detection patterns
    window_title_pattern: str = r".*Rise of Kingdoms Bot.*"
    window_title: str = "Rise of Kingdoms Bot"

    # Click coordinates and spacing
    base_x_coordinate: int = 16
    base_y_coordinate: int = 15
    step_size: int = 20
    max_visible_items: int = 6

    # Timing settings
    click_delay: float = 0.2
    scroll_delay: float = 0.2
    attach_delay: float = 0.5
    operation_timeout: float = 30.0

    # Scroll settings
    scroll_wheel_amount: int = 120
    default_scroll_up: int = 40
    scroll_position_x: int = 50
    scroll_position_y: int = 50
    
    # Click method settings
    use_message_based_click: bool = False  # True = try SendMessage first, False = force physical mouse
    force_physical_mouse: bool = True  # True = always use mouse_event (most reliable)


@dataclass
class FileConfiguration:
    """Configuration for file operations and paths."""

    # Base paths
    base_path: Optional[str] = None

    # Relative paths
    apps_directory: str = "Apps"
    rise_of_kingdoms_bot_dir: str = "rise-of-kingdoms-bot"
    settings_directory: str = "Settings"

    # File names
    accounts_file: str = "Accounts.json"
    last_state_file: str = "last_state"

    # Backup settings
    enable_backups: bool = True
    backup_directory: str = "backups"
    max_backup_files: int = 10

    # File I/O settings
    file_encoding: str = "utf-8"
    cache_ttl_seconds: int = 30
    enable_file_cache: bool = True
    sanitize_file_paths: bool = True
    max_file_size_mb: int = 10

    @property
    def rise_of_kingdoms_path(self) -> str:
        """Get the full path to Rise of Kingdoms bot settings."""
        if self.base_path:
            return os.path.join(
                self.base_path,
                self.apps_directory,
                self.rise_of_kingdoms_bot_dir,
                self.settings_directory
            )
        return os.path.join(
            self.apps_directory,
            self.rise_of_kingdoms_bot_dir,
            self.settings_directory
        )

    @property
    def accounts_file_path(self) -> str:
        """Get the full path to the accounts file."""
        return os.path.join(self.rise_of_kingdoms_path, self.accounts_file)

    @property
    def last_state_file_path(self) -> str:
        """Get the full path to the last state file."""
        return os.path.join(self.rise_of_kingdoms_path, self.last_state_file)

    @property
    def backup_path(self) -> str:
        """Get the full path to the backup directory."""
        base = self.base_path if self.base_path else "."
        return os.path.join(base, self.backup_directory)


@dataclass
class LoggingConfiguration:
    """Configuration for logging settings."""

    # Log levels
    default_level: str = "INFO"
    debug_level: str = "DEBUG"

    # Log formatting
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"

    # File logging
    enable_file_logging: bool = True
    log_file_path: str = "logs/whalebots.log"
    max_log_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

    # Console logging
    enable_console_logging: bool = True


@dataclass
class ProcessConfiguration:
    """Configuration for process monitoring and management."""

    # Process detection
    enable_process_monitoring: bool = True
    process_check_interval: float = 1.0
    max_process_wait_time: float = 60.0

    # Memory settings
    memory_warning_threshold_mb: int = 1024
    memory_critical_threshold_mb: int = 2048

    # Process matching
    process_name_patterns: List[str] = field(default_factory=lambda: [
        "HD-Player.exe",  # BlueStacks
        "LdVBoxHeadless.exe",  # LDPlayer
        "Nox.exe",  # Nox Player
        "MEmu.exe"  # MEmu Player
    ])


@dataclass
class SecurityConfiguration:
    """Configuration for security settings."""

    # File security
    validate_file_encoding: bool = True
    sanitize_file_paths: bool = True
    max_file_size_mb: int = 100

    # Input validation
    validate_coordinates: bool = True
    max_coordinate_value: int = 10000
    min_coordinate_value: int = 0

    # Operation security
    require_confirmation_for_dangerous_operations: bool = False
    enable_operation_logging: bool = True


@dataclass
class WhaleBotsConfiguration:
    """Main configuration class for WhaleBots automation."""

    ui: UIConfiguration = field(default_factory=UIConfiguration)
    files: FileConfiguration = field(default_factory=FileConfiguration)
    logging: LoggingConfiguration = field(default_factory=LoggingConfiguration)
    process: ProcessConfiguration = field(default_factory=ProcessConfiguration)
    security: SecurityConfiguration = field(default_factory=SecurityConfiguration)

    # Environment settings
    environment: str = "production"
    debug_mode: bool = False

    def __post_init__(self):
        """Post-initialization validation and setup."""
        self._validate_configuration()
        self._setup_directories()

    def _validate_configuration(self) -> None:
        """Validate configuration values."""
        if self.ui.base_x_coordinate < 0 or self.ui.base_y_coordinate < 0:
            raise ValueError("UI coordinates must be non-negative")

        if self.ui.step_size <= 0:
            raise ValueError("Step size must be positive")

        if self.files.max_backup_files <= 0:
            raise ValueError("Max backup files must be positive")

        if self.ui.click_delay < 0 or self.ui.scroll_delay < 0:
            raise ValueError("Delays must be non-negative")

    def _setup_directories(self) -> None:
        """Create necessary directories."""
        if self.files.enable_backups:
            os.makedirs(self.files.backup_path, exist_ok=True)

        if self.logging.enable_file_logging:
            log_dir = os.path.dirname(self.logging.log_file_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

    @classmethod
    def from_file(cls, config_path: str) -> "WhaleBotsConfiguration":
        """
        Load configuration from a JSON file.

        Args:
            config_path: Path to the configuration JSON file

        Returns:
            WhaleBotsConfiguration instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
            ValueError: If configuration values are invalid
        """
        path = Path(config_path)

        if not path.exists():
            default_config = cls()
            default_config.save_to_file(config_path)
            return default_config

        config_data = _load_json_with_fallback(path)
        return cls.from_dict(config_data)

    @classmethod
    def from_dict(cls, config_data: Dict[str, Any]) -> "WhaleBotsConfiguration":
        """
        Create configuration from a dictionary.

        Args:
            config_data: Dictionary containing configuration values

        Returns:
            WhaleBotsConfiguration instance
        """
        # Extract nested configurations
        ui_config = UIConfiguration(**config_data.get('ui', {}))
        files_config = FileConfiguration(**config_data.get('files', {}))
        logging_config = LoggingConfiguration(**config_data.get('logging', {}))
        process_config = ProcessConfiguration(**config_data.get('process', {}))
        security_config = SecurityConfiguration(**config_data.get('security', {}))

        # Create main configuration
        main_config_data = {
            'ui': ui_config,
            'files': files_config,
            'logging': logging_config,
            'process': process_config,
            'security': security_config,
            'environment': config_data.get('environment', 'production'),
            'debug_mode': config_data.get('debug_mode', False)
        }

        return cls(**main_config_data)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to a dictionary.

        Returns:
            Dictionary representation of the configuration
        """
        return {
            'ui': self.ui.__dict__,
            'files': self.files.__dict__,
            'logging': self.logging.__dict__,
            'process': self.process.__dict__,
            'security': self.security.__dict__,
            'environment': self.environment,
            'debug_mode': self.debug_mode
        }

    def save_to_file(self, config_path: str) -> None:
        """
        Save configuration to a JSON file.

        Args:
            config_path: Path where to save the configuration file
        """
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def update_from_dict(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration values from a dictionary.

        Args:
            updates: Dictionary containing updated values
        """
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)

        # Re-validate after updates
        self._validate_configuration()
        self._setup_directories()


def create_default_config(base_path: Optional[str] = None) -> WhaleBotsConfiguration:
    """
    Create a default configuration instance.

    Args:
        base_path: Base path for the WhaleBots application

    Returns:
        Default WhaleBotsConfiguration instance
    """
    config = WhaleBotsConfiguration()

    if base_path:
        config.files.base_path = os.path.abspath(base_path)

    return config


def load_config(config_path: Optional[str] = None,
               base_path: Optional[str] = None) -> WhaleBotsConfiguration:
    """
    Load configuration from file or create default.

    Args:
        config_path: Path to configuration file (optional)
        base_path: Base path for WhaleBots application (optional)

    Returns:
        Loaded or default WhaleBotsConfiguration instance
    """
    if config_path and os.path.exists(config_path):
        return WhaleBotsConfiguration.from_file(config_path)

    # Try to find config file in default locations
    default_paths = [
        "whalebots_config.json",
        "config/whalebots_config.json",
        os.path.expanduser("~/.whalebots/config.json")
    ]

    for path in default_paths:
        if os.path.exists(path):
            return WhaleBotsConfiguration.from_file(path)

    # Create default configuration
    return create_default_config(base_path)
