#!/usr/bin/env python
"""
Setup script for Israeli Basketball Calendar.

This script handles:
1. Installing Python dependencies
2. Installing Playwright browser binaries

Usage:
    python setup.py
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*50}")
    print(f"[*] {description}")
    print(f"{'='*50}")

    try:
        result = subprocess.run(cmd, shell=True, check=True)
        print(f"[+] Success: {description}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[-] Failed: {description}")
        print(f"    Error: {e}")
        return False


def check_venv():
    """Ensure script is running from a .venv virtual environment."""
    # Check if we're in a virtual environment
    venv_path = sys.prefix

    # Check if it's specifically a .venv directory
    if not (venv_path.endswith('.venv') or '/.venv' in venv_path or '\\.venv' in venv_path):
        print("[-] Error: Please run this script from a .venv virtual environment.")
        print("")
        print("    To create and activate a virtual environment:")
        print("      python -m venv .venv")
        print("")
        print("    On Windows:")
        print("      .venv\\Scripts\\activate")
        print("")
        print("    On macOS/Linux:")
        print("      source .venv/bin/activate")
        print("")
        print("    Then run this script again:")
        print("      python setup.py")
        return False
    return True


def main():
    print("=" * 60)
    print("  Israeli Basketball Calendar - Setup")
    print("=" * 60)

    # Check for .venv virtual environment
    if not check_venv():
        return 1

    # Get the directory of this script
    script_dir = Path(__file__).parent

    # Step 1: Install Python dependencies
    if not run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "Installing Python dependencies"
    ):
        print("\n[-] Failed to install Python dependencies")
        return 1

    # Step 2: Install Playwright browsers
    if not run_command(
        f"{sys.executable} -m playwright install chromium",
        "Installing Playwright Chromium browser"
    ):
        print("\n[-] Failed to install Playwright browser")
        print("    You can try manually: playwright install chromium")
        return 1

    # Step 3: Create cache directory
    cache_dir = script_dir / "cache"
    cache_dir.mkdir(exist_ok=True)
    print(f"\n[+] Created cache directory: {cache_dir}")

    print("\n" + "=" * 60)
    print("  Setup Complete!")
    print("=" * 60)
    print("\nTo run the application:")
    print("  uvicorn src.main:app --reload")
    print("\nTo run the scraper manually:")
    print("  python -m src.scraper.nbn23_scraper --no-headless")
    print("\nTo run the background scheduler:")
    print("  python -m src.scraper.scheduler")

    return 0


if __name__ == "__main__":
    sys.exit(main())
