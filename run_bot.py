"""
Discord bot launcher script.
"""

import os
import sys
import ctypes
from dotenv import load_dotenv
from discord_bot.bot import create_bot
from shared.updater import check_and_prompt


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return True  # non-Windows / can't determine -> don't block startup


def _relaunch_as_admin() -> bool:
    """Relaunch this program elevated (UAC prompt). Returns True if started."""
    try:
        argv = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
        params = " ".join(f'"{a}"' for a in argv)
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        return rc > 32
    except Exception as e:
        print(f"[WARN] Could not request administrator elevation: {e}")
        return False


def _app_dir() -> str:
    # When frozen by PyInstaller --onefile, __file__ points to the temp
    # extraction dir; the user's .env lives next to the .exe instead.
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def main():
    """Main entry point for Discord bot."""
    # GUI control of the (elevated) ROKBot window and the freeze watchdog require
    # administrator rights. Request elevation up-front so the operator just clicks
    # the UAC prompt instead of remembering to "Run as administrator".
    if os.name == "nt" and not _is_admin():
        print("[INFO] Requesting administrator privileges (needed for GUI control / watchdog)...")
        if _relaunch_as_admin():
            return  # the elevated instance takes over; this one exits
        print("[WARN] Continuing WITHOUT admin - GUI control and the watchdog may not work.")

    script_dir = _app_dir()
    env_path = os.path.join(script_dir, '.env')

    # Load environment variables from .env file
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        print(f"Error: .env file not found at {env_path}")
        print("Please create a .env file with DISCORD_BOT_TOKEN=your_token_here")
        input("Press Enter to exit...")
        return

    # Check for updates before doing anything else. Exits the process
    # if the user accepts an update so the relauncher can swap files in.
    check_and_prompt()
    
    # Get Discord token
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in .env file")
        print("Please add DISCORD_BOT_TOKEN=your_token_here to .env file")
        input("Press Enter to exit...")
        return
    
    # Get WhaleBots path
    whalebots_path = os.getenv("WHALEBOTS_PATH")
    if not whalebots_path:
        print("Warning: WHALEBOTS_PATH not set, using current directory")
        whalebots_path = os.getcwd()
    
    print("Starting WhaleBots Discord Bot...")
    print(f"WhaleBots path: {whalebots_path}")
    
    # Create and run bot
    bot = create_bot(whalebots_path)
    
    try:
        bot.run(token)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error running bot: {e}")


if __name__ == "__main__":
    main()

