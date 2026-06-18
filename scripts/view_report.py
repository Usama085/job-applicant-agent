"""View today's application report from the database.

Usage:
    python scripts/view_report.py              # Today's report
    python scripts/view_report.py --all        # All-time stats
    python scripts/view_report.py --date 2026-02-17  # Specific date
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_agent.config import Settings


def print_report(db_path: Path, date_filter: str | None = None, show_all: bool = False) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    if show_all:
        query = """
            SELECT j.title, j.company, j.location, j.platform,
                   a.applied_at, j.job_url, a.status
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            ORDER BY a.applied_at DESC
        """
        params = ()
    elif date_filter:
        query = """
            SELECT j.title, j.company, j.location, j.platform,
                   a.applied_at, j.job_url, a.status
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE date(a.applied_at) = ?
            ORDER BY a.applied_at DESC
        """
        params = (date_filter,)
    else:
        query = """
            SELECT j.title, j.company, j.location, j.platform,
                   a.applied_at, j.job_url, a.status
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE date(a.applied_at) = date('now')
            ORDER BY a.applied_at DESC
        """
        params = ()

    rows = conn.execute(query, params).fetchall()

    if not rows:
        print("No applications found.")
        conn.close()
        return

    # Print stats
    statuses = {}
    for row in rows:
        s = row["status"]
        statuses[s] = statuses.get(s, 0) + 1

    print(f"\n{'='*70}")
    print(f"  Application Report | Total: {len(rows)}")
    print(f"{'='*70}")

    for status, count in sorted(statuses.items()):
        print(f"  {status}: {count}")

    print(f"\n{'-'*70}")
    print(f"  {'Title':<25} {'Company':<20} {'Platform':<10} {'Status':<15}")
    print(f"{'-'*70}")

    for row in rows:
        title = (row["title"] or "N/A")[:24]
        company = (row["company"] or "N/A")[:19]
        platform = (row["platform"] or "N/A")[:9]
        status = (row["status"] or "N/A")[:14]
        print(f"  {title:<25} {company:<20} {platform:<10} {status:<15}")

    print(f"{'='*70}\n")
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="View job application reports")
    parser.add_argument("--all", action="store_true", help="Show all-time stats")
    parser.add_argument("--date", type=str, help="Show stats for a specific date (YYYY-MM-DD)")
    args = parser.parse_args()

    settings = Settings.from_env()
    db_path = settings.database_path

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Run the agent at least once to create the database.")
        sys.exit(1)

    print_report(db_path, date_filter=args.date, show_all=args.all)


if __name__ == "__main__":
    main()
