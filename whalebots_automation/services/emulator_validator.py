"""
Emulator Validator Service for WhaleBots automation platform.

This module provides comprehensive background validation for emulator processes,
including process-state synchronization, health checks, resource monitoring,
and automatic recovery actions.
"""

import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

try:
    from ..config import ProcessConfiguration
    from ..exceptions import (
        EmulatorError, EmulatorNotFoundError, EmulatorStateError,
        ValidationError, handle_exception
    )
    from ..logger import get_logger, log_performance
    from ..core.state import EmulatorStateManager, EmulatorState
except ImportError:
    # Fallback for running tests directly
    from whalebots_automation.config import ProcessConfiguration
    from whalebots_automation.exceptions import (
        EmulatorError, EmulatorNotFoundError, EmulatorStateError,
        ValidationError, handle_exception
    )
    from whalebots_automation.logger import get_logger, log_performance
    from whalebots_automation.core.state import EmulatorStateManager, EmulatorState

if TYPE_CHECKING:
    try:
        from ..whalesbot import WhaleBots, ProcessMonitor
    except ImportError:  # pragma: no cover - fallback for tests without package context
        from whalebots_automation.whalesbot import WhaleBots, ProcessMonitor


class EmulatorHealthStatus(Enum):
    """Enum for emulator health status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MISSING = "missing"


@dataclass
class EmulatorHealthResult:
    """Container for emulator health check results."""
    index: int
    name: str
    status: EmulatorHealthStatus
    process_running: bool
    state_active: bool
    responsive: bool = False
    cpu_usage: Optional[float] = None
    memory_usage_mb: Optional[int] = None
    last_check: datetime = field(default_factory=datetime.now)
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'index': self.index,
            'name': self.name,
            'status': self.status.value,
            'process_running': self.process_running,
            'state_active': self.state_active,
            'responsive': self.responsive,
            'cpu_usage': self.cpu_usage,
            'memory_usage_mb': self.memory_usage_mb,
            'last_check': self.last_check.isoformat(),
            'issues': self.issues
        }


@dataclass
class ValidationSummary:
    """Container for validation summary information."""
    total_emulators: int
    healthy_count: int
    unhealthy_count: int
    missing_count: int
    last_validation: datetime = field(default_factory=datetime.now)
    validation_count: int = 0
    emulators: List[EmulatorHealthResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'overall_status': 'healthy' if self.unhealthy_count == 0 else 'unhealthy',
            'total_emulators': self.total_emulators,
            'healthy_count': self.healthy_count,
            'unhealthy_count': self.unhealthy_count,
            'missing_count': self.missing_count,
            'last_validation': self.last_validation.isoformat(),
            'validation_count': self.validation_count,
            'emulators': [emu.to_dict() for emu in self.emulators]
        }


class EmulatorValidator:
    """
    Background service for emulator validation and health checks.

    This class provides comprehensive emulator monitoring including:
    - Process-state synchronization
    - Health checks and responsiveness testing
    - Resource monitoring
    - Automatic recovery actions
    - Status reporting
    """

    def __init__(
        self,
        whalesbot: 'WhaleBots',
        interval_minutes: int = 10,
        enable_resource_monitoring: bool = True,
        enable_auto_recovery: bool = True
    ):
        """
        Initialize emulator validator.

        Args:
            whalesbot: WhaleBots instance for emulator management
            interval_minutes: Validation interval in minutes
            enable_resource_monitoring: Enable CPU/memory monitoring
            enable_auto_recovery: Enable automatic recovery actions
        """
        self.whalesbot = whalesbot
        self.interval = interval_minutes * 60  # Convert to seconds
        self.enable_resource_monitoring = enable_resource_monitoring
        self.enable_auto_recovery = enable_auto_recovery

        # Initialize components
        self.state_manager = whalesbot.state_manager
        self.process_monitor = whalesbot.process_monitor
        self.logger = get_logger(f"{__name__}.EmulatorValidator")

        # Threading control
        self._running = False
        self._validation_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Validation statistics
        self.validation_count = 0
        self.last_validation_time: Optional[datetime] = None
        self.health_history: Dict[int, List[EmulatorHealthResult]] = {}

        # Recovery tracking
        self.restart_attempts: Dict[int, int] = {}
        self.last_restart_time: Dict[int, datetime] = {}

        self.logger.info(f"EmulatorValidator initialized with {interval_minutes} minute interval")

    def start(self) -> None:
        """
        Start the background validation thread.

        Raises:
            EmulatorError: If validator is already running
        """
        if self._running:
            raise EmulatorError("Emulator validator is already running")

        self._running = True
        self._stop_event.clear()

        self._validation_thread = threading.Thread(
            target=self._validation_loop,
            daemon=True,
            name="EmulatorValidator"
        )
        self._validation_thread.start()

        self.logger.info("Emulator validator started")

    def stop(self) -> None:
        """Stop the background validation thread."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._validation_thread and self._validation_thread.is_alive():
            self._validation_thread.join(timeout=5)

        self.logger.info("Emulator validator stopped")

    def is_running(self) -> bool:
        """Check if validator is currently running."""
        return self._running

    def _validation_loop(self) -> None:
        """Main validation loop running in background thread."""
        self.logger.debug("Validation loop started")

        while self._running and not self._stop_event.is_set():
            try:
                self._validate_emulators()

                # Wait for next iteration or stop signal
                if self._stop_event.wait(self.interval):
                    break  # Stop signal received

            except Exception as e:
                self.logger.error(f"Error in validation loop: {e}")
                # Shorter delay on error to prevent rapid error loops
                if self._stop_event.wait(30):
                    break

        self.logger.debug("Validation loop stopped")

    @log_performance()
    def _validate_emulators(self) -> ValidationSummary:
        """
        Perform comprehensive emulator validation.

        Returns:
            ValidationSummary with results
        """
        operation_id = self.logger.log_operation_start("_validate_emulators")

        try:
            # Get emulator states
            emulator_states = self.state_manager.get_emulator_states()

            # Get running processes
            running_processes = self.process_monitor.detect_running_emulators()

            # Validate each emulator
            health_results = []
            for emulator_state in emulator_states:
                result = self._validate_single_emulator(emulator_state, running_processes)
                health_results.append(result)

                # Store in health history
                if emulator_state.index not in self.health_history:
                    self.health_history[emulator_state.index] = []

                self.health_history[emulator_state.index].append(result)

                # Keep only last 10 results per emulator
                if len(self.health_history[emulator_state.index]) > 10:
                    self.health_history[emulator_state.index].pop(0)

            # Create summary
            summary = self._create_summary(health_results)

            # Update statistics
            self.validation_count += 1
            self.last_validation_time = datetime.now()

            # Perform recovery actions if enabled
            if self.enable_auto_recovery:
                self._perform_recovery_actions(health_results)

            self.logger.info(
                f"Validation completed: {summary.healthy_count} healthy, "
                f"{summary.unhealthy_count} unhealthy, {summary.missing_count} missing"
            )

            self.logger.log_operation_end(operation_id, success=True)
            return summary

        except Exception as e:
            self.logger.log_operation_end(operation_id, success=False)
            self.logger.error(f"Emulator validation failed: {e}")
            raise

    def _validate_single_emulator(
        self,
        emulator_state: EmulatorState,
        running_processes: List[Dict[str, Any]]
    ) -> EmulatorHealthResult:
        """
        Validate a single emulator.

        Args:
            emulator_state: Emulator state to validate
            running_processes: List of running emulator processes

        Returns:
            EmulatorHealthResult with validation results
        """
        result = EmulatorHealthResult(
            index=emulator_state.index,
            name=emulator_state.emulator_info.name,
            status=EmulatorHealthStatus.UNKNOWN,
            process_running=False,
            state_active=emulator_state.is_active
        )

        # Check if process is running
        result.process_running = self._is_process_running(emulator_state, running_processes)

        # Determine health status
        if result.state_active and result.process_running:
            result.status = EmulatorHealthStatus.HEALTHY

            # Perform additional health checks
            if self._perform_health_check(emulator_state):
                result.responsive = True
            else:
                result.status = EmulatorHealthStatus.UNHEALTHY
                result.issues.append("Emulator not responsive")

            # Get resource usage if enabled
            if self.enable_resource_monitoring:
                cpu_usage, memory_mb = self._get_resource_usage(emulator_state)
                result.cpu_usage = cpu_usage
                result.memory_usage_mb = memory_mb

                # Check resource thresholds
                if cpu_usage and cpu_usage > 90:
                    result.status = EmulatorHealthStatus.UNHEALTHY
                    result.issues.append(f"High CPU usage: {cpu_usage:.1f}%")

                if memory_mb and memory_mb > 4096:
                    result.status = EmulatorHealthStatus.UNHEALTHY
                    result.issues.append(f"High memory usage: {memory_mb}MB")

        elif result.state_active and not result.process_running:
            result.status = EmulatorHealthStatus.MISSING
            result.issues.append("Process should be running but not found")

        elif not result.state_active and result.process_running:
            result.status = EmulatorHealthStatus.UNHEALTHY
            result.issues.append("Process running but state indicates inactive")

        else:  # not active and not running
            result.status = EmulatorHealthStatus.HEALTHY  # This is expected

        return result

    def _is_process_running(
        self,
        emulator_state: EmulatorState,
        running_processes: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if emulator process is running.

        Args:
            emulator_state: Emulator state to check
            running_processes: List of running processes

        Returns:
            True if process is running, False otherwise
        """
        emulator_info = emulator_state.emulator_info

        for process in running_processes:
            process_info = process['process_info']

            # Check by executable path
            if (emulator_info.executable_path and
                process_info.get('executable', '').lower() == emulator_info.executable_path.lower()):
                return True

            # Check by command line arguments
            command_line = process_info.get('command_line', [])
            if (emulator_info.vm_name and
                any(emulator_info.vm_name in str(arg) for arg in command_line)):
                return True

            # Check by device ID
            if (emulator_info.device_id and
                any(emulator_info.device_id in str(arg) for arg in command_line)):
                return True

        return False

    def _perform_health_check(self, emulator_state: EmulatorState) -> bool:
        """
        Perform basic health check on emulator.

        Args:
            emulator_state: Emulator state to check

        Returns:
            True if emulator appears healthy, False otherwise
        """
        try:
            # For now, just check if we can get process info
            # This could be extended with more sophisticated checks
            running_processes = self.process_monitor.detect_running_emulators()

            for process in running_processes:
                process_info = process['process_info']
                pid = process_info.get('pid')

                if pid and self._is_process_running(emulator_state, [process]):
                    # Try to get detailed process info
                    detailed_info = self.process_monitor.get_process_info(pid)
                    if detailed_info and detailed_info.get('status') == 'running':
                        return True

            return False

        except Exception as e:
            self.logger.warning(f"Health check failed for {emulator_state.emulator_info.name}: {e}")
            return False

    def _get_resource_usage(self, emulator_state: EmulatorState) -> Tuple[Optional[float], Optional[int]]:
        """
        Get CPU and memory usage for emulator.

        Args:
            emulator_state: Emulator state to check

        Returns:
            Tuple of (cpu_percent, memory_mb)
        """
        try:
            running_processes = self.process_monitor.detect_running_emulators()

            for process in running_processes:
                if self._is_process_running(emulator_state, [process]):
                    process_info = process['process_info']
                    pid = process_info.get('pid')

                    if pid:
                        detailed_info = self.process_monitor.get_process_info(pid)
                        if detailed_info:
                            cpu_percent = detailed_info.get('cpu_percent')
                            memory_info = detailed_info.get('memory_info', {})

                            memory_mb = None
                            if memory_info and 'rss' in memory_info:
                                memory_mb = memory_info['rss'] / (1024 * 1024)  # Convert to MB

                            return cpu_percent, memory_mb

            return None, None

        except Exception as e:
            self.logger.warning(f"Failed to get resource usage for {emulator_state.emulator_info.name}: {e}")
            return None, None

    def _create_summary(self, health_results: List[EmulatorHealthResult]) -> ValidationSummary:
        """
        Create validation summary from health results.

        Args:
            health_results: List of individual emulator health results

        Returns:
            ValidationSummary
        """
        healthy_count = sum(1 for result in health_results if result.status == EmulatorHealthStatus.HEALTHY)
        unhealthy_count = sum(1 for result in health_results if result.status == EmulatorHealthStatus.UNHEALTHY)
        missing_count = sum(1 for result in health_results if result.status == EmulatorHealthStatus.MISSING)

        return ValidationSummary(
            total_emulators=len(health_results),
            healthy_count=healthy_count,
            unhealthy_count=unhealthy_count,
            missing_count=missing_count,
            last_validation=datetime.now(),
            validation_count=self.validation_count,
            emulators=health_results
        )

    def _perform_recovery_actions(self, health_results: List[EmulatorHealthResult]) -> None:
        """
        Perform automatic recovery actions for unhealthy emulators.

        Args:
            health_results: List of emulator health results
        """
        for result in health_results:
            if result.status == EmulatorHealthStatus.MISSING:
                self._attempt_restart(result.index, result.name)
            elif result.status == EmulatorHealthStatus.UNHEALTHY:
                self._handle_unhealthy_emulator(result)

    def _attempt_restart(self, emulator_index: int, emulator_name: str) -> None:
        """
        Attempt to restart a missing emulator.

        Args:
            emulator_index: Index of emulator to restart
            emulator_name: Name of emulator
        """
        # Check restart attempt limits
        max_attempts = 3
        cooldown_minutes = 5

        current_attempts = self.restart_attempts.get(emulator_index, 0)
        last_restart = self.last_restart_time.get(emulator_index)

        if current_attempts >= max_attempts:
            self.logger.warning(f"Max restart attempts reached for {emulator_name} (index {emulator_index})")
            return

        if last_restart:
            time_since_restart = datetime.now() - last_restart
            if time_since_restart < timedelta(minutes=cooldown_minutes):
                self.logger.debug(f"Restart cooldown active for {emulator_name}")
                return

        try:
            self.logger.info(f"Attempting to restart emulator {emulator_name} (index {emulator_index})")

            # Update restart tracking
            self.restart_attempts[emulator_index] = current_attempts + 1
            self.last_restart_time[emulator_index] = datetime.now()

            # Here you would implement the actual restart logic
            # For now, just log the attempt
            self.logger.info(f"Restart attempted for {emulator_name} (attempt {current_attempts + 1}/{max_attempts})")

            # Reset attempts on success (this would be done after successful restart)
            # self.restart_attempts[emulator_index] = 0

        except Exception as e:
            self.logger.error(f"Failed to restart emulator {emulator_name}: {e}")

    def _handle_unhealthy_emulator(self, result: EmulatorHealthResult) -> None:
        """
        Handle unhealthy emulator (not responsive, high resources, etc.).

        Args:
            result: Health result for unhealthy emulator
        """
        self.logger.warning(f"Unhealthy emulator detected: {result.name} - {result.issues}")

        # For now, just log the issue
        # Future implementations could include:
        # - Sending notifications
        # - Attempting to restart non-responsive emulators
        # - Adjusting resource limits
        # - Creating support tickets

    def get_health_summary(self) -> ValidationSummary:
        """
        Get the most recent health summary.

        Returns:
            ValidationSummary with latest results, or empty summary if no validation has run
        """
        if not self.health_history:
            return ValidationSummary(
                total_emulators=0,
                healthy_count=0,
                unhealthy_count=0,
                missing_count=0,
                validation_count=self.validation_count
            )

        # Get the most recent results for each emulator
        latest_results = []
        for index, history in self.health_history.items():
            if history:
                latest_results.append(history[-1])

        return self._create_summary(latest_results)

    def get_emulator_health_history(self, emulator_index: int) -> List[EmulatorHealthResult]:
        """
        Get health history for a specific emulator.

        Args:
            emulator_index: Index of emulator

        Returns:
            List of health results for the emulator
        """
        return self.health_history.get(emulator_index, [])

    def validate_emulator_now(self, emulator_index: Optional[int] = None) -> Union[ValidationSummary, EmulatorHealthResult]:
        """
        Perform immediate validation of emulator(s).

        Args:
            emulator_index: Optional index of specific emulator to validate.
                          If None, validates all emulators.

        Returns:
            ValidationSummary if validating all emulators,
            EmulatorHealthResult if validating specific emulator
        """
        if emulator_index is not None:
            emulator_state = self.state_manager.get_emulator_state_by_index(emulator_index)
            if not emulator_state:
                raise EmulatorNotFoundError(f"Emulator not found at index {emulator_index}")

            running_processes = self.process_monitor.detect_running_emulators()
            return self._validate_single_emulator(emulator_state, running_processes)
        else:
            return self._validate_emulators()

    def reset_restart_counters(self, emulator_index: Optional[int] = None) -> None:
        """
        Reset restart attempt counters.

        Args:
            emulator_index: Optional index of specific emulator.
                          If None, resets all counters.
        """
        if emulator_index is not None:
            self.restart_attempts.pop(emulator_index, None)
            self.last_restart_time.pop(emulator_index, None)
        else:
            self.restart_attempts.clear()
            self.last_restart_time.clear()
