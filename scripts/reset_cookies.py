"""Reset browser cookies/session for a platform.

Usage:
    python scripts/reset_cookies.py linkedin
    python scripts/reset_cookies.py indeed
    python scripts/reset_cookies.py all
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_agent.config import Settings


def reset_cookies(platform: str) -> None:
    settings = Settings.from_env()
    base_dir = settings.browser_data_dir

    if platform == "all":
        platforms = ["linkedin", "indeed"]
    else:
        platforms = [platform]

    for p in platforms:
        data_dir = base_dir / p
        if data_dir.exists():
            shutil.rmtree(data_dir)
            print(f"Cleared browser data for: {p}")
        else:
            print(f"No browser data found for: {p}")

    print("\nYou will need to log in again using:")
    for p in platforms:
        print(f"  python scripts/manual_login.py {p}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/reset_cookies.py <platform|all>")
        print("Platforms: linkedin, indeed, all")
        sys.exit(1)

    platform = sys.argv[1].lower()
    if platform not in ("linkedin", "indeed", "all"):
        print(f"Unknown platform: {platform}")
        sys.exit(1)

    reset_cookies(platform)


if __name__ == "__main__":
    main()
