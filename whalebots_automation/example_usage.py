#!/usr/bin/env python3
"""
Example usage of the WhaleBots automation platform.

This script demonstrates how to use the refactored WhaleBots automation system
with proper error handling, logging, and configuration management.
"""

import os
import sys
import logging
from pathlib import Path

# Add the whalebots_automation directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from whalebots_automation import (
    WhaleBots, create_whalesbot, create_default_config,
    get_logger, setup_global_logging
)
from whalebots_automation.exceptions import WhaleBotsError


def setup_logging():
    """Set up logging for the example."""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/whalebots_example.log'),
            logging.StreamHandler()
        ]
    )


def example_basic_usage():
    """Example of basic WhaleBots usage."""
    print("\n" + "="*60)
    print("BASIC USAGE EXAMPLE")
    print("="*60)

    try:
        # Create WhaleBots instance using current directory
        whalesbot = create_whalesbot()

        # Get emulator states
        states = whalesbot.get_emulator_states()
        print(f"Found {len(states)} configured emulators")

        if states:
            # Print emulator information
            for state in states:
                status = "Active" if state.is_active else "Inactive"
                print(f"  Emulator {state.index}: {state.emulator_info.name} - {status}")

            # Get state summary
            summary = whalesbot.get_state_summary()
            print(f"\nSummary:")
            print(f"  Total emulators: {summary['total_emulators']}")
            print(f"  Active emulators: {summary['active_count']}")
            print(f"  Inactive emulators: {summary['inactive_count']}")

            # Detect running processes
            running = whalesbot.detect_running_emulators()
            print(f"  Running processes: {len(running)}")

        else:
            print("No emulators configured")

    except WhaleBotsError as e:
        print(f"WhaleBots error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def example_advanced_usage():
    """Example of advanced WhaleBots usage."""
    print("\n" + "="*60)
    print("ADVANCED USAGE EXAMPLE")
    print("="*60)

    try:
        # Create custom configuration
        config = create_default_config()
        config.debug_mode = True
        config.logging.default_level = "DEBUG"
        config.ui.step_size = 25  # Custom step size
        config.ui.max_visible_items = 8

        # Create WhaleBots instance with custom config
        whalesbot = WhaleBots(
            path=os.getcwd(),
            config=config
        )

        # Validate configuration
        is_valid, errors = whalesbot.validate_configuration()
        if not is_valid:
            print("Configuration issues found:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("Configuration is valid")

        # Get specific emulator
        emulator = whalesbot.get_emulator_state_by_index(0)
        if emulator:
            print(f"\nFirst emulator details:")
            print(f"  Name: {emulator.emulator_info.name}")
            print(f"  Device ID: {emulator.emulator_info.device_id}")
            print(f"  Executable: {emulator.emulator_info.executable_path}")
            print(f"  Status: {'Active' if emulator.is_active else 'Inactive'}")

            # Check if emulator is running by name
            is_running = whalesbot.is_active(emulator.emulator_info.name)
            print(f"  Currently running: {is_running}")

        # Get active and inactive emulators separately
        active_emulators = whalesbot.get_active_emulators()
        inactive_emulators = whalesbot.get_inactive_emulators()

        print(f"\nActive emulators: {len(active_emulators)}")
        for emu in active_emulators:
            print(f"  - {emu.emulator_info.name} (index: {emu.index})")

        print(f"\nInactive emulators: {len(inactive_emulators)}")
        for emu in inactive_emulators:
            print(f"  - {emu.emulator_info.name} (index: {emu.index})")

    except WhaleBotsError as e:
        print(f"WhaleBots error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def example_error_handling():
    """Example of error handling."""
    print("\n" + "="*60)
    print("ERROR HANDLING EXAMPLE")
    print("="*60)

    try:
        # Try to create WhaleBots with invalid path
        whalesbot = WhaleBots("/nonexistent/path")
    except WhaleBotsError as e:
        print(f"Expected error caught: {e}")

    try:
        # Create valid WhaleBots instance
        whalesbot = create_whalesbot()

        # Try to access non-existent emulator
        emulator = whalesbot.get_emulator_state_by_index(999)
        if emulator is None:
            print("Emulator at index 999 not found (expected)")

        # Try to access emulator by invalid name
        emulator = whalesbot.get_emulator_state_by_name("NonExistentEmulator")
        if emulator is None:
            print("Emulator 'NonExistentEmulator' not found (expected)")

        # Try to start emulator with invalid index
        try:
            whalesbot.start(999)
        except WhaleBotsError as e:
            print(f"Expected error when starting invalid emulator: {e}")

    except WhaleBotsError as e:
        print(f"WhaleBots error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def example_context_manager():
    """Example of using WhaleBots with context manager."""
    print("\n" + "="*60)
    print("CONTEXT MANAGER EXAMPLE")
    print("="*60)

    try:
        with create_whalesbot() as whalesbot:
            print("WhalesBot created successfully")

            # Get state summary
            summary = whalesbot.get_state_summary()
            print(f"Total emulators: {summary['total_emulators']}")

            # Resources will be automatically cleaned up when exiting context
        print("WhalesBot cleaned up automatically")

    except WhaleBotsError as e:
        print(f"WhaleBots error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def example_configuration():
    """Example of configuration management."""
    print("\n" + "="*60)
    print("CONFIGURATION EXAMPLE")
    print("="*60)

    try:
        # Create default configuration
        config = create_default_config()
        print(f"Default configuration created")
        print(f"  UI step size: {config.ui.step_size}")
        print(f"  Debug mode: {config.debug_mode}")
        print(f"  File caching: {config.files.enable_file_cache}")

        # Modify configuration
        config.debug_mode = True
        config.ui.step_size = 30
        config.files.max_backup_files = 15

        print(f"\nModified configuration:")
        print(f"  UI step size: {config.ui.step_size}")
        print(f"  Debug mode: {config.debug_mode}")
        print(f"  Max backup files: {config.files.max_backup_files}")

        # Save configuration to file
        config_path = "example_config.json"
        config.save_to_file(config_path)
        print(f"\nConfiguration saved to {config_path}")

        # Load configuration from file
        from whalebots_automation.config import WhaleBotsConfiguration
        loaded_config = WhaleBotsConfiguration.from_file(config_path)
        print(f"Configuration loaded from {config_path}")
        print(f"  Loaded UI step size: {loaded_config.ui.step_size}")

        # Clean up
        if os.path.exists(config_path):
            os.unlink(config_path)
            print(f"Cleaned up {config_path}")

    except Exception as e:
        print(f"Configuration error: {e}")


def example_logging():
    """Example of logging functionality."""
    print("\n" + "="*60)
    print("LOGGING EXAMPLE")
    print("="*60)

    try:
        # Get a logger
        logger = get_logger("example")

        logger.info("This is an info message")
        logger.debug("This is a debug message")
        logger.warning("This is a warning message")

        # Log operation timing
        operation_id = logger.log_operation_start("example_operation")
        import time
        time.sleep(0.1)  # Simulate some work
        logger.log_operation_end(operation_id, success=True)

        # Log exception
        try:
            raise ValueError("This is a test exception")
        except Exception as e:
            logger.log_exception(e, "example_operation")

        print("Logging examples completed. Check logs/whalebots_example.log for detailed logs.")

    except Exception as e:
        print(f"Logging error: {e}")


def main():
    """Main function to run all examples."""
    print("WhaleBots Automation Platform - Example Usage")
    print("=" * 60)

    # Set up logging
    setup_logging()

    try:
        # Run examples
        example_basic_usage()
        example_advanced_usage()
        example_error_handling()
        example_context_manager()
        example_configuration()
        example_logging()

        print("\n" + "="*60)
        print("All examples completed successfully!")
        print("="*60)

    except KeyboardInterrupt:
        print("\nExamples interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error in examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()