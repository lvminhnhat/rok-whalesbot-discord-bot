"""
Logging utilities for WhaleBots automation platform.

This module provides centralized logging configuration and utilities
with structured logging, security filtering, and performance monitoring.
"""

import logging
import logging.handlers
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
from functools import wraps

try:
    from .config import LoggingConfiguration
    from .exceptions import WhaleBotsError, create_error_context
except ImportError:
    # Fallback for running tests directly
    from whalebots_automation.config import LoggingConfiguration
    from whalebots_automation.exceptions import WhaleBotsError, create_error_context


class WhaleBotsLogger:
    """
    Enhanced logger with security filtering and structured logging.

    This class provides a wrapper around Python's logging module with
    additional features for security, performance monitoring, and structured output.
    """

    def __init__(self, name: str, config: Optional[LoggingConfiguration] = None):
        """
        Initialize WhaleBots logger.

        Args:
            name: Logger name (typically module or class name)
            config: Logging configuration (uses default if None)
        """
        self.name = name
        self.config = config or LoggingConfiguration()
        self._logger = logging.getLogger(name)
        self._setup_logger()
        self._performance_data: Dict[str, float] = {}

    def _setup_logger(self) -> None:
        """Configure the underlying Python logger."""
        # Remove existing handlers to avoid duplicates
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)

        # Set logging level
        level = getattr(logging, self.config.default_level.upper(), logging.INFO)
        self._logger.setLevel(level)

        # Create formatter
        formatter = logging.Formatter(
            self.config.log_format,
            datefmt=self.config.date_format
        )

        # Add console handler if enabled
        if self.config.enable_console_logging:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

        # Add file handler if enabled
        if self.config.enable_file_logging:
            try:
                # Create log directory if it doesn't exist
                log_dir = Path(self.config.log_file_path).parent
                log_dir.mkdir(parents=True, exist_ok=True)

                # Use rotating file handler
                file_handler = logging.handlers.RotatingFileHandler(
                    self.config.log_file_path,
                    maxBytes=self.config.max_log_file_size,
                    backupCount=self.config.backup_count,
                    encoding='utf-8'
                )
                file_handler.setFormatter(formatter)
                self._logger.addHandler(file_handler)

            except Exception as e:
                # Fallback to console logging if file logging fails
                self._logger.warning(f"Failed to setup file logging: {e}")

    def _sanitize_message(self, message: str) -> str:
        """
        Sanitize log messages to prevent sensitive data leakage.

        Args:
            message: Original log message

        Returns:
            Sanitized log message
        """
        # Remove potential sensitive information
        import re

        # Filter out file paths that might contain sensitive info
        message = re.sub(r'[A-Za-z]:\\[^\\s]*', '[FILE_PATH]', message)
        message = re.sub(r'/[^\\s]*', '[FILE_PATH]', message)

        # Filter out potential passwords or tokens
        message = re.sub(r'[a-zA-Z0-9]{20,}', '[REDACTED_TOKEN]', message)

        return message

    def _log_with_context(self, level: int, message: str, **kwargs) -> None:
        """
        Log message with additional context information.

        Args:
            level: Logging level
            message: Log message
            **kwargs: Additional context information
        """
        # Sanitize message
        sanitized_message = self._sanitize_message(message)

        # Add context if provided
        if kwargs:
            context_str = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            full_message = f"{sanitized_message} | Context: {context_str}"
        else:
            full_message = sanitized_message

        self._logger.log(level, full_message)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, exception: Optional[Exception] = None, **kwargs) -> None:
        """Log error message with optional exception details."""
        if exception:
            error_context = create_error_context(exception, **kwargs)
            self._log_with_context(logging.ERROR, message, **error_context)
        else:
            self._log_with_context(logging.ERROR, message, **kwargs)

    def critical(self, message: str, exception: Optional[Exception] = None, **kwargs) -> None:
        """Log critical message with optional exception details."""
        if exception:
            error_context = create_error_context(exception, **kwargs)
            self._log_with_context(logging.CRITICAL, message, **error_context)
        else:
            self._log_with_context(logging.CRITICAL, message, **kwargs)

    def log_operation_start(self, operation: str, **kwargs) -> str:
        """
        Log the start of an operation and return an operation ID.

        Args:
            operation: Description of the operation
            **kwargs: Additional operation context

        Returns:
            Operation ID for tracking
        """
        operation_id = f"{operation}_{int(time.time())}"
        start_time = time.time()

        self._performance_data[operation_id] = start_time

        self.info(f"Operation started: {operation}",
                 operation_id=operation_id,
                 **kwargs)

        return operation_id

    def log_operation_end(self, operation_id: str, success: bool = True, **kwargs) -> None:
        """
        Log the end of an operation with timing information.

        Args:
            operation_id: Operation ID returned by log_operation_start
            success: Whether the operation was successful
            **kwargs: Additional operation context
        """
        if operation_id not in self._performance_data:
            self.warning(f"Unknown operation ID: {operation_id}")
            return

        start_time = self._performance_data.pop(operation_id)
        duration = time.time() - start_time

        status = "completed" if success else "failed"
        self.info(f"Operation {status}",
                 operation_id=operation_id,
                 duration_seconds=round(duration, 3),
                 **kwargs)

    def log_exception(self, exception: Exception, operation: Optional[str] = None, **kwargs) -> None:
        """
        Log exception with full traceback and context.

        Args:
            exception: Exception to log
            operation: Operation that was being performed when exception occurred
            **kwargs: Additional context information
        """
        context = create_error_context(exception, **kwargs)
        if operation:
            context['operation'] = operation

        message = f"Exception occurred: {type(exception).__name__}: {exception}"
        if operation:
            message += f" during {operation}"

        self.error(message, exception=exception, **context)

    def set_level(self, level: Union[str, int]) -> None:
        """
        Set the logging level.

        Args:
            level: Logging level (string or constant)
        """
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)

        self._logger.setLevel(level)
        self.info(f"Logging level set to: {logging.getLevelName(level)}")

    def is_enabled_for(self, level: Union[str, int]) -> bool:
        """
        Check if a logging level is enabled.

        Args:
            level: Logging level to check

        Returns:
            True if the level is enabled, False otherwise
        """
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)

        return self._logger.isEnabledFor(level)


# Global logger registry
_loggers: Dict[str, WhaleBotsLogger] = {}


def get_logger(name: str, config: Optional[LoggingConfiguration] = None) -> WhaleBotsLogger:
    """
    Get or create a WhaleBots logger instance.

    Args:
        name: Logger name (typically module or class name)
        config: Optional logging configuration

    Returns:
        WhaleBotsLogger instance
    """
    if name not in _loggers:
        _loggers[name] = WhaleBotsLogger(name, config)

    return _loggers[name]


def setup_global_logging(config: LoggingConfiguration) -> None:
    """
    Setup global logging configuration.

    Args:
        config: Global logging configuration
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.default_level.upper(), logging.INFO))

    # Update existing loggers with new config
    for logger in _loggers.values():
        logger.config = config
        logger._setup_logger()


def log_function_call(logger: Optional[WhaleBotsLogger] = None):
    """
    Decorator to log function calls with timing and exception handling.

    Args:
        logger: Logger instance to use (creates new if None)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get or create logger
            func_logger = logger or get_logger(func.__module__)

            # Log function start
            operation_id = func_logger.log_operation_start(
                f"{func.__module__}.{func.__name__}",
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Log successful completion
                func_logger.log_operation_end(operation_id, success=True)

                return result

            except Exception as e:
                # Log exception
                func_logger.log_operation_end(operation_id, success=False)
                func_logger.log_exception(e, f"{func.__module__}.{func.__name__}")
                raise

        return wrapper
    return decorator


def log_performance(logger: Optional[WhaleBotsLogger] = None):
    """
    Decorator to measure and log function performance.

    Args:
        logger: Logger instance to use (creates new if None)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_logger = logger or get_logger(f"{func.__module__}.performance")

            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                execution_time = time.perf_counter() - start_time

                func_logger.debug(f"Performance: {func.__name__}",
                                 execution_time=round(execution_time, 4),
                                 success=True)

                return result

            except Exception as e:
                execution_time = time.perf_counter() - start_time

                func_logger.debug(f"Performance: {func.__name__}",
                                 execution_time=round(execution_time, 4),
                                 success=False,
                                 error_type=type(e).__name__)

                raise

        return wrapper
    return decorator


class SecurityFilter(logging.Filter):
    """
    Logging filter that removes sensitive information from log records.

    This filter can be added to logging handlers to automatically
    sanitize log messages and prevent sensitive data leakage.
    """

    SENSITIVE_PATTERNS = [
        (r'[a-zA-Z0-9]{20,}', '[REDACTED_TOKEN]'),  # Tokens/keys
        (r'[A-Za-z]:\\[^\\s]*', '[FILE_PATH]'),      # Windows file paths
        (r'/home/[^\\s]*', '[FILE_PATH]'),           # Unix file paths
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\\s]+', 'password=[REDACTED]'),  # Passwords
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and sanitize log record.

        Args:
            record: Log record to filter

        Returns:
            True if record should be logged, False otherwise
        """
        if hasattr(record, 'msg'):
            message = str(record.msg)

            # Apply all sanitization patterns
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                import re
                message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)

            record.msg = message

        return True


def create_default_logger(name: str, log_level: str = "INFO") -> WhaleBotsLogger:
    """
    Create a logger with default configuration.

    Args:
        name: Logger name
        log_level: Default log level

    Returns:
        Configured WhaleBotsLogger instance
    """
    config = LoggingConfiguration(default_level=log_level)
    return WhaleBotsLogger(name, config)