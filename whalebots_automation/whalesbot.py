"""
WhalesBot class for managing the WhaleBots gaming automation platform.

This module provides a comprehensive interface for managing WhaleBots instances,
including emulator detection, state management, process monitoring, and UI automation
with proper error handling, logging, and security validation.
"""

import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple

try:
    from .config import (
        WhaleBotsConfiguration, UIConfiguration, FileConfiguration,
        ProcessConfiguration, load_config
    )
    from .exceptions import (
        WhaleBotsError, EmulatorNotFoundError, EmulatorStateError,
        EmulatorAlreadyRunningError, EmulatorNotRunningError,
        WindowError, ValidationError, handle_exception
    )
    from .logger import get_logger, log_performance, log_function_call
    from .core.state import (
        EmulatorStateManager, EmulatorState, create_state_manager
    )
    from .core.emulator_action import WindowController
    from .services.emulator_validator import EmulatorValidator
except ImportError:
    # Fallback for running tests directly
    from whalebots_automation.config import (
        WhaleBotsConfiguration, UIConfiguration, FileConfiguration,
        ProcessConfiguration, load_config
    )
    from whalebots_automation.exceptions import (
        WhaleBotsError, EmulatorNotFoundError, EmulatorStateError,
        EmulatorAlreadyRunningError, EmulatorNotRunningError,
        WindowError, ValidationError, handle_exception
    )
    from whalebots_automation.logger import get_logger, log_performance, log_function_call
    from whalebots_automation.core.state import (
        EmulatorStateManager, EmulatorState, create_state_manager
    )
    from whalebots_automation.core.emulator_action import WindowController
    from whalebots_automation.services.emulator_validator import EmulatorValidator


class ProcessMonitor:
    """
    Monitors and manages emulator processes.

    Provides functionality to detect running emulator processes,
    gather process information, and monitor process status.
    """

    def __init__(self, config: ProcessConfiguration):
        """
        Initialize process monitor.

        Args:
            config: Process configuration settings
        """
        self.config = config
        self.logger = get_logger(f"{__name__}.ProcessMonitor")

        # Try to import psutil for process monitoring
        try:
            import psutil
            self.psutil = psutil
        except ImportError:
            self.psutil = None
            self.logger.warning(
                "psutil not available. Process monitoring will be limited."
            )

    @log_performance()
    def detect_running_emulators(self) -> List[Dict[str, Any]]:
        """
        Detect currently running emulator processes.

        Returns:
            List of dictionaries containing process information for running emulators.
            Empty list if psutil is not available or no emulators are running.
        """
        if not self.psutil or not self.config.enable_process_monitoring:
            self.logger.debug("Process monitoring disabled or psutil not available")
            return []

        operation_id = self.logger.log_operation_start("detect_running_emulators")

        try:
            running_emulators = []
            all_processes = self.psutil.process_iter(['pid', 'name', 'exe', 'cmdline'])

            for process in all_processes:
                try:
                    process_info = process.info
                    process_name = process_info.get('name', '')

                    # Check if process name matches any emulator patterns
                    if any(pattern.lower() in process_name.lower()
                          for pattern in self.config.process_name_patterns):

                        emulator_info = {
                            'process_info': {
                                'pid': process_info['pid'],
                                'name': process_name,
                                'executable': process_info.get('exe', ''),
                                'command_line': process_info.get('cmdline', [])
                            },
                            'status': 'running',
                            'start_time': process.create_time() if hasattr(process, 'create_time') else time.time()
                        }

                        running_emulators.append(emulator_info)
                        self.logger.debug(f"Found emulator process: {process_name} (PID: {process_info['pid']})")

                except (self.psutil.NoSuchProcess, self.psutil.AccessDenied):
                    continue

            self.logger.info(f"Detected {len(running_emulators)} running emulator processes")
            self.logger.log_operation_end(operation_id, success=True)
            return running_emulators

        except Exception as e:
            self.logger.log_operation_end(operation_id, success=False)
            self.logger.error(f"Error detecting running emulators: {e}")
            return []

    def get_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific process.

        Args:
            pid: Process ID

        Returns:
            Dictionary containing process information, or None if process not found.
        """
        if not self.psutil:
            return None

        try:
            process = self.psutil.Process(pid)

            # Get basic process info
            info = {
                'pid': pid,
                'name': process.name(),
                'status': process.status(),
                'create_time': process.create_time(),
                'cpu_percent': process.cpu_percent(),
                'memory_info': process.memory_info()._asdict(),
                'cmdline': process.cmdline()
            }

            return info

        except (self.psutil.NoSuchProcess, self.psutil.AccessDenied) as e:
            self.logger.warning(f"Cannot get process info for PID {pid}: {e}")
            return None


class WhaleBots:
    """
    Main class for managing WhaleBots gaming automation platform.

    This class provides a comprehensive interface for managing WhaleBots instances,
    including emulator detection, state management, process monitoring, and UI automation
    with proper error handling, logging, and security validation.
    """

    def __init__(
        self,
        path: str,
        config: Optional[WhaleBotsConfiguration] = None,
        config_file: Optional[str] = None
    ):
        """
        Initialize the WhalesBot manager.

        Args:
            path: Path to the WhaleBots application directory. Must be a non-empty string.
            config: Optional configuration object (loaded from file if not provided)
            config_file: Optional path to configuration file

        Raises:
            ValidationError: If the path is empty or invalid.
            WhaleBotsError: If initialization fails.
            ConfigurationError: If configuration is invalid
        """
        # Validate path parameter
        if not path or not isinstance(path, str):
            raise ValidationError("The 'path' argument must be a non-empty string.")

        # Initialize configuration
        if config:
            self.config = config
        else:
            self.config = load_config(config_file, path)

        # Update base path in configuration
        self.config.files.base_path = os.path.abspath(path)

        # Validate base path
        if not os.path.exists(self.config.files.base_path):
            raise WhaleBotsError(f"Base path does not exist: {self.config.files.base_path}")

        # Initialize logger
        self.logger = get_logger(f"{__name__}.WhalesBot", self.config.logging)

        # Initialize components
        self._initialize_components()

        self.logger.info(f"WhalesBot initialized with base path: {self.config.files.base_path}")

    def _initialize_components(self) -> None:
        """
        Initialize internal components.

        Raises:
            WhaleBotsError: If component initialization fails
        """
        try:
            # Initialize state manager
            self.state_manager = EmulatorStateManager(
                base_path=self.config.files.base_path,
                file_config=self.config.files,
                security_config=self.config.security
            )

            # Initialize process monitor
            self.process_monitor = ProcessMonitor(self.config.process)

            # Initialize UI controller (lazy initialization)
            self._ui_controller: Optional[WindowController] = None

            # Initialize emulator validator (lazy initialization)
            self._emulator_validator: Optional[EmulatorValidator] = None

            # Validate configuration
            is_valid, errors = self.validate_configuration()
            if not is_valid:
                self.logger.warning(f"Configuration validation issues: {errors}")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise WhaleBotsError(f"Failed to initialize components: {e}")

    @property
    def ui_controller(self) -> WindowController:
        """
        Get UI controller, initializing it lazily if needed.

        Returns:
            WindowController instance

        Raises:
            DependencyError: If required dependencies are missing
            WindowError: If UI controller initialization fails
        """
        if self._ui_controller is None:
            self._ui_controller = WindowController.create(
                pattern=self.config.ui.window_title_pattern,
                config=self.config.ui
            )
            self._ui_controller.attach()
            self.logger.info("UI controller initialized and attached")

        return self._ui_controller

    @property
    def emulator_validator(self) -> EmulatorValidator:
        """
        Get emulator validator, initializing it lazily if needed.

        Returns:
            EmulatorValidator instance

        Raises:
            EmulatorError: If validator initialization fails
        """
        if self._emulator_validator is None:
            self._emulator_validator = EmulatorValidator(
                whalesbot=self,
                interval_minutes=10,  # Validate every 10 minutes
                enable_resource_monitoring=True,
                enable_auto_recovery=True
            )
            self.logger.info("Emulator validator initialized")

        return self._emulator_validator

    @log_performance()
    def validate_configuration(self) -> Tuple[bool, List[str]]:
        """
        Validate the WhaleBots configuration.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        return self.state_manager.validate_configuration()

    @log_function_call()
    def check_status(self, device: Union[str, int]) -> bool:
        """
        Check if a device/emulator exists and is configured.

        Args:
            device: Device identifier (name or index)

        Returns:
            True if device exists, False otherwise

        Raises:
            WhaleBotsError: If state manager is not initialized
        """
        if not self.state_manager:
            raise WhaleBotsError("State manager is not initialized")

        return (self.state_manager.is_device_active(device) or
                self.state_manager.get_emulator_state_by_name(str(device)) is not None or
                (str(device).isdigit() and
                 self.state_manager.get_emulator_state_by_index(int(device)) is not None))

    @log_function_call()
    def is_active(self, device: Union[str, int]) -> bool:
        """
        Check if a device/emulator is currently active (running).

        Args:
            device: Device identifier (name or index)

        Returns:
            True if device is active (state > 0), False otherwise

        Raises:
            WhaleBotsError: If state manager is not initialized
        """
        if not self.state_manager:
            raise WhaleBotsError("State manager is not initialized")

        return self.state_manager.is_device_active(device)

    def _start_by_name(self, name: str) -> None:
        """
        Start an emulator by name.

        Args:
            name: Name of the emulator to start

        Raises:
            EmulatorNotFoundError: If emulator is not found
            EmulatorAlreadyRunningError: If emulator is already running
            WindowError: If UI operations fail
        """
        index = self.state_manager.get_index_emulator_by_name(name)
        if index == -1:
            raise EmulatorNotFoundError(name, "name")

        self._start_by_index(index)

    def _start_by_index(self, index: int) -> None:
        """
        Start an emulator by index.

        Args:
            index: Index of the emulator to start

        Raises:
            ValidationError: If index is invalid
            EmulatorAlreadyRunningError: If emulator is already running
            WindowError: If UI operations fail
        """
        if index < 0:
            raise ValidationError("Emulator index cannot be negative")

        # Get current state
        emulator_state = self.state_manager.get_emulator_state_by_index(index)
        if emulator_state is None:
            raise EmulatorNotFoundError(str(index), "index")

        if emulator_state.is_active:
            raise EmulatorAlreadyRunningError(f"Emulator at index {index}")

        # Calculate click coordinates
        click_x, click_y, scroll_down = self._calculate_ui_coordinates(index)

        # Perform UI operations
        try:
            # Scroll to the emulator position
            self.ui_controller.scroll(
                self.config.ui.scroll_position_x,
                self.config.ui.scroll_position_y,
                up=self.config.ui.default_scroll_up,
                down=scroll_down
            )

            # Click to start
            success = self.ui_controller.click(click_x, click_y)
            if not success:
                raise WindowError(f"Failed to click at coordinates ({click_x}, {click_y})")

            # Update state
            self.state_manager.set_emulator_active(index)

            self.logger.info(f"Started emulator at index {index}")

        except Exception as e:
            raise WindowError(f"Failed to start emulator at index {index}: {e}")

    def _calculate_ui_coordinates(self, index: int) -> Tuple[int, int, int]:
        """
        Calculate UI coordinates for emulator interaction.

        Args:
            index: Emulator index

        Returns:
            Tuple of (click_x, click_y, scroll_down)
        """
        if index <= self.config.ui.max_visible_items - 1:
            # Visible without scrolling
            click_y = self.config.ui.base_y_coordinate + self.config.ui.step_size * index
            scroll_down = 0
        else:
            # Need to scroll down
            click_y = self.config.ui.base_y_coordinate + self.config.ui.step_size * (self.config.ui.max_visible_items - 1 -1)
            scroll_down = index - (self.config.ui.max_visible_items - 1)

        click_x = self.config.ui.base_x_coordinate

        return click_x, click_y, scroll_down

    @log_performance()
    def start(self, device: Union[str, int]) -> None:
        """
        Start an emulator device.

        Args:
            device: Device identifier (name or index)

        Raises:
            ValidationError: If device identifier is invalid
            EmulatorNotFoundError: If emulator is not found
            EmulatorAlreadyRunningError: If emulator is already running
            WindowError: If UI operations fail
            WhaleBotsError: If state manager is not initialized
        """
        if not self.state_manager:
            raise WhaleBotsError("State manager is not initialized")

        device_str = str(device)

        if device_str.isdigit():
            self._start_by_index(int(device_str))
        else:
            self._start_by_name(device_str)

    def _stop_by_name(self, name: str) -> None:
        """
        Stop an emulator by name.

        Args:
            name: Name of the emulator to stop

        Raises:
            EmulatorNotFoundError: If emulator is not found
            EmulatorNotRunningError: If emulator is not running
            WindowError: If UI operations fail
        """
        index = self.state_manager.get_index_emulator_by_name(name)
        if index == -1:
            raise EmulatorNotFoundError(name, "name")

        self._stop_by_index(index)

    def _stop_by_index(self, index: int) -> None:
        """
        Stop an emulator by index.

        Args:
            index: Index of the emulator to stop

        Raises:
            ValidationError: If index is invalid
            EmulatorNotFoundError: If emulator is not found
            EmulatorNotRunningError: If emulator is not running
            WindowError: If UI operations fail
        """
        if index < 0:
            raise ValidationError("Emulator index cannot be negative")

        # Check if emulator is currently running
        emulator_state = self.state_manager.get_emulator_state_by_index(index)
        if emulator_state is None:
            raise EmulatorNotFoundError(str(index), "index")

        if not emulator_state.is_active:
            raise EmulatorNotRunningError(f"Emulator at index {index}")

        # Calculate click coordinates (same as start)
        click_x, click_y, scroll_down = self._calculate_ui_coordinates(index)

        # Perform UI operations
        try:
            # Scroll to the emulator position
            self.ui_controller.scroll(
                self.config.ui.scroll_position_x,
                self.config.ui.scroll_position_y,
                up=self.config.ui.default_scroll_up,
                down=scroll_down
            )

            # Click to stop
            success = self.ui_controller.click(click_x, click_y)
            if not success:
                raise WindowError(f"Failed to click at coordinates ({click_x}, {click_y})")

            # Update state
            self.state_manager.set_emulator_inactive(index)

            self.logger.info(f"Stopped emulator at index {index}")

        except Exception as e:
            raise WindowError(f"Failed to stop emulator at index {index}: {e}")

    @log_performance()
    def stop(self, device: Union[str, int]) -> None:
        """
        Stop an emulator device.

        Args:
            device: Device identifier (name or index)

        Raises:
            ValidationError: If device identifier is invalid
            EmulatorNotFoundError: If emulator is not found
            EmulatorNotRunningError: If emulator is not running
            WindowError: If UI operations fail
            WhaleBotsError: If state manager is not initialized
        """
        if not self.state_manager:
            raise WhaleBotsError("State manager is not initialized")

        device_str = str(device)

        if device_str.isdigit():
            self._stop_by_index(int(device_str))
        else:
            self._stop_by_name(device_str)

    # State management methods (delegated to state manager)
    def get_emulator_states(self) -> List[EmulatorState]:
        """
        Get the state data for each emulator.

        Returns:
            List of EmulatorState objects containing emulator information with their states.
        """
        return self.state_manager.get_emulator_states()

    def get_emulator_state_by_index(self, index: int) -> Optional[EmulatorState]:
        """
        Get state data for a specific emulator by index.

        Args:
            index: Index of the emulator (0-based)

        Returns:
            EmulatorState object, or None if not found.
        """
        return self.state_manager.get_emulator_state_by_index(index)

    def get_emulator_state_by_name(self, name: str) -> Optional[EmulatorState]:
        """
        Get state data for a specific emulator by name.

        Args:
            name: Name of the emulator to search for

        Returns:
            EmulatorState object, or None if not found.
        """
        return self.state_manager.get_emulator_state_by_name(name)

    def get_active_emulators(self) -> List[EmulatorState]:
        """
        Get list of emulators that are currently active.

        Returns:
            List of EmulatorState objects for active emulators.
        """
        return self.state_manager.get_active_emulators()

    def get_inactive_emulators(self) -> List[EmulatorState]:
        """
        Get list of emulators that are currently inactive.

        Returns:
            List of EmulatorState objects for inactive emulators.
        """
        return self.state_manager.get_inactive_emulators()

    def get_emulator_count(self) -> int:
        """
        Get the total number of configured emulators.

        Returns:
            Number of emulators configured in the accounts file.
        """
        return self.state_manager.get_emulator_count()

    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all emulator states.

        Returns:
            Dictionary containing summary information.
        """
        summary = self.state_manager.get_state_summary()
        return summary.to_dict()

    # Process monitoring methods
    def detect_running_emulators(self) -> List[Dict[str, Any]]:
        """
        Detect currently running emulator processes.

        Returns:
            List of dictionaries containing process information for running emulators.
        """
        return self.process_monitor.detect_running_emulators()

    def get_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific process.

        Args:
            pid: Process ID

        Returns:
            Dictionary containing process information, or None if process not found.
        """
        return self.process_monitor.get_process_info(pid)

    def cleanup(self) -> None:
        """
        Clean up resources and close connections.

        This method should be called when the WhalesBot instance is no longer needed.
        """
        try:
            # Detach UI controller
            if self._ui_controller:
                self._ui_controller.detach()
                self._ui_controller = None

            # Invalidate caches
            if self.state_manager:
                self.state_manager.invalidate_cache()

            self.logger.info("WhalesBot cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        if exc_type:
            self.logger.error(f"Exception in context: {exc_type.__name__}: {exc_val}")


def create_whalesbot(
    path: Optional[str] = None,
    config_file: Optional[str] = None
) -> WhaleBots:
    """
    Convenience function to create a WhaleBots instance.

    Args:
        path: Path to WhaleBots application directory (uses current directory if None)
        config_file: Optional path to configuration file

    Returns:
        Configured WhaleBots instance

    Raises:
        WhaleBotsError: If creation fails
    """
    if path is None:
        path = os.getcwd()

    return WhaleBots(path, config_file=config_file)