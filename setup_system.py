"""WhaleBots system setup helper.

This script prepares local folders, configuration files, a virtual
environment, and required dependencies so that non-technical users can
launch the WhaleBots Discord bot and web dashboard with minimal effort.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

import venv


def create_directories() -> None:
    """Create required project directories."""
    print("📁 Creating directories...")

    directories = [
        Path("data"),
        Path("logs"),
        Path("web_dashboard/static/css"),
        Path("web_dashboard/static/js"),
        Path("web_dashboard/templates"),
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {directory.as_posix()}")


def create_config_json() -> None:
    """Create default data/config.json if missing."""
    print("\n⚙️  Preparing data/config.json...")

    config_file = Path("data/config.json")

    if config_file.exists():
        print("  ℹ️  config.json already exists, skipping")
        return

    default_config = {
        "allowed_guilds": [],
        "allowed_channels": [],
        "admin_roles": [],
        "admin_users": [],
        "cooldown_seconds": 60,
        "max_emulators": 20,
    }

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)

    print("  ✅ data/config.json created")


def create_users_json() -> None:
    """Create empty data/users.json if missing."""
    print("\n👥 Preparing data/users.json...")

    users_file = Path("data/users.json")

    if users_file.exists():
        print("  ℹ️  users.json already exists, skipping")
        return

    empty_users = {"users": {}}

    with open(users_file, "w", encoding="utf-8") as f:
        json.dump(empty_users, f, indent=2, ensure_ascii=False)

    print("  ✅ data/users.json created")


def create_logs_json() -> None:
    """Create empty data/audit_logs.json if missing."""
    print("\n📋 Preparing data/audit_logs.json...")

    logs_file = Path("data/audit_logs.json")

    if logs_file.exists():
        print("  ℹ️  audit_logs.json already exists, skipping")
        return

    empty_logs = {"logs": []}

    with open(logs_file, "w", encoding="utf-8") as f:
        json.dump(empty_logs, f, indent=2, ensure_ascii=False)

    print("  ✅ data/audit_logs.json created")


def ensure_env_file() -> bool:
    """Ensure a .env file exists for environment variables."""
    print("\n🔑 Checking .env file...")

    env_file = Path(".env")
    example_file = Path("env_example.txt")

    if env_file.exists():
        print("  ✅ .env file found")
        return True

    if example_file.exists():
        env_file.write_text(example_file.read_text(encoding="utf-8"), encoding="utf-8")
        print("  🆕 Created .env from env_example.txt")
        print("  ⚠️  Update DISCORD_BOT_TOKEN in .env before starting the bot")
        return False

    print("  ❌ .env file is missing and no template was found")
    print("     Create it manually with the required keys shown in env_example.txt")
    return False


def add_admin_user_hint() -> None:
    """Remind the user to add at least one admin account."""
    print("\n👤 Admin access reminder...")

    config_file = Path("data/config.json")

    if not config_file.exists():
        print("  ⚠️  data/config.json is missing; run setup again")
        return

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    if config.get("admin_users"):
        print(f"  ✅ Admin users already configured: {config['admin_users']}")
        return

    print("  ℹ️  Add your Discord User ID to data/config.json under admin_users")
    print("  How to copy your User ID in Discord:")
    print("    1. Settings ➜ Advanced ➜ enable 'Developer Mode'")
    print("    2. Right-click your name ➜ Copy ID")
    print("    3. Update data/config.json, for example:")
    print('       "admin_users": ["123456789012345678"]')


def create_virtual_environment(venv_dir: Path = Path(".venv")) -> Optional[Path]:
    """Create a virtual environment for the project."""
    print("\n🐍 Setting up virtual environment...")

    if venv_dir.exists():
        print(f"  ✅ Virtual environment already exists at {venv_dir.resolve()}")
        return venv_dir

    try:
        builder = venv.EnvBuilder(with_pip=True, upgrade=False, clear=False)
        builder.create(str(venv_dir))
        print(f"  ✅ Virtual environment created at {venv_dir.resolve()}")
        return venv_dir
    except Exception as exc:  # pragma: no cover - informational output only
        print(f"  ❌ Failed to create virtual environment: {exc}")
        print("     You can create it manually with: python -m venv .venv")
        return None


def get_venv_python(venv_dir: Path) -> Optional[Path]:
    """Return the Python executable inside the virtual environment."""
    if os.name == "nt":
        candidate = venv_dir / "Scripts" / "python.exe"
    else:
        candidate = venv_dir / "bin" / "python"

    if candidate.exists():
        return candidate

    print(f"  ❌ Unable to find Python inside {venv_dir}")
    return None


def install_dependencies(python_executable: Path) -> bool:
    """Install project dependencies using the provided Python executable."""
    print("\n📦 Installing dependencies (this may take a few minutes)...")

    pip_cmd = [str(python_executable), "-m", "pip"]

    try:
        subprocess.run(pip_cmd + ["install", "--upgrade", "pip"], check=True)
        if Path("requirements.txt").exists():
            subprocess.run(pip_cmd + ["install", "-r", "requirements.txt"], check=True)
        else:
            print("  ⚠️  requirements.txt was not found; skipping package installation")
            return False
    except subprocess.CalledProcessError as exc:  # pragma: no cover - informational output only
        print("  ❌ Failed to install dependencies")
        print(f"     {exc}")
        if os.name == "nt":
            print("     Try running: .\\.venv\\Scripts\\pip install -r requirements.txt")
        else:
            print("     Try running: ./.venv/bin/pip install -r requirements.txt")
        return False

    print("  ✅ Dependencies installed successfully")
    return True


def _module_available(python_executable: Optional[Path], module_name: str) -> bool:
    """Check whether a module can be imported using the given Python interpreter."""
    if python_executable is None:
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False

    code = (
        "import importlib.util, sys; "
        "sys.exit(0 if importlib.util.find_spec('" + module_name + "') else 1)"
    )
    result = subprocess.run([str(python_executable), "-c", code], capture_output=True)
    return result.returncode == 0


def check_dependencies(python_executable: Optional[Path] = None) -> bool:
    """Verify that required Python packages are available."""
    print("\n🔍 Verifying required packages...")

    packages = {
        "discord": "discord (py-cord)",
        "flask": "Flask",
        "dotenv": "python-dotenv",
        "pytz": "pytz",
    }

    missing = []

    for module_name, friendly_name in packages.items():
        if _module_available(python_executable, module_name):
            print(f"  ✅ {friendly_name}")
        else:
            print(f"  ❌ {friendly_name} is missing")
            missing.append(friendly_name)

    if missing:
        print("\n  ⚠️  Install the missing packages using pip and rerun this script")
        return False

    print("\n  ✅ All core packages are available")
    return True


def show_activation_help(venv_dir: Path) -> None:
    """Display instructions to activate the virtual environment."""
    print("\n▶️ Activate the virtual environment before running commands:")
    if os.name == "nt":
        print(f"   {venv_dir}\\Scripts\\activate")
    else:
        print(f"   source {venv_dir}/bin/activate")


def show_summary(env_ready: bool, deps_ready: bool, venv_dir: Optional[Path]) -> None:
    """Print the final setup summary for the user."""
    print("\n" + "=" * 60)
    print("📊 Setup summary")
    print("=" * 60)

    if env_ready and deps_ready:
        print("✅ WhaleBots is ready to run!")
    else:
        print("⚠️  Setup is not complete yet.")

    if not env_ready:
        print("  - Update the new .env file with your Discord bot token")
    if not deps_ready:
        print("  - Install the missing Python packages and rerun this script")

    print("\nNext steps:")
    if venv_dir:
        show_activation_help(venv_dir)
        python_hint = f"{venv_dir}\\Scripts\\python" if os.name == "nt" else f"{venv_dir}/bin/python"
        print(f"   {python_hint} run_bot.py")
        print(f"   {python_hint} run_dashboard.py")
    else:
        print("   python run_bot.py")
        print("   python run_dashboard.py")

    print("\nOpen the dashboard at http://127.0.0.1:5000 once it is running.")
    print("=" * 60)


def main() -> None:
    """Run the setup workflow."""
    print("=" * 60)
    print("🚀 WhaleBots Discord Bot + Web Dashboard Setup")
    print("=" * 60)

    create_directories()
    create_config_json()
    create_users_json()
    create_logs_json()

    env_ready = ensure_env_file()
    add_admin_user_hint()

    venv_dir = create_virtual_environment()
    python_executable = get_venv_python(venv_dir) if venv_dir else None

    deps_ready = False
    if python_executable:
        installed = install_dependencies(python_executable)
        deps_ready = check_dependencies(python_executable) if installed else False
    else:
        deps_ready = check_dependencies(None)

    show_summary(env_ready, deps_ready, venv_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # pragma: no cover - user interruption
        print("\nSetup cancelled by user")
