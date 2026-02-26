# TCG Investment Tracker

Track the total market value of your TCG collection and your net cost basis over time.

## Features

- **Transaction Types:** BUY, SELL, OPEN (sealed product), TRADE
- **Daily Price Tracking:** Automated via GitHub Actions at 3 PM PST
- **Derived Daily Summary:** Total portfolio value and cost basis for every day since inception
- **Carry-Forward Pricing:** Missing price days use the last known price
- **Inventory Validation:** Prevents negative quantities at any point in time
- **Backdated Transactions:** Full timeline rebuild on every change
- **GitHub Pages Dashboard:** Password-protected site with interactive Plotly charts
- **Flask Local UI:** Add/edit/delete transactions with product search

## Requirements

- Python 3.10+ (macOS: use the system `python3` or Homebrew/pyenv)
- 7zip (for price archive extraction when using `daily_run.py`)

## Local setup & run

1. Create and activate a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies into the venv:

```bash
.venv/bin/python3 -m pip install --upgrade pip
.venv/bin/python3 -m pip install -r requirements.txt
```

3. Start the Flask app:

```bash
.venv/bin/python3 app.py
```

Or use the convenience script (it will create/activate `.venv` and install deps if missing):

```bash
bash run_app.sh
```

Open the site at: http://127.0.0.1:5001

To change the port or other env vars before starting:

```bash
export PORT=5001
export SECRET_KEY="your-secret"
.venv/bin/python3 app.py
```

If you see "ModuleNotFoundError: No module named 'flask'", ensure you installed the requirements into the venv using the commands above.

## Persisting encoding/"mojibake" fixes

This project now includes a small automatic fixer in `engine.py` that attempts to correct common double-encoded UTF-8 sequences when loading JSON. To persist corrected values back into `transactions.json` (so files are clean on disk), run the following while the venv is activated:

```bash
.venv/bin/python3 - <<'PY'
from engine import load_transactions, TRANSACTIONS_FILE
import json
txns = load_transactions()
with open(TRANSACTIONS_FILE, 'w', encoding='utf-8') as f:
    json.dump(txns, f, indent=2, ensure_ascii=False)
print('Wrote', len(txns), 'transactions to', TRANSACTIONS_FILE)
PY
```

## Local GitHub Pages Preview

To preview the GitHub Pages static site locally (same static HTML + docs/data files), run:

```bash
./run_docs.sh
```

Then open http://127.0.0.1:8000/index.html

Notes:
- Serving over http://127.0.0.1 is required (opening files via file:// will break auth/crypto in the browser).
- The script regenerates `docs/data/` and the static HTML before starting the server.

## Editing data: static pages vs local server

- The static `docs/` pages include a client-side GitHub helper that can commit changes directly to the repository. To save new products or transactions from the static pages the browser must provide a GitHub Personal Access Token (PAT) with repository write permissions.
- If you open the static `add-transaction.html` or `docs/add-transaction.html` and see an alert like "GitHub token is required to save new products on GitHub Pages", that's because the static frontend could not obtain a token (or the helper files `auth.js` / `github-api.js` are not present).
- Recommended for local development: run the Flask app (see "Local setup & run") and use the dynamic UI — it POSTs to the local server and does not require a GitHub token.

If you really want to enable editing directly from the static site locally, you must provide a client-side implementation that exposes `githubAPI.authenticate()` and related methods. A minimal approach is:

1. Create `docs/auth.js` that prompts for a PAT and stores it in `localStorage` (only for local testing).
2. Create `docs/github-api.js` that uses the token to call GitHub's REST API to `GET`/`PUT` files and create commits (must implement `isAuthenticated()`, `authenticate()`, `getFile()` and `updateFilesAtomic()`).

Warning: storing a PAT in the browser is insecure. Only use this flow for short-lived local testing and never expose your token on public machines.

## Project structure (high level)

- `engine.py` — Core engine: inventory timeline, daily summary derivation, price loading
- `transaction_manager.py` — CRUD for transactions with validation
- `price_fetcher.py` — Fetches prices from tcgcsv archives
- `app.py` — Flask web app for local development
- `daily_run.py` — Daily job: fetch prices, derive summary, generate static data
- `config.json` — Start date, timezone, GitHub config
- `transactions.json` — All transactions (source of truth)
- `mappings.json` — Product metadata (name, URL, image)
- `prices/` — Per-product price history (`{cat}/{group}/{product}.json`)
- `daily_summary.json` — Derived daily portfolio values
- `docs/` — GitHub Pages static site

## GitHub Actions

The daily workflow (`.github/workflows/daily-update.yml`) runs at 3 PM PST:

1. Fetch today's prices for all held products
2. Re-derive the daily summary
3. Generate static JSON files in `docs/data/`
4. Commit and push

## GitHub Pages

The `docs/` folder is served via GitHub Pages with password + PAT authentication. Data files in `docs/data/` are auto-generated by the daily job.
