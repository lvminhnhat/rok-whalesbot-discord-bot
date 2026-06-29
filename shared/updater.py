"""Self-update via GitHub Releases.

Flow on startup:
  1. Read local VERSION (bundled into the PyInstaller exe).
  2. Hit the GitHub Releases API for the latest tag.
  3. If newer, ask the user [y/N]. Default N — only an explicit `y` updates.
  4. On y: download the release zip, extract to a staging dir, spawn
     updater.bat, exit so the bat can swap files in and relaunch the exe.

The release zip is expected to contain files at the archive root
(WhalesBot.exe, etc). `data/` and `.env` are skipped during extraction
so user state is never overwritten.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from typing import Optional, Tuple

GITHUB_REPO = "Minnyat/rok-whalesbot-discord-bot"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
HTTP_TIMEOUT = 5
DOWNLOAD_TIMEOUT = 120
USER_AGENT = "WhalesBot-Updater"

PRESERVE_PATHS = {"data", ".env"}


def _install_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bundled_resource(name: str) -> str:
    base = getattr(sys, "_MEIPASS", None) or _install_dir()
    return os.path.join(base, name)


def get_current_version() -> str:
    try:
        with open(_bundled_resource("VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def _parse_version(v: str) -> Tuple[int, ...]:
    v = v.strip().lstrip("vV")
    return tuple(int(p) for p in v.split(".") if p.isdigit())


def _is_newer(current: str, latest: str) -> bool:
    try:
        return _parse_version(latest) > _parse_version(current)
    except ValueError:
        return False


def _fetch_latest_release() -> Optional[dict]:
    req = urllib.request.Request(RELEASES_API, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _pick_zip_asset(release: dict) -> Optional[str]:
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if name.lower().endswith(".zip"):
            return asset.get("browser_download_url")
    return release.get("zipball_url")


def _download(url: str, dest: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _extract(zip_path: str, staging_dir: str) -> bool:
    """Extract zip into staging_dir, skipping preserved paths.

    If the zip has a single top-level folder (common for source archives),
    descend into it so the staging dir matches the install dir layout.
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            top = {n.split("/", 1)[0] for n in names if n}
            strip_prefix = ""
            if len(top) == 1:
                only = next(iter(top))
                if any(n.startswith(only + "/") for n in names):
                    strip_prefix = only + "/"

            for member in zf.infolist():
                name = member.filename
                if strip_prefix and name.startswith(strip_prefix):
                    name = name[len(strip_prefix):]
                if not name or name.endswith("/"):
                    continue
                first = name.split("/", 1)[0].split("\\", 1)[0]
                if first in PRESERVE_PATHS or name in PRESERVE_PATHS:
                    continue
                target = os.path.join(staging_dir, name.replace("/", os.sep))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        return True
    except (zipfile.BadZipFile, OSError):
        return False


def _prompt_yes(question: str) -> bool:
    try:
        answer = input(question).strip().lower()
    except (EOFError, OSError):
        return False
    return answer == "y"


def _spawn_updater_and_exit(staging_dir: str) -> None:
    install_dir = _install_dir()
    bat = os.path.join(install_dir, "updater.bat")
    if not os.path.exists(bat):
        # Fallback: ship a copy in the bundle and stage it next to the exe.
        bundled_bat = _bundled_resource("updater.bat")
        if os.path.exists(bundled_bat):
            shutil.copy2(bundled_bat, bat)
        else:
            print("[updater] updater.bat missing — cannot apply update.")
            return

    if getattr(sys, "frozen", False):
        exe_name = os.path.basename(sys.executable)
    else:
        exe_name = "WhalesBot.exe"

    # Run the updater in its OWN new console (survives this process exiting).
    # We avoid the previous `cmd /c start "" bat ...` form: that nested `start`
    # ran the bat with no console, where cmd's `start`/relaunch fails with
    # "Not enough memory resources are available to process this command".
    CREATE_NEW_CONSOLE = 0x00000010
    subprocess.Popen(
        ["cmd.exe", "/c", bat, staging_dir, install_dir, exe_name],
        creationflags=CREATE_NEW_CONSOLE,
        close_fds=True,
    )
    print("[updater] Update staged. Closing so the updater can swap files in...")
    sys.exit(0)


def check_and_prompt() -> None:
    """Entry point: call once at startup, before anything else.

    Honors AUTO_UPDATE env var: `prompt` (default) checks and asks the
    user; `off` skips the check entirely.
    """
    mode = os.getenv("AUTO_UPDATE", "prompt").strip().lower()
    if mode == "off":
        return

    current = get_current_version()
    release = _fetch_latest_release()
    if not release:
        return

    latest = (release.get("tag_name") or "").strip()
    if not latest or not _is_newer(current, latest):
        return

    notes = (release.get("body") or "").strip().splitlines()
    first_line = notes[0] if notes else "(no release notes)"

    print()
    print("=" * 60)
    print(f"Update available: v{current.lstrip('vV')} -> {latest}")
    print(f"Notes: {first_line}")
    print("=" * 60)
    if not _prompt_yes("Update now? [y/N]: "):
        print("[updater] Skipped. Continuing startup...")
        return

    asset_url = _pick_zip_asset(release)
    if not asset_url:
        print("[updater] No downloadable zip in release. Skipping.")
        return

    print(f"[updater] Downloading {latest}...")
    tmp_dir = tempfile.mkdtemp(prefix="whalesbot_update_")
    zip_path = os.path.join(tmp_dir, "release.zip")
    if not _download(asset_url, zip_path):
        print("[updater] Download failed. Skipping.")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return

    staging = os.path.join(tmp_dir, "staging")
    os.makedirs(staging, exist_ok=True)
    print("[updater] Extracting...")
    if not _extract(zip_path, staging):
        print("[updater] Extraction failed. Skipping.")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return

    try:
        os.remove(zip_path)
    except OSError:
        pass

    _spawn_updater_and_exit(staging)
