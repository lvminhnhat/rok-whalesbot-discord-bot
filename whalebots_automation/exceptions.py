"""
Custom exception classes for WhaleBots automation platform.

This module defines all custom exceptions used throughout the WhaleBots
automation system to provide clear error handling and debugging information.
"""

import os
from typing import Optional, Any, Dict


class WhaleBotsError(Exception):
    """
    Base exception class for all WhaleBots operations.

    All custom exceptions in the WhaleBots system should inherit from this
    class to provide a consistent error handling interface.
    """

    def __init__(self, message: str, error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize WhaleBots base exception.

        Args:
            message: Human-readable error message
            error_code: Optional error code for programmatic handling
            details: Additional error context information
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def __str__(self) -> str:
        """String representation of the exception."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            'exception_type': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details
        }


class ConfigurationError(WhaleBotsError):
    """
    Raised when configuration-related operations fail.

    This includes invalid configuration values, missing configuration files,
    or configuration validation failures.
    """
    pass


class FileOperationError(WhaleBotsError):
    """
    Raised when file operations fail.

    This includes file reading, writing, backup operations, and file validation
    failures.
    """

    def __init__(self, message: str, file_path: Optional[str] = None,
                 operation: Optional[str] = None, **kwargs):
        """
        Initialize file operation error.

        Args:
            message: Human-readable error message
            file_path: Path of the file that caused the error
            operation: Type of file operation (read, write, delete, etc.)
        """
        super().__init__(message, **kwargs)
        self.file_path = file_path
        self.operation = operation

        if file_path:
            self.details['file_path'] = file_path
        if operation:
            self.details['operation'] = operation


class SecurityError(WhaleBotsError):
    """
    Raised when security-related issues are detected.

    This includes unsafe file operations, invalid inputs, or potential
    security vulnerabilities.
    """
    pass


class EmulatorError(WhaleBotsError):
    """
    Raised when emulator operations fail.

    This is the base class for all emulator-related exceptions.
    """
    pass


class EmulatorNotFoundError(EmulatorError):
    """
    Raised when an emulator cannot be found or accessed.
    """

    def __init__(self, emulator_identifier: str, identifier_type: str = "name", **kwargs):
        """
        Initialize emulator not found error.

        Args:
            emulator_identifier: The identifier that was not found
            identifier_type: Type of identifier (name, index, device_id, etc.)
        """
        message = f"Emulator not found: {emulator_identifier} (by {identifier_type})"
        super().__init__(message, **kwargs)
        self.emulator_identifier = emulator_identifier
        self.identifier_type = identifier_type

        self.details.update({
            'emulator_identifier': emulator_identifier,
            'identifier_type': identifier_type
        })


class EmulatorStateError(EmulatorError):
    """
    Raised when emulator state operations fail.

    This includes invalid state transitions, state corruption, or
    state synchronization failures.
    """

    def __init__(self, message: str, emulator_index: Optional[int] = None,
                 current_state: Optional[int] = None, **kwargs):
        """
        Initialize emulator state error.

        Args:
            message: Human-readable error message
            emulator_index: Index of the emulator with state issues
            current_state: Current state value that caused the error
        """
        super().__init__(message, **kwargs)
        self.emulator_index = emulator_index
        self.current_state = current_state

        if emulator_index is not None:
            self.details['emulator_index'] = emulator_index
        if current_state is not None:
            self.details['current_state'] = current_state


class EmulatorAlreadyRunningError(EmulatorStateError):
    """
    Raised when trying to start an emulator that is already running.
    """

    def __init__(self, emulator_identifier: str, **kwargs):
        """
        Initialize emulator already running error.

        Args:
            emulator_identifier: Identifier of the emulator that is already running
        """
        message = f"Emulator is already running: {emulator_identifier}"
        super().__init__(message, **kwargs)
        self.emulator_identifier = emulator_identifier
        self.details['emulator_identifier'] = emulator_identifier


class EmulatorNotRunningError(EmulatorStateError):
    """
    Raised when trying to stop an emulator that is not running.
    """

    def __init__(self, emulator_identifier: str, **kwargs):
        """
        Initialize emulator not running error.

        Args:
            emulator_identifier: Identifier of the emulator that is not running
        """
        message = f"Emulator is not running: {emulator_identifier}"
        super().__init__(message, **kwargs)
        self.emulator_identifier = emulator_identifier
        self.details['emulator_identifier'] = emulator_identifier


class ProcessError(WhaleBotsError):
    """
    Raised when process operations fail.

    This includes process detection, monitoring, or control failures.
    """

    def __init__(self, message: str, process_id: Optional[int] = None,
                 process_name: Optional[str] = None, **kwargs):
        """
        Initialize process error.

        Args:
            message: Human-readable error message
            process_id: PID of the process that caused the error
            process_name: Name of the process that caused the error
        """
        super().__init__(message, **kwargs)
        self.process_id = process_id
        self.process_name = process_name

        if process_id:
            self.details['process_id'] = process_id
        if process_name:
            self.details['process_name'] = process_name


class WindowError(WhaleBotsError):
    """
    Raised when window operations fail.

    This includes window detection, manipulation, or control failures.
    """

    def __init__(self, message: str, window_handle: Optional[int] = None,
                 window_title: Optional[str] = None, **kwargs):
        """
        Initialize window error.

        Args:
            message: Human-readable error message
            window_handle: Handle of the window that caused the error
            window_title: Title of the window that caused the error
        """
        super().__init__(message, **kwargs)
        self.window_handle = window_handle
        self.window_title = window_title

        if window_handle:
            self.details['window_handle'] = hex(window_handle)
        if window_title:
            self.details['window_title'] = window_title


class WindowNotFoundError(WindowError):
    """
    Raised when the target window cannot be found.
    """

    def __init__(self, pattern: str, **kwargs):
        """
        Initialize window not found error.

        Args:
            pattern: The pattern used to search for the window
        """
        message = f"Window not found matching pattern: {pattern}"
        super().__init__(message, **kwargs)
        self.pattern = pattern
        self.details['search_pattern'] = pattern


class UICoordinateError(WindowError):
    """
    Raised when UI coordinate operations fail.

    This includes invalid coordinates, out-of-bounds clicks, or coordinate
    transformation failures.
    """

    def __init__(self, message: str, x: Optional[int] = None,
                 y: Optional[int] = None, **kwargs):
        """
        Initialize UI coordinate error.

        Args:
            message: Human-readable error message
            x: X coordinate that caused the error
            y: Y coordinate that caused the error
        """
        super().__init__(message, **kwargs)
        self.x = x
        self.y = y

        if x is not None:
            self.details['x_coordinate'] = x
        if y is not None:
            self.details['y_coordinate'] = y


class DependencyError(WhaleBotsError):
    """
    Raised when required dependencies are missing or unavailable.

    This includes missing Python packages, unavailable system libraries,
    or incompatible dependency versions.
    """

    def __init__(self, dependency_name: str, **kwargs):
        """
        Initialize dependency error.

        Args:
            dependency_name: Name of the missing dependency
        """
        message = f"Required dependency is not available: {dependency_name}"
        super().__init__(message, **kwargs)
        self.dependency_name = dependency_name
        self.details['dependency_name'] = dependency_name


class TimeoutError(WhaleBotsError):
    """
    Raised when operations timeout.

    This includes process startup timeouts, window detection timeouts,
    or any other time-bound operation failures.
    """

    def __init__(self, operation: str, timeout_seconds: float, **kwargs):
        """
        Initialize timeout error.

        Args:
            operation: Description of the operation that timed out
            timeout_seconds: Timeout duration in seconds
        """
        message = f"Operation timed out: {operation} (after {timeout_seconds}s)"
        super().__init__(message, **kwargs)
        self.operation = operation
        self.timeout_seconds = timeout_seconds

        self.details.update({
            'operation': operation,
            'timeout_seconds': timeout_seconds
        })


class ValidationError(WhaleBotsError):
    """
    Raised when input validation fails.

    This includes invalid parameter values, out-of-range values,
    or malformed input data.
    """

    def __init__(self, message: str, field_name: Optional[str] = None,
                 field_value: Optional[Any] = None, **kwargs):
        """
        Initialize validation error.

        Args:
            message: Human-readable error message
            field_name: Name of the field that failed validation
            field_value: Value that failed validation
        """
        super().__init__(message, **kwargs)
        self.field_name = field_name
        self.field_value = field_value

        if field_name:
            self.details['field_name'] = field_name
        if field_value is not None:
            self.details['field_value'] = str(field_value)


# Utility functions for exception handling
def handle_exception(func):
    """
    Decorator for standardized exception handling.

    This decorator catches exceptions and converts them to appropriate
    WhaleBots exceptions with proper logging.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except WhaleBotsError:
            # Re-raise WhaleBots exceptions as-is
            raise
        except FileNotFoundError as e:
            raise FileOperationError(
                f"File not found: {e.filename}",
                file_path=e.filename,
                operation="read"
            )
        except PermissionError as e:
            raise SecurityError(
                f"Permission denied: {e.filename}",
                details={'filename': e.filename}
            )
        except OSError as e:
            raise FileOperationError(
                f"OS error during file operation: {e}",
                details={'errno': e.errno, 'filename': getattr(e, 'filename', None)}
            )
        except ValueError as e:
            raise ValidationError(f"Invalid value provided: {e}")
        except Exception as e:
            # Catch-all for unexpected exceptions
            raise WhaleBotsError(
                f"Unexpected error: {str(e)}",
                details={'original_exception': type(e).__name__}
            )

    return wrapper


def create_error_context(exc: Exception, **additional_context) -> Dict[str, Any]:
    """
    Create error context dictionary for logging.

    Args:
        exc: Exception to create context for
        **additional_context: Additional context information

    Returns:
        Dictionary containing error context information
    """
    context = {
        'exception_type': type(exc).__name__,
        'exception_message': str(exc),
        'exception_module': type(exc).__module__,
    }

    if isinstance(exc, WhaleBotsError):
        context.update(exc.to_dict())

    context.update(additional_context)
    return context