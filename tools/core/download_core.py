#!/usr/bin/env python3
"""
CDISC CORE Engine Installer & Updater.

Downloads the pre-built CORE executable from the official CDISC GitHub releases.
Auto-detects OS and architecture. Tracks installed version for update checks.

Usage:
    python tools/core/download_core.py            # Install (first time) or show status
    python tools/core/download_core.py --update    # Check for updates and re-download if newer
    python tools/core/download_core.py --force     # Force re-download even if up to date

Pipeline integration:
    from tools.core.download_core import ensure_core_engine
    exe_path = ensure_core_engine()  # Returns Path to executable or None
"""

import json
import logging
import os
import platform
import shutil
import stat
import struct
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_REPO = "cdisc-org/cdisc-rules-engine"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES = f"https://github.com/{GITHUB_REPO}/releases"

# Install location: tools/core/bin/<extracted contents>
INSTALL_DIR = Path(__file__).parent / "bin"
VERSION_FILE = INSTALL_DIR / ".version.json"

# Platform → asset name mapping
# Keys: (system, machine_hint)
_ASSET_MAP = {
    ("Windows", "any"):         "core-windows.zip",
    ("Linux", "any"):           "core-ubuntu-latest.zip",
    ("Darwin", "arm64"):        "core-mac-apple-silicon.zip",
    ("Darwin", "x86_64"):       "core-mac-intel.zip",
}


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def _detect_platform() -> Tuple[str, str]:
    """
    Detect current OS and architecture.

    Returns:
        (asset_name, executable_name) for the current platform.

    Raises:
        RuntimeError: If the platform is not supported.
    """
    system = platform.system()  # Windows, Linux, Darwin
    machine = platform.machine().lower()  # x86_64, amd64, arm64, aarch64

    # Normalize architecture
    if machine in ("arm64", "aarch64"):
        arch_hint = "arm64"
    else:
        arch_hint = "x86_64"

    # Determine executable name
    exe_name = "core.exe" if system == "Windows" else "core"

    # Lookup asset
    asset = _ASSET_MAP.get((system, arch_hint)) or _ASSET_MAP.get((system, "any"))
    if not asset:
        raise RuntimeError(
            f"Unsupported platform: {system}/{machine}. "
            f"Download manually from {GITHUB_RELEASES}"
        )

    return asset, exe_name


def _get_exe_path() -> Path:
    """Return the expected path to the CORE executable for this platform."""
    _, exe_name = _detect_platform()
    return INSTALL_DIR / exe_name


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
    """
    Find the download URL for the named asset in a release.

    Returns:
        (download_url, tag_name)
    """
    tag = release.get("tag_name", "unknown")
    for asset in release.get("assets", []):
        if asset["name"] == asset_name:
            return asset["browser_download_url"], tag
    available = [a["name"] for a in release.get("assets", [])]
    raise RuntimeError(
        f"Asset '{asset_name}' not found in release {tag}. "
        f"Available: {available}"
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
    sys.stdout.write(f"\r  [{bar}] {percent}%  ({mb_done:.1f}/{mb_total:.1f} MB)")
    sys.stdout.flush()


def _download_and_extract(url: str, asset_name: str) -> None:
    """Download an archive from URL and extract to INSTALL_DIR."""
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = INSTALL_DIR / asset_name

    print(f"  Downloading: {asset_name}")
    print(f"  URL: {url}")
    try:
        urllib.request.urlretrieve(url, str(tmp_path), _progress_hook)
        print()  # newline after progress bar
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Download failed: {e}\n"
            f"Manual download: {GITHUB_RELEASES}"
        ) from e

    # Extract to a temporary subdirectory, then flatten
    tmp_extract = INSTALL_DIR / "_extract_tmp"
    tmp_extract.mkdir(parents=True, exist_ok=True)

    print(f"  Extracting to: {INSTALL_DIR}")
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

    # Flatten: if extraction produced a single subdirectory, move its
    # contents up to INSTALL_DIR (e.g., bin/_extract_tmp/core/* → bin/*)
    children = list(tmp_extract.iterdir())
    if len(children) == 1 and children[0].is_dir():
        nested = children[0]
        for item in nested.iterdir():
            dest = INSTALL_DIR / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))
        shutil.rmtree(tmp_extract, ignore_errors=True)
    else:
        # No nesting — move everything up
        for item in tmp_extract.iterdir():
            dest = INSTALL_DIR / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))
        shutil.rmtree(tmp_extract, ignore_errors=True)


def _post_install(exe_path: Path) -> None:
    """Platform-specific post-install steps (chmod, xattr)."""
    system = platform.system()

    if system == "Darwin":
        # Remove quarantine attribute on macOS
        os.system(f'xattr -rd com.apple.quarantine "{exe_path.parent}"')
        exe_path.chmod(exe_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print("  Applied macOS quarantine removal + chmod +x")
    elif system == "Linux":
        exe_path.chmod(exe_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print("  Applied chmod +x")


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


def _write_version_info(tag: str, asset_name: str) -> None:
    """Write version metadata after successful install."""
    info = {
        "version": tag.lstrip("v"),
        "tag": tag,
        "asset": asset_name,
        "platform": platform.system(),
        "machine": platform.machine(),
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }
    VERSION_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install_core(force: bool = False) -> Optional[Path]:
    """
    Install CDISC CORE engine executable.

    Downloads the appropriate pre-built executable from the latest GitHub
    release. Skips download if already installed (unless force=True).

    Args:
        force: Re-download even if already installed.

    Returns:
        Path to the executable, or None on failure.
    """
    try:
        asset_name, exe_name = _detect_platform()
    except RuntimeError as e:
        print(f"✗ {e}")
        return None

    exe_path = INSTALL_DIR / exe_name

    # Already installed?
    if exe_path.exists() and not force:
        info = _read_version_info()
        ver = info.get("version", "unknown") if info else "unknown"
        print(f"✓ CORE engine v{ver} already installed at: {exe_path}")
        return exe_path

    # Clean previous install if forcing
    if force and INSTALL_DIR.exists():
        print("  Removing previous installation...")
        shutil.rmtree(INSTALL_DIR, ignore_errors=True)

    # Fetch latest release info
    print("Fetching latest CDISC CORE release...")
    try:
        release = _fetch_latest_release()
        url, tag = _find_asset_url(release, asset_name)
    except RuntimeError as e:
        print(f"✗ {e}")
        return None

    print(f"Installing CDISC CORE Engine {tag} ({asset_name})...")

    # Download and extract
    try:
        _download_and_extract(url, asset_name)
    except RuntimeError as e:
        print(f"✗ {e}")
        return None

    # Post-install
    if not exe_path.exists():
        print(f"✗ Expected executable not found at: {exe_path}")
        print(f"  Contents of {INSTALL_DIR}:")
        for item in sorted(INSTALL_DIR.iterdir()):
            print(f"    {item.name}")
        return None

    _post_install(exe_path)
    _write_version_info(tag, asset_name)

    print(f"✓ CORE engine {tag} installed at: {exe_path}")
    return exe_path


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


def update_core() -> Optional[Path]:
    """
    Check for updates and re-download if a newer version is available.

    Returns:
        Path to the executable, or None on failure.
    """
    print("Checking for CDISC CORE updates...")
    try:
        needs_update, installed, latest = check_for_update()
    except RuntimeError as e:
        print(f"✗ Update check failed: {e}")
        return _get_exe_path() if _get_exe_path().exists() else None

    if not needs_update:
        print(f"✓ CORE engine v{installed} is up to date (latest: v{latest})")
        return _get_exe_path()

    print(f"  Update available: v{installed} → v{latest}")
    return install_core(force=True)


def ensure_core_engine(auto_install: bool = True) -> Optional[Path]:
    """
    Ensure the CORE engine executable is available.

    Called by the pipeline at runtime. If the executable is not found and
    auto_install is True, downloads it automatically.

    Args:
        auto_install: If True, download on first run. If False, return None.

    Returns:
        Path to the executable, or None if unavailable.
    """
    try:
        exe_path = _get_exe_path()
    except RuntimeError:
        logger.warning("CDISC CORE: unsupported platform")
        return None

    if exe_path.exists():
        return exe_path

    if not auto_install:
        return None

    logger.info("CDISC CORE engine not found — downloading automatically...")
    print("\n--- CDISC CORE Engine Auto-Install ---")
    result = install_core()
    if result:
        print("--- Auto-Install Complete ---\n")
    else:
        print("--- Auto-Install Failed (pipeline will skip CORE validation) ---\n")
    return result


def get_core_engine_path() -> Optional[Path]:
    """
    Return the path to the CORE executable without triggering install.
    Returns None if not installed.
    """
    try:
        exe_path = _get_exe_path()
        return exe_path if exe_path.exists() else None
    except RuntimeError:
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="CDISC CORE Engine Installer",
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
    args = parser.parse_args()

    if args.status:
        info = _read_version_info()
        if info:
            print(f"CDISC CORE Engine Status:")
            print(f"  Version:    v{info.get('version', '?')}")
            print(f"  Tag:        {info.get('tag', '?')}")
            print(f"  Asset:      {info.get('asset', '?')}")
            print(f"  Platform:   {info.get('platform', '?')}/{info.get('machine', '?')}")
            print(f"  Installed:  {info.get('installed_at', '?')}")
            try:
                exe = _get_exe_path()
                print(f"  Executable: {exe} ({'exists' if exe.exists() else 'MISSING'})")
            except RuntimeError:
                print(f"  Executable: unknown platform")
        else:
            print("CDISC CORE Engine: not installed")
            print(f"  Run: python {__file__}")
        return

    if args.update:
        result = update_core()
    else:
        result = install_core(force=args.force)

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
