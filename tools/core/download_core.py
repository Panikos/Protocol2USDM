#!/usr/bin/env python3
"""
CDISC CORE Engine Installer & Updater.

Downloads ALL platform executables from the official CDISC GitHub releases
into platform-specific subdirectories. Auto-detects the correct one at
runtime. Use --core to override auto-detection.

Directory layout after install:
    tools/core/bin/
        windows/core.exe   (+ DLLs, resources)
        linux/core          (+ shared libs, resources)
        mac/core            (+ dylibs, resources)
        .version.json       (tracks installed version)

Usage:
    python tools/core/download_core.py              # Install all platforms
    python tools/core/download_core.py --update     # Check for newer version
    python tools/core/download_core.py --force      # Force re-download
    python tools/core/download_core.py --status     # Show install info

Pipeline integration:
    from tools.core.download_core import ensure_core_engine
    exe_path = ensure_core_engine()                 # Auto-detect OS
    exe_path = ensure_core_engine(core="windows")   # Force platform
"""

import json
import logging
import os
import platform
import shutil
import stat
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_REPO = "cdisc-org/cdisc-rules-engine"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES = f"https://github.com/{GITHUB_REPO}/releases"

# Root install location
INSTALL_DIR = Path(__file__).parent / "bin"
VERSION_FILE = INSTALL_DIR / ".version.json"

# Platform definitions: label → (asset_name, executable_name)
PLATFORMS: Dict[str, Tuple[str, str]] = {
    "windows": ("core-windows.zip", "core.exe"),
    "linux":   ("core-ubuntu-latest.zip", "core"),
    "mac":     ("core-mac-apple-silicon.zip", "core"),
}

# Valid --core flag values
VALID_CORE_FLAGS = list(PLATFORMS.keys())


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def detect_platform() -> str:
    """
    Auto-detect the current platform label.

    Returns:
        One of 'windows', 'linux', 'mac'.

    Raises:
        RuntimeError if platform is unsupported.
    """
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Linux":
        return "linux"
    elif system == "Darwin":
        return "mac"
    else:
        raise RuntimeError(
            f"Unsupported OS: {system}. Use --core windows|linux|mac to override."
        )


def get_exe_path(core: Optional[str] = None) -> Path:
    """
    Return the path to the CORE executable for the given (or detected) platform.

    Args:
        core: Platform override ('windows', 'linux', 'mac'). Auto-detects if None.
    """
    plat = core or detect_platform()
    _, exe_name = PLATFORMS[plat]
    return INSTALL_DIR / plat / exe_name


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

def _fetch_latest_release() -> dict:
    """Query GitHub API for the latest release metadata."""
    req = urllib.request.Request(
        GITHUB_API_LATEST,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Protocol2USDM"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub API error: {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error (check internet connection): {e.reason}") from e


def _find_asset_url(release: dict, asset_name: str) -> Tuple[str, str]:
    """Find the download URL for an asset. Returns (url, tag)."""
    tag = release.get("tag_name", "unknown")
    for asset in release.get("assets", []):
        if asset["name"] == asset_name:
            return asset["browser_download_url"], tag
    available = [a["name"] for a in release.get("assets", [])]
    raise RuntimeError(
        f"Asset '{asset_name}' not found in release {tag}. Available: {available}"
    )


# ---------------------------------------------------------------------------
# Download & extract
# ---------------------------------------------------------------------------

def _progress_hook(block_num: int, block_size: int, total_size: int) -> None:
    """Show download progress bar."""
    if total_size <= 0:
        return
    downloaded = block_num * block_size
    percent = min(100, downloaded * 100 // total_size)
    bar = "=" * (percent // 2) + "-" * (50 - percent // 2)
    mb_done = downloaded / (1024 * 1024)
    mb_total = total_size / (1024 * 1024)
    sys.stdout.write(f"\r    [{bar}] {percent}%  ({mb_done:.1f}/{mb_total:.1f} MB)")
    sys.stdout.flush()


def _download_and_extract(url: str, asset_name: str, target_dir: Path) -> None:
    """Download an archive and extract (flattened) into target_dir."""
    target_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = target_dir / asset_name

    print(f"    Downloading: {asset_name}")
    try:
        urllib.request.urlretrieve(url, str(tmp_path), _progress_hook)
        print()  # newline after progress bar
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Download failed: {e}") from e

    # Extract to temp, then flatten nested directory if present
    tmp_extract = target_dir / "_extract_tmp"
    tmp_extract.mkdir(parents=True, exist_ok=True)

    try:
        if asset_name.endswith(".tar.gz"):
            with tarfile.open(str(tmp_path), "r:gz") as tf:
                tf.extractall(str(tmp_extract))
        elif asset_name.endswith(".zip"):
            with zipfile.ZipFile(str(tmp_path), "r") as zf:
                zf.extractall(str(tmp_extract))
        else:
            raise RuntimeError(f"Unknown archive format: {asset_name}")
    finally:
        tmp_path.unlink(missing_ok=True)

    # Flatten: if extraction produced a single subdirectory, move contents up
    children = list(tmp_extract.iterdir())
    source = children[0] if len(children) == 1 and children[0].is_dir() else tmp_extract
    for item in source.iterdir():
        dest = target_dir / item.name
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        shutil.move(str(item), str(dest))
    shutil.rmtree(tmp_extract, ignore_errors=True)


def _post_install_platform(plat: str, exe_path: Path) -> None:
    """Platform-specific post-install steps."""
    if plat == "mac":
        os.system(f'xattr -rd com.apple.quarantine "{exe_path.parent}" 2>/dev/null')
        exe_path.chmod(exe_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    elif plat == "linux":
        exe_path.chmod(exe_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# Version tracking
# ---------------------------------------------------------------------------

def _read_version_info() -> Optional[dict]:
    """Read installed version metadata."""
    if VERSION_FILE.exists():
        try:
            return json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _write_version_info(tag: str, platforms_installed: List[str]) -> None:
    """Write version metadata after successful install."""
    info = {
        "version": tag.lstrip("v"),
        "tag": tag,
        "platforms": platforms_installed,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "host_os": platform.system(),
        "host_machine": platform.machine(),
    }
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install_core(force: bool = False) -> bool:
    """
    Download ALL platform executables from the latest GitHub release.

    Creates: tools/core/bin/{windows,linux,mac}/ with flattened contents.

    Args:
        force: Re-download even if already installed.

    Returns:
        True if all platforms installed successfully.
    """
    # Already installed?
    info = _read_version_info()
    if info and not force:
        installed_plats = info.get("platforms", [])
        all_present = all(
            (INSTALL_DIR / plat / PLATFORMS[plat][1]).exists()
            for plat in PLATFORMS
        )
        if all_present:
            ver = info.get("version", "unknown")
            print(f"✓ CORE engine v{ver} already installed for: {', '.join(installed_plats)}")
            return True

    # Clean previous install if forcing
    if force and INSTALL_DIR.exists():
        print("  Removing previous installation...")
        shutil.rmtree(INSTALL_DIR, ignore_errors=True)

    # Fetch latest release
    print("Fetching latest CDISC CORE release...")
    try:
        release = _fetch_latest_release()
    except RuntimeError as e:
        print(f"✗ {e}")
        return False

    tag = release.get("tag_name", "unknown")
    print(f"Installing CDISC CORE Engine {tag} (all platforms)...\n")

    installed_plats = []
    for plat, (asset_name, exe_name) in PLATFORMS.items():
        plat_dir = INSTALL_DIR / plat
        exe_path = plat_dir / exe_name

        print(f"  [{plat}]")
        try:
            url, _ = _find_asset_url(release, asset_name)
            _download_and_extract(url, asset_name, plat_dir)

            if not exe_path.exists():
                print(f"    ✗ Executable not found at: {exe_path}")
                continue

            _post_install_platform(plat, exe_path)
            installed_plats.append(plat)
            print(f"    ✓ {plat} ready\n")

        except RuntimeError as e:
            print(f"    ✗ {e}\n")
            continue

    if installed_plats:
        _write_version_info(tag, installed_plats)
        print(f"✓ CORE engine {tag} installed: {', '.join(installed_plats)}")
        return True
    else:
        print("✗ No platforms installed successfully")
        return False


def check_for_update() -> Tuple[bool, str, str]:
    """
    Check if a newer version is available.

    Returns:
        (update_available, installed_version, latest_version)
    """
    info = _read_version_info()
    installed = info.get("version", "0.0.0") if info else "0.0.0"

    release = _fetch_latest_release()
    latest = release.get("tag_name", "v0.0.0").lstrip("v")

    return (latest != installed), installed, latest


def update_core() -> bool:
    """Check for updates and re-download if a newer version is available."""
    print("Checking for CDISC CORE updates...")
    try:
        needs_update, installed, latest = check_for_update()
    except RuntimeError as e:
        print(f"✗ Update check failed: {e}")
        return False

    if not needs_update:
        print(f"✓ CORE engine v{installed} is up to date (latest: v{latest})")
        return True

    print(f"  Update available: v{installed} → v{latest}")
    return install_core(force=True)


def ensure_core_engine(
    core: Optional[str] = None,
    auto_install: bool = True,
) -> Optional[Path]:
    """
    Ensure the CORE engine executable is available.

    Called by the pipeline at runtime. Auto-detects platform unless
    overridden via ``core`` parameter.

    Args:
        core: Platform override ('windows', 'linux', 'mac'). Auto-detects if None.
        auto_install: If True, download all platforms on first run.

    Returns:
        Path to the executable, or None if unavailable.
    """
    # Resolve platform
    if core:
        if core not in PLATFORMS:
            logger.error(f"Invalid --core value: {core}. Use: {VALID_CORE_FLAGS}")
            return None
        plat = core
    else:
        try:
            plat = detect_platform()
        except RuntimeError:
            logger.warning("CDISC CORE: unsupported platform — use --core to specify")
            return None

    exe_path = get_exe_path(plat)

    if exe_path.exists():
        return exe_path

    if not auto_install:
        return None

    logger.info("CDISC CORE engine not found — downloading all platforms...")
    print("\n--- CDISC CORE Engine Auto-Install ---")
    success = install_core()
    if success:
        print("--- Auto-Install Complete ---\n")
        # Re-check — the exe should now exist
        if exe_path.exists():
            return exe_path
    else:
        print("--- Auto-Install Failed (pipeline will skip CORE validation) ---\n")
    return None


def get_core_engine_path(core: Optional[str] = None) -> Optional[Path]:
    """
    Return the path to the CORE executable without triggering install.

    Args:
        core: Platform override. Auto-detects if None.

    Returns:
        Path if installed, None otherwise.
    """
    try:
        exe_path = get_exe_path(core)
        return exe_path if exe_path.exists() else None
    except (RuntimeError, KeyError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="CDISC CORE Engine Installer — downloads all platform executables",
        epilog=f"Downloads from: {GITHUB_RELEASES}",
    )
    parser.add_argument(
        "--update", action="store_true",
        help="Check for updates and re-download if a newer version is available",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-download even if already installed",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show installation status and exit",
    )
    parser.add_argument(
        "--core", choices=VALID_CORE_FLAGS,
        help="Override platform auto-detection (for --status only)",
    )
    args = parser.parse_args()

    if args.status:
        info = _read_version_info()
        if info:
            print("CDISC CORE Engine Status:")
            print(f"  Version:    v{info.get('version', '?')}")
            print(f"  Tag:        {info.get('tag', '?')}")
            print(f"  Platforms:  {', '.join(info.get('platforms', []))}")
            print(f"  Host:       {info.get('host_os', '?')}/{info.get('host_machine', '?')}")
            print(f"  Installed:  {info.get('installed_at', '?')}")
            try:
                detected = detect_platform()
                print(f"  Detected:   {detected}")
            except RuntimeError:
                print("  Detected:   unknown")
            print()
            for plat, (_, exe_name) in PLATFORMS.items():
                exe = INSTALL_DIR / plat / exe_name
                status = "✓ exists" if exe.exists() else "✗ missing"
                active = " (active)" if plat == (args.core or detect_platform()) else ""
                print(f"  {plat:10s}  {status}{active}")
        else:
            print("CDISC CORE Engine: not installed")
            print(f"  Run: python {__file__}")
        return

    if args.update:
        success = update_core()
    else:
        success = install_core(force=args.force)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
