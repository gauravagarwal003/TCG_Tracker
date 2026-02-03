#!/usr/bin/env python3
"""
Backfill helper for Pokemon Tracker.

Usage:
    python backfill_dates.py 2024-12-10 2024-12-15    # Backfill date range
    python backfill_dates.py --missing                 # Find and fill missing dates

This script runs update_single_day.py for each date in a range.
"""

import sys
import subprocess
from datetime import datetime, timedelta
import pandas as pd
import os


def backfill_range(start_date: str, end_date: str):
    """Run single-day update for each date in range."""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    current = start
    total = (end - start).days + 1
    success_count = 0
    
    print(f"Backfilling {total} days from {start_date} to {end_date}")
    print("=" * 50)
    
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        print(f"\n[{success_count + 1}/{total}] Processing {date_str}...")
        
        result = subprocess.run(
            [sys.executable, "update_single_day.py", date_str],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            success_count += 1
        else:
            print(f"  Error: {result.stderr}")
        
        current += timedelta(days=1)
    
    print("\n" + "=" * 50)
    print(f"Backfill complete: {success_count}/{total} days successful")


def find_missing_dates():
    """Find gaps in daily_tracker.csv and backfill them."""
    if not os.path.exists("daily_tracker.csv"):
        print("No daily_tracker.csv found. Nothing to check for gaps.")
        return []
    
    df = pd.read_csv("daily_tracker.csv")
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    
    if len(df) < 2:
        print("Not enough data to detect gaps.")
        return []
    
    # Find all dates in range
    start_date = df['Date'].min()
    end_date = df['Date'].max()
    all_dates = pd.date_range(start_date, end_date, freq='D')
    
    # Find missing dates
    existing_dates = set(df['Date'].dt.strftime('%Y-%m-%d'))
    missing = [d.strftime('%Y-%m-%d') for d in all_dates if d.strftime('%Y-%m-%d') not in existing_dates]
    
    return missing


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python backfill_dates.py START_DATE END_DATE  # Backfill range")
        print("  python backfill_dates.py --missing            # Find and fill gaps")
        print()
        print("Examples:")
        print("  python backfill_dates.py 2024-12-10 2024-12-15")
        print("  python backfill_dates.py --missing")
        sys.exit(1)
    
    if sys.argv[1] == '--missing':
        missing = find_missing_dates()
        if not missing:
            print("No missing dates found!")
            return
        
        print(f"Found {len(missing)} missing dates:")
        for d in missing:
            print(f"  - {d}")
        
        response = input("\nBackfill these dates? [y/N] ").strip().lower()
        if response == 'y':
            for date_str in missing:
                print(f"\nProcessing {date_str}...")
                subprocess.run([sys.executable, "update_single_day.py", date_str])
        else:
            print("Aborted.")
    
    elif len(sys.argv) >= 3:
        start_date = sys.argv[1]
        end_date = sys.argv[2]
        
        # Validate dates
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            print("Error: Dates must be in YYYY-MM-DD format")
            sys.exit(1)
        
        backfill_range(start_date, end_date)
    
    else:
        print("Error: Need either --missing or START_DATE END_DATE")
        sys.exit(1)


if __name__ == "__main__":
    main()
