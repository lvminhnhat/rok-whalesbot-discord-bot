"""
Flask dashboard launcher script.
"""

import os
from dotenv import load_dotenv
from web_dashboard.app import create_app


def main():
    """Main entry point for Flask dashboard."""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    
    # Load environment variables from .env file
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        print(f"Warning: .env file not found at {env_path}")
        print("Using default settings...")
    
    # Get configuration
    whalebots_path = os.getenv("WHALEBOTS_PATH")
    if not whalebots_path:
        print("Warning: WHALEBOTS_PATH not set, using current directory")
        whalebots_path = os.getcwd()
    
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    
    print("=" * 60)
    print("WhaleBots Web Dashboard")
    print("=" * 60)
    print(f"WhaleBots path: {whalebots_path}")
    print(f"Server: http://{host}:{port}")
    print(f"Debug mode: {debug}")
    print()
    print("WARNING: This dashboard has NO authentication!")
    print("Only run on localhost or secure network.")
    print("=" * 60)
    print()
    
    # Create and run app
    app = create_app(whalebots_path)
    
    try:
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\nDashboard stopped by user")
    except Exception as e:
        print(f"Error running dashboard: {e}")


if __name__ == "__main__":
    main()
