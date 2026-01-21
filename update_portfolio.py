import argparse
import os
import pandas as pd
from datetime import datetime
import update_prices
import analyze_portfolio

def main():
    parser = argparse.ArgumentParser(description="Update portfolio prices and analyze value.")
    parser.add_argument('--incremental', action='store_true', help="Resume analysis from last tracked date.")
    args = parser.parse_args()

    print("--- Starting Portfolio Update ---")

    # 1. Sync Prices
    # This runs the batch update logic. It automatically skips files that already exist,
    # so it is efficient by default.
    try:
        print("\nStep 1: Syncing Market Prices...")
        update_prices.main() 
    except Exception as e:
        print(f"Error updating prices: {e}")

    # 2. Analyze Portfolio
    print("\nStep 2: Calculating Portfolio Value...")
    resume_date = None
    
    if args.incremental and os.path.exists("daily_tracker.csv"):
        try:
            df = pd.read_csv("daily_tracker.csv")
            if not df.empty:
                # Get the last date recorded
                last_record_date = pd.to_datetime(df.iloc[-1]['Date']).strftime('%Y-%m-%d')
                print(f"Found existing data. Resuming analysis from {last_record_date}...")
                resume_date = last_record_date
        except Exception as e:
            print(f"could not read daily_tracker.csv for incremental mode: {e}")

    analyze_portfolio.run_analysis(resume_date)
    print("\n--- Update Complete ---")

if __name__ == "__main__":
    main()
