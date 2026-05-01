# Firebase Setup (Owner Auth, Firestore, and Daily Price Fetch)

This is the canonical setup guide for Firebase in this repository.

It covers:

1. Frontend Google Auth + Firestore owner data
2. Migration from local `transactions.json` to Firestore
3. Daily GitHub Actions price fetch via Firestore

## Prerequisites

- Firebase project: `tcg-tracker-b1fb3` (or your own)
- Firestore Database enabled (Native mode)
- Google Auth provider enabled
- Repo deployed to GitHub Pages

## Quick Start Checklist

1. Enable Google Sign-In in Firebase Auth
2. Configure GitHub Pages to serve from `main` branch `/docs` folder
3. Add GitHub Pages domain to authorized domains
4. Publish rules from `FIRESTORE_RULES.md`
5. Sign in on your live site and confirm reads/writes
6. (Optional) migrate local JSON to Firestore
7. Add `FIREBASE_SERVICE_ACCOUNT_JSON` secret for daily price fetch

## GitHub Pages Setup

1. GitHub repo -> Settings -> Pages
2. Source: Deploy from a branch
3. Branch: `main`
4. Folder: `/docs`
5. Save and wait for first publish

Your production URL should be:

- `https://<username>.github.io/<repo>/`

Example for this repo:

- `https://gauravagarwal003.github.io/TCG_Tracker/`

Do not include `/docs` in the live URL.

## 1) Frontend Auth + Firestore Setup

### Enable Google Sign-In

1. Open Firebase Console
2. Authentication -> Sign-in method
3. Enable Google provider

### Add Authorized Domain

1. Authentication -> Settings -> Authorized domains
2. Add your Pages domain host (example: `gauravagarwal003.github.io`)

### Publish Firestore Rules

Copy the full rules from `FIRESTORE_RULES.md` and publish them in Firebase Console.

### Verify Live Site

1. Open `https://<username>.github.io/<repo>/`
2. Sign in with Google
3. Confirm dashboard and transactions load

## 2) Migrate Existing Local Data to Firestore

If Firestore is empty but local `transactions.json` has history:

```bash
.venv/bin/python3 migrate_transactions_to_firestore.py --uid YOUR_FIREBASE_UID
```

Overwrite existing docs for that UID if needed:

```bash
.venv/bin/python3 migrate_transactions_to_firestore.py --uid YOUR_FIREBASE_UID --overwrite
```

Required env var (one of):

- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `FIREBASE_SERVICE_ACCOUNT_FILE`

## 3) Enable Daily Price Fetch in GitHub Actions

### Add service-account secret

1. Firebase Console -> Project Settings -> Service Accounts -> generate key
2. GitHub repo -> Settings -> Secrets and variables -> Actions
3. Add secret: `FIREBASE_SERVICE_ACCOUNT_JSON`

The workflow auto-detects this secret:

- Present: runs `python daily_run.py --firebase-union`, which reads your Firestore transactions and refreshes shared price files
- Missing: runs legacy local mode

### Add cost guardrails (recommended)

1. Firebase Console -> Usage and billing -> Budgets and alerts
2. Set budget to $0 and alert at 50%, 90%, 100%
3. Firestore -> Usage tab: monitor daily reads/writes

## Data Model

- `users/{uid}/transactions/{txnId}`: owner transaction history
- `users/{uid}/holdings/{holdingId}`: optional derived holdings
- `users/{uid}/meta/{docId}`: user metadata flags/preferences
- `product_mappings/{groupId_productId}`: shared mapping metadata for search/autocomplete

## Troubleshooting

### Login works but dashboard is empty

1. Confirm you're logged in under the expected email/UID
2. Confirm docs exist at `users/{uid}/transactions`
3. Confirm rules from `FIRESTORE_RULES.md` are published
4. Hard refresh browser after deploy (`Cmd+Shift+R`)

### Transactions fail to save

1. Check browser console for Firestore permission errors
2. Re-check rules for `users/{uid}/transactions`
3. Confirm `firebase-config.js` points to the correct project

### Daily job not fetching prices

1. Confirm `FIREBASE_SERVICE_ACCOUNT_JSON` exists in GitHub Actions secrets
2. Confirm service account has Firestore access
3. Review workflow logs

## Current Status

Implemented:

1. Frontend Firebase Google Auth + Firestore CRUD flow
2. Owner-only login guard in the static app and Firestore rules
3. Daily Firestore-backed price fetch in GitHub Actions
4. Local migration script from JSON to Firestore

## Related Docs

1. `FIRESTORE_RULES.md` - production rules used by this setup
2. `README.md` - project overview and local run commands
3. `DEPLOYMENT.md` - deployment checklist, runbook, and free hosting options
