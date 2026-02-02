#!/usr/bin/env python3
"""
Download CDISC CORE Engine from official GitHub releases.
Run this script to set up the CORE engine for conformance validation.
"""

import os
import sys
import zipfile
import urllib.request
from pathlib import Path

# CDISC CORE Engine release URL
CORE_VERSION = "0.14.1"
CORE_RELEASE_URL = f"https://github.com/cdisc-org/cdisc-rules-engine/releases/download/v{CORE_VERSION}/core-windows.zip"

def download_core():
    """Download and extract CORE engine."""
    script_dir = Path(__file__).parent
    zip_path = script_dir / "core-windows.zip"
    extract_dir = script_dir / "core"
    
    # Check if already extracted
    exe_path = extract_dir / "core.exe"
    if exe_path.exists():
        print(f"✓ CORE engine already installed at: {exe_path}")
        return str(exe_path)
    
    # Download if zip doesn't exist
    if not zip_path.exists():
        print(f"Downloading CDISC CORE Engine v{CORE_VERSION}...")
        print(f"URL: {CORE_RELEASE_URL}")
        
        try:
            urllib.request.urlretrieve(CORE_RELEASE_URL, zip_path, _progress_hook)
            print("\n✓ Download complete")
        except Exception as e:
            print(f"\n✗ Download failed: {e}")
            print("\nManual download:")
            print(f"  1. Go to: https://github.com/cdisc-org/cdisc-rules-engine/releases")
            print(f"  2. Download core-windows.zip")
            print(f"  3. Place it in: {script_dir}")
            sys.exit(1)
    
    # Extract
    print(f"Extracting to: {extract_dir}")
    extract_dir.mkdir(exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_dir)
    
    print(f"✓ CORE engine installed at: {exe_path}")
    return str(exe_path)


def _progress_hook(block_num, block_size, total_size):
    """Show download progress."""
    downloaded = block_num * block_size
    percent = min(100, downloaded * 100 // total_size)
    bar = '=' * (percent // 2) + '-' * (50 - percent // 2)
    sys.stdout.write(f'\r[{bar}] {percent}%')
    sys.stdout.flush()


if __name__ == "__main__":
    download_core()
