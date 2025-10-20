"""
Test suite for WhaleBots automation platform.

This module provides comprehensive tests for all components of the WhaleBots
automation system, including configuration, state management, UI automation,
and error handling.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Test configuration
TEST_BASE_PATH = os.path.dirname(os.path.abspath(__file__))
TEST_DATA_DIR = os.path.join(TEST_BASE_PATH, "test_data")

# Import the modules to test
# Handle both relative and absolute imports for test flexibility
try:
    # Try relative imports first (when run as module)
    from .config import (
        WhaleBotsConfiguration, UIConfiguration, FileConfiguration,
        LoggingConfiguration, ProcessConfiguration, SecurityConfiguration,
        load_config, create_default_config
    )
    from .exceptions import (
        WhaleBotsError, ConfigurationError, ValidationError,
        EmulatorNotFoundError, EmulatorStateError
    )
    from .core.state import (
        EmulatorStateManager, EmulatorState, EmulatorInfo, StateValidator
    )
    from .utils import SecureFileHandler, FileCache, BackupManager
    from .logger import WhaleBotsLogger
except ImportError:
    # Fallback to absolute imports (when run directly)
    from config import (
        WhaleBotsConfiguration, UIConfiguration, FileConfiguration,
        LoggingConfiguration, ProcessConfiguration, SecurityConfiguration,
        load_config, create_default_config
    )
    from exceptions import (
        WhaleBotsError, ConfigurationError, ValidationError,
        EmulatorNotFoundError, EmulatorStateError, SecurityError
    )
    from core.state import (
        EmulatorStateManager, EmulatorState, EmulatorInfo, StateValidator
    )
    from utils import SecureFileHandler, FileCache, BackupManager
    from logger import WhaleBotsLogger


class TestConfiguration(unittest.TestCase):
    """Test configuration management."""

    def test_ui_configuration_defaults(self):
        """Test UI configuration default values."""
        config = UIConfiguration()
        self.assertEqual(config.window_title_pattern, r".*Rise of Kingdoms Bot.*")
        self.assertEqual(config.base_x_coordinate, 16)
        self.assertEqual(config.base_y_coordinate, 14)
        self.assertEqual(config.step_size, 20)
        self.assertEqual(config.max_visible_items, 6)

    def test_file_configuration_paths(self):
        """Test file configuration path generation."""
        config = FileConfiguration(base_path="/test/path")

        expected_rok_path = os.path.join("/test/path", "Apps", "rise-of-kingdoms-bot", "Settings")
        self.assertEqual(config.rise_of_kingdoms_path, expected_rok_path)

        expected_accounts_path = os.path.join(expected_rok_path, "Accounts.json")
        self.assertEqual(config.accounts_file_path, expected_accounts_path)

    def test_whalebots_configuration_validation(self):
        """Test WhaleBots configuration validation."""
        # Test invalid coordinates
        config = WhaleBotsConfiguration()
        config.ui.base_x_coordinate = -1

        with self.assertRaises(ValueError):
            config._validate_configuration()

    def test_configuration_from_dict(self):
        """Test creating configuration from dictionary."""
        config_data = {
            "ui": {
                "base_x_coordinate": 100,
                "step_size": 25
            },
            "environment": "test"
        }

        config = WhaleBotsConfiguration.from_dict(config_data)
        self.assertEqual(config.ui.base_x_coordinate, 100)
        self.assertEqual(config.ui.step_size, 25)
        self.assertEqual(config.environment, "test")

    def test_configuration_save_load(self):
        """Test saving and loading configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name

        try:
            # Create and save configuration
            original_config = create_default_config()
            original_config.environment = "test"
            original_config.save_to_file(config_path)

            # Load configuration
            loaded_config = WhaleBotsConfiguration.from_file(config_path)

            self.assertEqual(loaded_config.environment, "test")
            self.assertEqual(loaded_config.ui.base_x_coordinate, original_config.ui.base_x_coordinate)

        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)


class TestExceptions(unittest.TestCase):
    """Test custom exception classes."""

    def test_whalebots_error_creation(self):
        """Test WhaleBotsError creation and serialization."""
        error = WhaleBotsError("Test error", "ERR001", {"context": "test"})

        self.assertEqual(str(error), "[ERR001] Test error")
        self.assertEqual(error.error_code, "ERR001")
        self.assertEqual(error.details["context"], "test")

        error_dict = error.to_dict()
        self.assertEqual(error_dict["exception_type"], "WhaleBotsError")
        self.assertEqual(error_dict["message"], "Test error")

    def test_emulator_not_found_error(self):
        """Test EmulatorNotFoundError creation."""
        error = EmulatorNotFoundError("TestEmulator", "name")

        self.assertEqual(error.emulator_identifier, "TestEmulator")
        self.assertEqual(error.identifier_type, "name")
        self.assertIn("TestEmulator", str(error))

    def test_emulator_state_error(self):
        """Test EmulatorStateError creation."""
        error = EmulatorStateError("State error", emulator_index=5, current_state=1)

        self.assertEqual(error.emulator_index, 5)
        self.assertEqual(error.current_state, 1)


class TestFileCache(unittest.TestCase):
    """Test file cache functionality."""

    def setUp(self):
        """Set up test cache."""
        self.cache = FileCache(max_size=3, default_ttl=1)

    def test_cache_put_get(self):
        """Test putting and getting cache entries."""
        self.cache.put("test_key", "test_data")
        result = self.cache.get("test_key")

        self.assertEqual(result, "test_data")

    def test_cache_miss(self):
        """Test cache miss scenarios."""
        result = self.cache.get("nonexistent_key")
        self.assertIsNone(result)

    def test_cache_ttl(self):
        """Test cache TTL expiration."""
        self.cache.put("test_key", "test_data")

        # Should be valid immediately
        result = self.cache.get("test_key")
        self.assertEqual(result, "test_data")

        # Simulate TTL expiration
        self.cache._cache["test_key"].timestamp = 0
        result = self.cache.get("test_key")
        self.assertIsNone(result)

    def test_cache_eviction(self):
        """Test cache eviction when full."""
        self.cache.put("key1", "data1")
        self.cache.put("key2", "data2")
        self.cache.put("key3", "data3")
        self.cache.put("key4", "data4")  # Should evict oldest

        self.assertIsNone(self.cache.get("key1"))
        self.assertEqual(self.cache.get("key4"), "data4")


class TestSecureFileHandler(unittest.TestCase):
    """Test secure file handler functionality."""

    def setUp(self):
        """Set up test file handler."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = FileConfiguration(
            base_path=self.temp_dir,
            enable_file_cache=True,
            cache_ttl_seconds=1
        )
        self.handler = SecureFileHandler(self.config)

    def tearDown(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_write_json(self):
        """Test JSON file reading and writing."""
        test_data = {"key": "value", "number": 42}
        file_path = os.path.join(self.temp_dir, "test.json")

        # Write data
        success = self.handler.write_json(file_path, test_data)
        self.assertTrue(success)

        # Read data
        read_data = self.handler.read_json(file_path)
        self.assertEqual(read_data, test_data)

    def test_read_write_text(self):
        """Test text file reading and writing."""
        test_text = "Hello, World!"
        file_path = os.path.join(self.temp_dir, "test.txt")

        # Write data
        success = self.handler.write_text(file_path, test_text)
        self.assertTrue(success)

        # Read data
        read_text = self.handler.read_text(file_path)
        self.assertEqual(read_text, test_text)

    def test_file_validation(self):
        """Test file path validation."""
        # Test path traversal attempt
        with self.assertRaises(SecurityError):
            self.handler._validate_file_path("../../../etc/passwd")

    def test_caching(self):
        """Test file caching functionality."""
        test_data = {"key": "cached_value"}
        file_path = os.path.join(self.temp_dir, "cache_test.json")

        # Write data
        self.handler.write_json(file_path, test_data)

        # First read should hit file system
        read_data1 = self.handler.read_json(file_path)
        self.assertEqual(read_data1, test_data)

        # Second read should hit cache
        read_data2 = self.handler.read_json(file_path)
        self.assertEqual(read_data2, test_data)

    def test_backup_creation(self):
        """Test backup file creation."""
        test_data = {"key": "backup_test"}
        file_path = os.path.join(self.temp_dir, "backup_test.json")

        # Create initial file
        self.handler.write_json(file_path, test_data)

        # Modify file (should create backup)
        modified_data = {"key": "modified_value"}
        self.handler.write_json(file_path, modified_data)

        # Check that backup was created
        backup_manager = self.handler.backup_manager
        backups = backup_manager.list_backups(file_path)
        self.assertGreater(len(backups), 0)


class TestStateValidator(unittest.TestCase):
    """Test state validation functionality."""

    def setUp(self):
        """Set up test validator."""
        from config import SecurityConfiguration
        from exceptions import SecurityError
        self.config = SecurityConfiguration()
        self.validator = StateValidator(self.config)

    def test_valid_emulator_state(self):
        """Test validation of valid emulator state."""
        emulator_info = EmulatorInfo(
            name="TestEmulator",
            device_id="test_device",
            vm_name="TestVM",
            executable_path="C:\\test.exe",
            working_directory="C:\\test",
            command_line="test args"
        )

        state = EmulatorState(
            index=0,
            state=1,
            emulator_info=emulator_info
        )

        self.assertTrue(self.validator.validate_emulator_state(state))

    def test_invalid_emulator_state(self):
        """Test validation of invalid emulator state."""
        # Test negative index
        emulator_info = EmulatorInfo(
            name="TestEmulator",
            device_id="test_device",
            vm_name="TestVM",
            executable_path="C:\\test.exe",
            working_directory="C:\\test",
            command_line="test args"
        )

        state = EmulatorState(
            index=-1,  # Invalid
            state=1,
            emulator_info=emulator_info
        )

        self.assertFalse(self.validator.validate_emulator_state(state))

    def test_valid_state_array(self):
        """Test validation of valid state array."""
        states = [0, 1, 0, 1, 1]
        self.assertTrue(self.validator.validate_state_array(states))

    def test_invalid_state_array(self):
        """Test validation of invalid state array."""
        # Test non-integer value
        states = [0, 1, "invalid", 1]
        self.assertFalse(self.validator.validate_state_array(states))


class TestEmulatorStateManager(unittest.TestCase):
    """Test emulator state manager functionality."""

    def setUp(self):
        """Set up test state manager."""
        self.temp_dir = tempfile.mkdtemp()

        # Create test directory structure
        apps_dir = os.path.join(self.temp_dir, "Apps", "rise-of-kingdoms-bot", "Settings")
        os.makedirs(apps_dir, exist_ok=True)

        # Create test accounts file
        accounts_data = [
            {
                "emuInfo": {
                    "name": "TestEmulator1",
                    "deviceId": "device1",
                    "vmName": "VM1",
                    "executablePath": "C:\\emulator1.exe",
                    "workingDirectory": "C:\\emulator1",
                    "commandLine": "-args",
                    "type": 0
                },
                "gameInfo": {"game": "ROK"},
                "commonInfo": {"common": "data"}
            },
            {
                "emuInfo": {
                    "name": "TestEmulator2",
                    "deviceId": "device2",
                    "vmName": "VM2",
                    "executablePath": "C:\\emulator2.exe",
                    "workingDirectory": "C:\\emulator2",
                    "commandLine": "-args",
                    "type": 0
                },
                "gameInfo": {"game": "ROK"},
                "commonInfo": {"common": "data"}
            }
        ]

        accounts_file = os.path.join(apps_dir, "Accounts.json")
        with open(accounts_file, 'w') as f:
            json.dump(accounts_data, f)

        # Create test state file
        state_file = os.path.join(apps_dir, "last_state")
        with open(state_file, 'w') as f:
            json.dump([1, 0], f)  # First emulator active, second inactive

        self.manager = EmulatorStateManager(base_path=self.temp_dir)

    def tearDown(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_accounts(self):
        """Test reading accounts file."""
        accounts = self.manager.read_accounts()
        self.assertEqual(len(accounts), 2)
        self.assertEqual(accounts[0]["emuInfo"]["name"], "TestEmulator1")

    def test_read_last_state(self):
        """Test reading last state file."""
        states = self.manager.read_last_state()
        self.assertEqual(states, [1, 0])

    def test_get_emulator_states(self):
        """Test getting emulator states."""
        emulator_states = self.manager.get_emulator_states()
        self.assertEqual(len(emulator_states), 2)
        self.assertEqual(emulator_states[0].emulator_info.name, "TestEmulator1")
        self.assertTrue(emulator_states[0].is_active)
        self.assertFalse(emulator_states[1].is_active)

    def test_get_emulator_by_index(self):
        """Test getting emulator by index."""
        emulator = self.manager.get_emulator_state_by_index(0)
        self.assertIsNotNone(emulator)
        self.assertEqual(emulator.emulator_info.name, "TestEmulator1")

        # Test invalid index
        emulator = self.manager.get_emulator_state_by_index(99)
        self.assertIsNone(emulator)

    def test_get_emulator_by_name(self):
        """Test getting emulator by name."""
        emulator = self.manager.get_emulator_state_by_name("TestEmulator1")
        self.assertIsNotNone(emulator)
        self.assertEqual(emulator.index, 0)

        # Test invalid name
        emulator = self.manager.get_emulator_state_by_name("NonExistent")
        self.assertIsNone(emulator)

    def test_get_active_emulators(self):
        """Test getting active emulators."""
        active = self.manager.get_active_emulators()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].emulator_info.name, "TestEmulator1")

    def test_update_emulator_state(self):
        """Test updating emulator state."""
        # Deactivate first emulator
        success = self.manager.set_emulator_inactive(0)
        self.assertTrue(success)

        # Verify state was updated
        states = self.manager.read_last_state()
        self.assertEqual(states[0], 0)

    def test_is_device_active(self):
        """Test checking if device is active."""
        # Test by index
        self.assertTrue(self.manager.is_device_active(0))
        self.assertFalse(self.manager.is_device_active(1))

        # Test by name
        self.assertTrue(self.manager.is_device_active("TestEmulator1"))
        self.assertFalse(self.manager.is_device_active("TestEmulator2"))

    def test_validate_configuration(self):
        """Test configuration validation."""
        is_valid, errors = self.manager.validate_configuration()
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)


class TestLogger(unittest.TestCase):
    """Test logging functionality."""

    def setUp(self):
        """Set up test logger."""
        from config import LoggingConfiguration
        self.config = LoggingConfiguration(enable_console_logging=False)
        self.logger = WhaleBotsLogger("test_logger", self.config)

    def test_logger_creation(self):
        """Test logger creation."""
        self.assertIsNotNone(self.logger)
        self.assertEqual(self.logger.name, "test_logger")

    def test_message_sanitization(self):
        """Test message sanitization."""
        # Test file path sanitization
        message = "Error with file C:\\Users\\secret\\password.txt"
        sanitized = self.logger._sanitize_message(message)
        self.assertIn("[FILE_PATH]", sanitized)
        self.assertNotIn("C:\\Users\\secret", sanitized)

    def test_operation_tracking(self):
        """Test operation start/end tracking."""
        operation_id = self.logger.log_operation_start("test_operation")
        self.assertIsNotNone(operation_id)

        self.logger.log_operation_end(operation_id, success=True)

    def test_exception_logging(self):
        """Test exception logging."""
        try:
            raise ValueError("Test exception")
        except Exception as e:
            # Should not raise an exception
            self.logger.log_exception(e, "test_operation")


def run_tests():
    """Run all tests."""
    # Create test suite
    test_classes = [
        TestConfiguration,
        TestExceptions,
        TestFileCache,
        TestSecureFileHandler,
        TestStateValidator,
        TestEmulatorStateManager,
        TestLogger
    ]

    suite = unittest.TestSuite()
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("Running WhaleBots Automation Test Suite...")
    print("=" * 60)

    success = run_tests()

    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")

    exit(0 if success else 1)