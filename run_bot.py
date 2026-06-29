"""
Discord bot launcher script.
"""

import os
import sys
import ctypes
from dotenv import load_dotenv
from discord_bot.bot import create_bot
from shared.updater import check_and_prompt, get_current_version


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


def _run_selftest() -> None:
    """Verify the freeze-watchdog OCR works in this build (mainly: that winsdk
    bundled into the exe). Renders a known string, OCRs it, prints the result.
    No Discord, no admin needed.  Usage:  WhalesBot.exe --selftest
    """
    print(f"WhalesBot version {get_current_version()} - watchdog OCR self-test")
    try:
        from PIL import Image, ImageDraw
        from whalebots_automation.services.watchdog_reader import ocr_image
        img = Image.new("RGB", (360, 90), "white")
        ImageDraw.Draw(img).text((12, 28), "[12:34:56] selftest", fill="black")
        words, _lines = ocr_image(img, scale=2)
        text = " ".join(w.text for w in words)
        print(f"OCR result: {text!r}")
        if "selftest" in text.lower():
            print("[OK] OCR self-test PASSED - winsdk bundled correctly.")
        else:
            print("[WARN] OCR ran but didn't read the test text - inspect above.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[FAIL] OCR self-test FAILED: {e}")
    input("Press Enter to exit...")


def main():
    """Main entry point for Discord bot."""
    if "--selftest" in sys.argv:
        _run_selftest()
        return

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

    print(f"WhalesBot version {get_current_version()}")

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

