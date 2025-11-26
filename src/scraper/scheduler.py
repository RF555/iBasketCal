"""
Background Scheduler for NBN23 Data Refresh.

Runs the scraper on a schedule to keep cached data fresh.
"""

import schedule
import time
from datetime import datetime
from .nbn23_scraper import NBN23Scraper


def refresh_data():
    """Background job to refresh data."""
    print(f"[{datetime.now()}] Starting scheduled data refresh...")
    try:
        scraper = NBN23Scraper(headless=True)
        data = scraper.scrape()

        # Log summary
        print(f"[{datetime.now()}] Data refresh complete:")
        print(f"  - Seasons: {len(data.get('seasons', []))}")
        print(f"  - Competition sets: {len(data.get('competitions', {}))}")
        print(f"  - Calendars: {len(data.get('calendars', {}))}")
        print(f"  - Standings: {len(data.get('standings', {}))}")

    except Exception as e:
        print(f"[{datetime.now()}] Error during data refresh: {e}")


def main():
    """Main entry point for scheduler."""
    print("=" * 50)
    print("Israeli Basketball Calendar - Background Scraper")
    print("=" * 50)

    # Run immediately on start
    print("\n[*] Running initial data refresh...")
    refresh_data()

    # Schedule every 30 minutes
    schedule.every(30).minutes.do(refresh_data)
    print("\n[*] Scheduled to run every 30 minutes")
    print("[*] Press Ctrl+C to stop\n")

    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    main()
