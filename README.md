# Pokemon Investment Tracker

A highly optimized portfolio tracker for Pokemon TCG investments. Tracks inventory, historical value, and daily performance with automated updates.

## 🚀 Key Features
- **Smart Tracking:** Only tracks prices for days you actually owned the item (prevents file bloat).
- **Incremental Updates:** Updates "Today" in seconds without recalculating the entire history.
- **GitHub Automation:** Runs daily in the cloud, free of charge.
- **Interactive Graphs:** Visualizes Portfolio Value & Cost Basis over time.

## 🛠 Setup

1. **Install Python 3.10+**
2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Data:**
   - Ensure `transactions.csv` contains your purchase history.
   - `mappings.json` handles product ID lookups.

## 📈 How to Use

### 1. Adding Transactions
You can edit `transactions.csv` directly or use the Web App.

*   **Logic:** The system treats `transactions.csv` as the "Source of Truth".
*   **Automation:** When you commit and push changes to `transactions.csv` to GitHub, the Action will automatically triggering a rebuild to fetch any missing history for new items.

### 2. Running Locally (Manual)
**Standard Daily Update (Fast):**
RESUMES from the last date in `daily_tracker.csv`.
```bash
python daily_run.py --incremental
```

**Full Rebuild (Slow):**
Wipes history and recalculates everything. Use if data looks corrupted.
```bash
python daily_run.py
```

### 3. Web Interface
View graphs and edit transactions via the UI:
```bash
python app.py
```
Open `http://127.0.0.1:5000` in your browser.

## 🤖 GitHub Actions Automation
The project is configured to run automatically via GitHub Actions (`.github/workflows/daily.yml`):
1.  **Daily Trigger:** Runs at midnight UTC to append the latest day's value.
2.  **Push Trigger:** Runs whenever you push changes to `transactions.csv`.

**Note on Storage:**
The potentially huge `historical_prices/` folder is **cached** in GitHub Actions and ignored by Git. This keeps your repository size small while retaining all necessary data for calculations.

## 📂 Project Structure
- `daily_run.py`: Mains orchestration script.
- `transactions.csv`: Your portfolio ledger.
- `daily_tracker.csv`: Generated daily history of your portfolio value.
- `current_holdings.csv`: Snapshot of current inventory.
- `analyze_portfolio.py`: Logic for calculating value and generating graphs.
- `update_prices.py`: Logic for fetching daily price dumps.
