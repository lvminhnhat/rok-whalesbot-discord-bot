#!/usr/bin/env python3
"""
Script to test state reading functionality.
This will help verify if the state reading is working correctly.
"""

import sys
import os

# Add the whalebots_automation to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'whalebots_automation'))

from whalebots_automation.core.state import EmulatorStateManager
from whalebots_automation.config import FileConfiguration

def test_state_reading():
    """Test reading states from last_state file."""

    print("Testing state reading functionality...")

    # Initialize state manager
    try:
        file_config = FileConfiguration()
        file_config.base_path = os.getcwd()

        state_manager = EmulatorStateManager(
            base_path=os.getcwd(),
            file_config=file_config
        )

        print(f"Base path: {os.getcwd()}")
        print(f"Last state file path: {file_config.last_state_file_path}")

        # Check if file exists
        if os.path.exists(file_config.last_state_file_path):
            print("[OK] Last state file exists")

            # Read raw content
            with open(file_config.last_state_file_path, 'r') as f:
                raw_content = f.read()
            print(f"Raw content: {raw_content}")

            # Read using state manager
            states = state_manager.read_last_state()
            print(f"Parsed states: {states}")

            # Get emulator states
            emulator_states = state_manager.get_emulator_states()
            print(f"Number of emulators: {len(emulator_states)}")

            for i, state in enumerate(emulator_states):
                print(f"Emulator {i}:")
                print(f"  - Index: {state.index}")
                print(f"  - State: {state.state}")
                print(f"  - Is Active: {state.is_active}")
                print(f"  - Name: {state.emulator_info.name}")
                print()

            # Test getting state by index
            for i in range(len(states)):
                emulator_state = state_manager.get_emulator_state_by_index(i)
                if emulator_state:
                    print(f"Emulator {i} by index lookup:")
                    print(f"  - State: {emulator_state.state}")
                    print(f"  - Is Active: {emulator_state.is_active}")
                    print()
        else:
            print("[ERROR] Last state file does not exist")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_state_reading()