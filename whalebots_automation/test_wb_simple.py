#!/usr/bin/env python3
"""
Simple WhaleBots Start/Stop/Status Test.
"""

import os
import sys
import time
from pathlib import Path

# Add the whalebots_automation directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Direct imports
from whalesbot import create_whalesbot
from exceptions import WhaleBotsError

def print_header(title):
    """Print formatted header."""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def main():
    """Main test function."""
    print_header("WHALEBOTS START/STOP/STATUS TEST")
    print("Testing basic functionality of WhaleBots automation platform")

    try:
        # Initialize WhaleBots
        print("Initializing WhaleBots...")
        with create_whalesbot() as whalesbot:
            print("Successfully initialized!")

            # Test 1: Check emulator states
            print_header("CHECKING EMULATOR STATES")
            try:
                states = whalesbot.get_emulator_states()
                if states:
                    print(f"Found {len(states)} emulators:")
                    for i, state in enumerate(states):
                        name = state.emulator_info.name if hasattr(state, 'emulator_info') else str(state)
                        is_active = state.state > 0 if hasattr(state, 'state') else False
                        status = "RUNNING" if is_active else "STOPPED"
                        print(f"  {i}: {name} - {status}")
                else:
                    print("No emulators found!")

                # Test 2: Get summary
                summary = whalesbot.get_state_summary()
                print(f"\nSummary: {summary}")

                # Test 3: Get active emulators
                active = whalesbot.get_active_emulators()
                print(f"Active emulators: {len(active)}")

            except Exception as e:
                print(f"Error checking states: {e}")

            # Test 4: Test status checks
            print_header("TESTING STATUS CHECKS")
            try:
                if states:
                    first_state = states[0]
                    name = first_state.emulator_info.name if hasattr(first_state, 'emulator_info') else "Unknown"

                    # Check if emulator exists
                    exists = whalesbot.check_status(name)
                    print(f"Emulator '{name}' exists: {exists}")

                    # Check if active
                    is_active = whalesbot.is_active(name)
                    print(f"Emulator '{name}' is active: {is_active}")

            except Exception as e:
                print(f"Error in status checks: {e}")

            # Test 5: Test process monitoring
            print_header("TESTING PROCESS MONITORING")
            try:
                running_processes = whalesbot.detect_running_emulators()
                if running_processes:
                    print(f"Found {len(running_processes)} running processes:")
                    for i, proc in enumerate(running_processes):
                        proc_info = proc.get('process_info', {})
                        pid = proc_info.get('pid', 'N/A')
                        name = proc_info.get('name', 'N/A')
                        print(f"  {i}: PID {pid} - {name}")
                else:
                    print("No running processes found (psutil may not be available)")

            except Exception as e:
                print(f"Error in process monitoring: {e}")

    except WhaleBotsError as e:
        print(f"WhaleBots Error: {e}")
        print("Hint: Check if WhaleBots is properly installed and configured")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    print_header("TEST COMPLETED")
    print("WhaleBots automation platform test finished!")

if __name__ == "__main__":
    main()