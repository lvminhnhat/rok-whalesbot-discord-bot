"""
State management module for WhaleBots automation platform.

This module provides comprehensive state management for emulator configurations
with proper error handling, caching, security validation, and performance
optimizations.
"""

import json
import os
import re  # Added for regex fallback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

try:
    from ..config import FileConfiguration, SecurityConfiguration
    from ..exceptions import (
        EmulatorError, EmulatorNotFoundError, EmulatorStateError,
        FileOperationError, ValidationError, handle_exception
    )
    from ..logger import get_logger, log_performance
    from ..utils import SecureFileHandler
except ImportError:
    # Fallback for running tests directly
    from whalebots_automation.config import FileConfiguration, SecurityConfiguration
    from whalebots_automation.exceptions import (
        EmulatorError, EmulatorNotFoundError, EmulatorStateError,
        FileOperationError, ValidationError, handle_exception
    )
    from whalebots_automation.logger import get_logger, log_performance
    from whalebots_automation.utils import SecureFileHandler


@dataclass
class EmulatorInfo:
    """Container for emulator information."""
    name: str
    device_id: str
    vm_name: str
    executable_path: str
    working_directory: str
    command_line: str
    emulator_type: int = 0

    def __post_init__(self) -> None:
        """Validate emulator info after initialization."""
        if not self.name:
            raise ValidationError("Emulator name cannot be empty")
        if not self.device_id:
            raise ValidationError("Device ID cannot be empty")


@dataclass
class EmulatorState:
    """Container for emulator state information."""
    index: int
    state: int
    emulator_info: EmulatorInfo
    game_info: Dict[str, Any] = field(default_factory=dict)
    common_info: Dict[str, Any] = field(default_factory=dict)
    full_account_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if emulator is currently active."""
        return self.state > 0

    @property
    def is_inactive(self) -> bool:
        """Check if emulator is currently inactive."""
        return self.state == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'index': self.index,
            'state': self.state,
            'emulator_info': {
                'name': self.emulator_info.name,
                'device_id': self.emulator_info.device_id,
                'vm_name': self.emulator_info.vm_name,
                'executable_path': self.emulator_info.executable_path,
                'working_directory': self.emulator_info.working_directory,
                'command_line': self.emulator_info.command_line,
                'type': self.emulator_info.emulator_type
            },
            'game_info': self.game_info,
            'common_info': self.common_info,
            'full_account_data': self.full_account_data
        }


@dataclass
class StateSummary:
    """Container for state summary information."""
    total_emulators: int
    active_count: int
    inactive_count: int
    states: List[int]
    emulator_details: List[EmulatorState]

    @property
    def active_emulators(self) -> List[EmulatorState]:
        """Get list of active emulators."""
        return [emu for emu in self.emulator_details if emu.is_active]

    @property
    def inactive_emulators(self) -> List[EmulatorState]:
        """Get list of inactive emulators."""
        return [emu for emu in self.emulator_details if emu.is_inactive]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'total_emulators': self.total_emulators,
            'active_count': self.active_count,
            'inactive_count': self.inactive_count,
            'states': self.states,
            'emulator_details': [emu.to_dict() for emu in self.emulator_details]
        }


class IStateValidator(ABC):
    """Interface for state validation operations."""

    @abstractmethod
    def validate_emulator_state(self, state: EmulatorState) -> bool:
        """Validate emulator state data."""
        pass

    @abstractmethod
    def validate_state_array(self, states: List[int]) -> bool:
        """Validate state array data."""
        pass


class StateValidator(IStateValidator):
    """Implementation of state validation logic."""

    def __init__(self, config: SecurityConfiguration):
        """
        Initialize state validator.

        Args:
            config: Security configuration
        """
        self.config = config
        self.logger = get_logger(f"{__name__}.StateValidator")

    def validate_emulator_state(self, state: EmulatorState) -> bool:
        """
        Validate emulator state data.

        Args:
            state: Emulator state to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Validate index
            if state.index < 0:
                self.logger.warning(f"Invalid emulator index: {state.index}")
                return False

            # Validate state value
            if state.state < 0:
                self.logger.warning(f"Invalid state value: {state.state}")
                return False

            # Validate emulator info
            if not state.emulator_info.name:
                self.logger.warning("Emulator name is empty")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating emulator state: {e}")
            return False

    def validate_state_array(self, states: List[int]) -> bool:
        """
        Validate state array data.

        Args:
            states: State array to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            if not isinstance(states, list):
                self.logger.warning("State data is not a list")
                return False

            for i, state in enumerate(states):
                if not isinstance(state, int):
                    self.logger.warning(f"State at index {i} is not an integer: {state}")
                    return False

                if state < 0:
                    self.logger.warning(f"State at index {i} is negative: {state}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating state array: {e}")
            return False


class EmulatorStateManager:
    """
    Manages emulator state data with comprehensive error handling and logging.

    This class provides a robust interface for managing emulator states
    with file I/O operations, validation, caching, and security features.
    """

    def __init__(
        self,
        base_path: Optional[str] = None,
        file_config: Optional[FileConfiguration] = None,
        security_config: Optional[SecurityConfiguration] = None
    ):
        """
        Initialize emulator state manager.

        Args:
            base_path: Base path to WhaleBots application directory
            file_config: File configuration settings
            security_config: Security configuration settings
        """
        # Set up configurations
        if base_path:
            self.base_path = os.path.abspath(base_path)
        else:
            self.base_path = os.getcwd()

        self.file_config = file_config or FileConfiguration()
        self.security_config = security_config or SecurityConfiguration()
        self.file_config.base_path = self.base_path

        # Initialize components
        self.file_handler = SecureFileHandler(self.file_config)
        self.validator = StateValidator(self.security_config)
        self.logger = get_logger(f"{__name__}.EmulatorStateManager")

        # Cache for performance optimization
        self._state_cache: Optional[List[EmulatorState]] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = self.file_config.cache_ttl_seconds

        self.logger.info(f"EmulatorStateManager initialized with base path: {self.base_path}")

    @log_performance()
    def read_last_state(self) -> List[int]:
        """
        Read the last_state file and return the state array.

        Returns:
            List of integers representing the state for each emulator.
            Returns empty list if file doesn't exist or is invalid.

        Raises:
            FileOperationError: If file read fails
        """
        operation_id = self.logger.log_operation_start("read_last_state")

        try:
            content = self.file_handler.read_text(self.file_config.last_state_file_path)
            if content is None:
                self.logger.info("Last state file does not exist")
                self.logger.log_operation_end(operation_id, success=True)
                return []

            # Parse the content as a JSON array
            if content.strip().startswith('[') and content.strip().endswith(']'):
                states = json.loads(content)
            else:
                self.logger.warning("Last state file does not contain valid JSON array")
                self.logger.log_operation_end(operation_id, success=False)
                return []

            # Validate the state array
            if not self.validator.validate_state_array(states):
                raise EmulatorStateError("Invalid state array data")

            self.logger.debug(f"Read {len(states)} states from last_state file")
            self.logger.log_operation_end(operation_id, success=True)
            return states

        except json.JSONDecodeError as e:
            raise FileOperationError(
                f"Invalid JSON in last_state file: {e}",
                file_path=self.file_config.last_state_file_path,
                operation="read"
            )

    @log_performance()
    def read_accounts(self) -> List[Dict[str, Any]]:
        """
        Read the Accounts.json file to get emulator information.

        Returns:
            List of account dictionaries containing emulator information.
            Returns empty list if file doesn't exist or is invalid.

        Raises:
            FileOperationError: If file read fails
        """
        operation_id = self.logger.log_operation_start("read_accounts")

        try:
            content = self.file_handler.read_text(self.file_config.accounts_file_path)
            if content is None:
                self.logger.info("Accounts file does not exist")
                self.logger.log_operation_end(operation_id, success=True)
                return []

            try:
                # Try full JSON parse first
                accounts = json.loads(content)
            except json.JSONDecodeError as e:
                self.logger.warning(f"JSON parse failed: {e}. Trying to clean and parse again...")
                
                try:
                    # Try cleaning invalid control characters
                    cleaned_content = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', content)
                    accounts = json.loads(cleaned_content)
                    self.logger.info(f"Successfully parsed after cleaning. Found {len(accounts)} accounts.")
                except json.JSONDecodeError as e2:
                    self.logger.warning(f"Cleaned parse also failed: {e2}. Falling back to regex extraction.")
                    
                    # Fallback: Use regex to extract all emuInfo fields
                    pattern = r'"emuInfo"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]*)"[^}]*\}'
                    matches = re.finditer(pattern, content)
                    accounts = []
                    
                    for i, match in enumerate(matches):
                        full_block = match.group(0)
                        
                        # Extract all fields with regex
                        name_match = re.search(r'"name"\s*:\s*"([^"]*)"', full_block)
                        device_id_match = re.search(r'"deviceId"\s*:\s*"([^"]*)"', full_block)
                        vm_name_match = re.search(r'"vmName"\s*:\s*"([^"]*)"', full_block)
                        exec_path_match = re.search(r'"executablePath"\s*:\s*"([^"]*)"', full_block)
                        work_dir_match = re.search(r'"workingDirectory"\s*:\s*"([^"]*)"', full_block)
                        cmd_line_match = re.search(r'"commandLine"\s*:\s*"([^"]*)"', full_block)
                        type_match = re.search(r'"type"\s*:\s*(\d+)', full_block)
                        
                        accounts.append({
                            'emuInfo': {
                                'name': name_match.group(1) if name_match else f'Emulator_{i}',
                                'deviceId': device_id_match.group(1) if device_id_match else '',
                                'vmName': vm_name_match.group(1) if vm_name_match else '',
                                'executablePath': exec_path_match.group(1) if exec_path_match else '',
                                'workingDirectory': work_dir_match.group(1) if work_dir_match else '',
                                'commandLine': cmd_line_match.group(1) if cmd_line_match else '',
                                'type': int(type_match.group(1)) if type_match else 0
                            },
                            'gameInfo': {},
                            'commonInfo': {}
                        })
                    
                    self.logger.info(f"Extracted {len(accounts)} accounts via regex fallback.")

            if not isinstance(accounts, list):
                raise ValidationError("Accounts file must contain an array")

            self.logger.debug(f"Read {len(accounts)} accounts from Accounts.json")
            self.logger.log_operation_end(operation_id, success=True)
            return accounts

        except Exception as e:
            self.logger.log_operation_end(operation_id, success=False)
            raise

    def _get_cached_states(self, force_refresh: bool = False) -> List[EmulatorState]:
        """
        Get emulator states from cache or refresh if needed.

        Args:
            force_refresh: Force cache refresh even if not expired

        Returns:
            List of emulator states
        """
        current_time = datetime.now().timestamp()

        if (self._state_cache is None or
            force_refresh or
            (current_time - self._cache_timestamp) > self._cache_ttl):

            # Refresh cache
            self._state_cache = self._refresh_state_cache()
            self._cache_timestamp = current_time

        return self._state_cache or []

    def _refresh_state_cache(self) -> List[EmulatorState]:
        """
        Refresh the state cache by reading from files.

        Returns:
            List of updated emulator states
        """
        self.logger.debug("Refreshing emulator state cache")

        # Read both data sources
        last_state = self.read_last_state()
        accounts = self.read_accounts()

        emulator_states = []

        # Combine the data
        for i, account in enumerate(accounts):
            try:
                emulator_info_data = account.get('emuInfo', {})
                state_value = last_state[i] if i < len(last_state) else 0

                # Create EmulatorInfo object (with defaults if fields missing)
                emulator_info = EmulatorInfo(
                    name=emulator_info_data.get('name', f'Emulator_{i}'),
                    device_id=emulator_info_data.get('deviceId', ''),
                    vm_name=emulator_info_data.get('vmName', ''),
                    executable_path=emulator_info_data.get('executablePath', ''),
                    working_directory=emulator_info_data.get('workingDirectory', ''),
                    command_line=emulator_info_data.get('commandLine', ''),
                    emulator_type=emulator_info_data.get('type', 0)
                )

                # Create EmulatorState object
                emulator_state = EmulatorState(
                    index=i,
                    state=state_value,
                    emulator_info=emulator_info,
                    game_info=account.get('gameInfo', {}),
                    common_info=account.get('commonInfo', {}),
                    full_account_data=account
                )

                # Validate the state
                if self.validator.validate_emulator_state(emulator_state):
                    emulator_states.append(emulator_state)
                else:
                    self.logger.warning(f"Invalid emulator state at index {i}, skipping")

            except Exception as e:
                self.logger.error(f"Error processing emulator state at index {i}: {e}")

        self.logger.debug(f"Cache refreshed with {len(emulator_states)} emulator states")
        return emulator_states

    @log_performance()
    def get_emulator_states(self) -> List[EmulatorState]:
        """
        Get the state data for each emulator by combining last_state and accounts data.

        Returns:
            List of EmulatorState objects containing emulator information with their states.
        """
        return self._get_cached_states()

    def get_emulator_state_by_index(self, index: int) -> Optional[EmulatorState]:
        """
        Get state data for a specific emulator by index.

        Args:
            index: Index of the emulator (0-based)

        Returns:
            EmulatorState object, or None if not found.

        Raises:
            ValidationError: If index is invalid
        """
        if index < 0:
            raise ValidationError("Emulator index cannot be negative")

        emulator_states = self.get_emulator_states()

        if index < len(emulator_states):
            return emulator_states[index]

        self.logger.debug(f"Emulator not found at index {index}")
        return None

    def get_emulator_state_by_name(self, name: str) -> Optional[EmulatorState]:
        """
        Get state data for a specific emulator by name.

        Args:
            name: Name of the emulator to search for

        Returns:
            EmulatorState object, or None if not found.
        """
        if not name or not isinstance(name, str):
            raise ValidationError("Emulator name must be a non-empty string")

        emulator_states = self.get_emulator_states()

        for emulator_state in emulator_states:
            if emulator_state.emulator_info.name == name:
                return emulator_state

        self.logger.debug(f"Emulator not found with name: {name}")
        return None

    def get_active_emulators(self) -> List[EmulatorState]:
        """
        Get list of emulators that are currently active (state > 0).

        Returns:
            List of EmulatorState objects for active emulators.
        """
        emulator_states = self.get_emulator_states()
        return [state for state in emulator_states if state.is_active]

    def get_inactive_emulators(self) -> List[EmulatorState]:
        """
        Get list of emulators that are currently inactive (state == 0).

        Returns:
            List of EmulatorState objects for inactive emulators.
        """
        emulator_states = self.get_emulator_states()
        return [state for state in emulator_states if state.is_inactive]

    def get_emulator_count(self) -> int:
        """
        Get the total number of configured emulators.

        Returns:
            Number of emulators configured in the accounts file.
        """
        try:
            accounts = self.read_accounts()
            return len(accounts)
        except Exception as e:
            self.logger.error(f"Error getting emulator count: {e}")
            return 0

    @log_performance()
    def get_state_summary(self) -> StateSummary:
        """
        Get a summary of all emulator states.

        Returns:
            StateSummary object containing summary information.
        """
        emulator_states = self.get_emulator_states()
        active_count = len(self.get_active_emulators())
        inactive_count = len(self.get_inactive_emulators())
        last_state = self.read_last_state()

        return StateSummary(
            total_emulators=len(emulator_states),
            active_count=active_count,
            inactive_count=inactive_count,
            states=last_state,
            emulator_details=emulator_states
        )

    @log_performance()
    def write_last_state(self, states: List[int]) -> bool:
        """
        Write the state array to the last_state file.

        Args:
            states: List of integers representing the state for each emulator.

        Returns:
            True if write was successful, False otherwise.

        Raises:
            ValidationError: If states are invalid
            FileOperationError: If write operation fails
        """
        if not self.validator.validate_state_array(states):
            raise ValidationError("Invalid state array provided")

        operation_id = self.logger.log_operation_start("write_last_state")

        try:
            # Convert to JSON and write
            success = self.file_handler.write_json(
                self.file_config.last_state_file_path,
                states
            )

            if success:
                # Invalidate cache
                self.invalidate_cache()
                self.logger.debug(f"Write {len(states)} states to last_state file")

            self.logger.log_operation_end(operation_id, success=success)
            return success

        except Exception as e:
            self.logger.log_operation_end(operation_id, success=False)
            raise

    def update_emulator_state(self, emulator_index: int, new_state: int) -> bool:
        """
        Update the state of a specific emulator.

        Args:
            emulator_index: Index of the emulator to update (0-based).
            new_state: New state value to set.

        Returns:
            True if update was successful, False otherwise.

        Raises:
            ValidationError: If parameters are invalid
            EmulatorStateError: If emulator not found
        """
        if emulator_index < 0:
            raise ValidationError("Emulator index cannot be negative")

        if new_state < 0:
            raise ValidationError("State value cannot be negative")

        operation_id = self.logger.log_operation_start(
            "update_emulator_state",
            emulator_index=emulator_index,
            new_state=new_state
        )

        try:
            # Read current states
            current_states = self.read_last_state()

            # Ensure the array is long enough
            while len(current_states) <= emulator_index:
                current_states.append(0)

            # Update the specific emulator state
            current_states[emulator_index] = new_state

            # Write back to file
            success = self.write_last_state(current_states)

            self.logger.log_operation_end(operation_id, success=success)
            return success

        except Exception as e:
            self.logger.log_operation_end(operation_id, success=False)
            raise

    def set_emulator_active(self, emulator_index: int) -> bool:
        """
        Set an emulator as active (state = 1).

        Args:
            emulator_index: Index of the emulator to activate.

        Returns:
            True if successful, False otherwise.
        """
        return self.update_emulator_state(emulator_index, 1)

    def set_emulator_inactive(self, emulator_index: int) -> bool:
        """
        Set an emulator as inactive (state = 0).

        Args:
            emulator_index: Index of the emulator to deactivate.

        Returns:
            True if successful, False otherwise.
        """
        return self.update_emulator_state(emulator_index, 0)

    def get_index_emulator_by_name(self, name: str) -> int:
        """
        Get the index of an emulator by its name.

        Args:
            name: Name of the emulator to find

        Returns:
            Index of the emulator, or -1 if not found
        """
        if not name:
            return -1

        emulator_states = self.get_emulator_states()

        for emulator_state in emulator_states:
            if emulator_state.emulator_info.name == name:
                return emulator_state.index

        return -1

    def is_device_active(self, device_identifier: Union[str, int]) -> bool:
        """
        Check if a device/emulator is currently active by name or index.

        Args:
            device_identifier: Device identifier - can be string (name) or number/integer (index)

        Returns:
            True if the device is active (state > 0), False otherwise.
        """
        try:
            # If the identifier is a number, treat it as an index
            if isinstance(device_identifier, (int, float)) or str(device_identifier).isdigit():
                index = int(device_identifier)
                emulator_state = self.get_emulator_state_by_index(index)
                if emulator_state:
                    return emulator_state.is_active
                return False

            # If the identifier is a string, treat it as a name
            else:
                device_name = str(device_identifier)
                emulator_state = self.get_emulator_state_by_name(device_name)
                if emulator_state:
                    return emulator_state.is_active

                # Try to convert to integer index if name doesn't match
                if device_name.isdigit():
                    index = int(device_name)
                    emulator_state = self.get_emulator_state_by_index(index)
                    if emulator_state:
                        return emulator_state.is_active

                return False

        except Exception as e:
            self.logger.error(f"Error checking device active status: {e}")
            return False

    def invalidate_cache(self) -> None:
        """Invalidate the internal state cache."""
        self._state_cache = None
        self._cache_timestamp = 0
        self.file_handler.invalidate_cache()
        self.logger.debug("State cache invalidated")

    def validate_configuration(self) -> Tuple[bool, List[str]]:
        """
        Validate the overall configuration.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        try:
            # Check if base path exists
            if not os.path.exists(self.base_path):
                errors.append(f"Base path does not exist: {self.base_path}")

            # Check if apps directory exists
            apps_path = os.path.join(self.base_path, self.file_config.apps_directory)
            if not os.path.exists(apps_path):
                errors.append(f"Apps directory does not exist: {apps_path}")

            # Check if Rise of Kingdoms bot directory exists
            rok_path = self.file_config.rise_of_kingdoms_path
            if not os.path.exists(rok_path):
                errors.append(f"Rise of Kingdoms bot directory does not exist: {rok_path}")

            # Check if accounts file exists
            if not os.path.exists(self.file_config.accounts_file_path):
                errors.append(f"Accounts file does not exist: {self.file_config.accounts_file_path}")
            else:
                # Try to read accounts file
                try:
                    accounts = self.read_accounts()
                    if not accounts:
                        errors.append("Accounts file is empty or invalid")
                except Exception as e:
                    errors.append(f"Failed to read accounts file: {e}")

        except Exception as e:
            errors.append(f"Configuration validation error: {e}")

        is_valid = len(errors) == 0
        return is_valid, errors


# Convenience function for quick usage
def create_state_manager(base_path: Optional[str] = None) -> EmulatorStateManager:
    """
    Convenience function to create an EmulatorStateManager.

    Args:
        base_path: Base path to the WhaleBots application directory.

    Returns:
        Configured EmulatorStateManager instance
    """
    return EmulatorStateManager(base_path)