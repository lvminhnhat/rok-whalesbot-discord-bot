"""
Discord bot launcher script.
"""

import os
from dotenv import load_dotenv
from discord_bot.bot import create_bot


def main():
    """Main entry point for Discord bot."""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    
    # Load environment variables from .env file
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        print(f"Error: .env file not found at {env_path}")
        print("Please create a .env file with DISCORD_BOT_TOKEN=your_token_here")
        input("Press Enter to exit...")
        return
    
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

