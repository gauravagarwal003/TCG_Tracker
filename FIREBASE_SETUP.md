# Firebase Setup (Auth, Firestore, and Daily Union Fetch)

This is the canonical setup guide for Firebase in this repository.

It covers:

1. Frontend Google Auth + Firestore per-user data
2. Migration from local `transactions.json` to Firestore
3. Daily GitHub Actions union fetch via Firestore

## Prerequisites

- Firebase project: `tcg-tracker-b1fb3` (or your own)
- Firestore Database enabled (Native mode)
- Google Auth provider enabled
- Repo deployed to GitHub Pages

## Quick Start Checklist

1. Enable Google Sign-In in Firebase Auth
2. Add GitHub Pages domain to authorized domains
3. Publish rules from `FIRESTORE_RULES.md`
4. Sign in on your live site and confirm reads/writes
5. (Optional) migrate local JSON to Firestore
6. Add `FIREBASE_SERVICE_ACCOUNT_JSON` secret for union daily fetch

## 1) Frontend Auth + Firestore Setup

### Enable Google Sign-In

1. Open Firebase Console
2. Authentication -> Sign-in method
3. Enable Google provider

### Add Authorized Domain

1. Authentication -> Settings -> Authorized domains
2. Add your Pages domain (example: `gauravagarwal003.github.io`)

### Publish Firestore Rules

Copy the full rules from `FIRESTORE_RULES.md` and publish them in Firebase Console.

### Verify Live Site

1. Open `https://<username>.github.io/TCG_Tracker/docs/index.html`
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

## 3) Enable Daily Union Fetch in GitHub Actions

### Add service-account secret

1. Firebase Console -> Project Settings -> Service Accounts -> generate key
2. GitHub repo -> Settings -> Secrets and variables -> Actions
3. Add secret: `FIREBASE_SERVICE_ACCOUNT_JSON`

The workflow auto-detects this secret:

- Present: runs `python daily_run.py --firebase-union`
- Missing: runs legacy local mode

## Data Model

- `users/{uid}/transactions/{txnId}`: per-user transaction history
- `users/{uid}/holdings/{holdingId}`: optional derived holdings
- `users/{uid}/meta/{docId}`: user metadata flags/preferences
- `product_mappings/{groupId_productId}`: shared mapping metadata for search/autocomplete
- `active_products/{cat_gid_pid}`: shared union index for scheduler

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

### Daily job not fetching union prices

1. Confirm `FIREBASE_SERVICE_ACCOUNT_JSON` exists in GitHub Actions secrets
2. Confirm service account has Firestore access
3. Review workflow logs

## Current Status

Implemented:

1. Frontend Firebase Google Auth + Firestore CRUD flow
2. Client-side `active_products` index maintenance on add/update/delete
3. Daily union fetch in GitHub Actions
4. Local migration script from JSON to Firestore

## Related Docs

1. `FIRESTORE_RULES.md` - production rules used by this setup
2. `README.md` - project overview and local run commands
