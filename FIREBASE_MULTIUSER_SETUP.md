# Firebase Multi-User + Free Daily Union Fetch

This repo now supports a free-friendly daily fetch mode that:

1. Reads all active product IDs across users from Firestore
2. Deduplicates them into one union set
3. Fetches each product price once per day in GitHub Actions

The scheduler entrypoint is:

- `python daily_run.py --firebase-union`

## What Was Implemented In Code

1. Firestore union loader in `firebase_union.py`
2. Explicit-key single-day fetch in `price_fetcher.py`
3. Firebase union run mode in `daily_run.py`
4. Workflow auto-switch in `.github/workflows/daily-update.yml`
5. Dependency update in `requirements.txt` (`firebase-admin`)

## Firestore Data Model (Recommended)

Use both collections below:

1. User holdings (source of truth)

- `users/{uid}/holdings/{holdingId}`
  - `categoryId` (string or number)
  - `group_id` (string or number)
  - `product_id` (string or number)
  - `quantity` (number)

2. Active products index (fast for scheduler)

- `active_products/{categoryId_groupId_productId}`
  - `categoryId`
  - `group_id`
  - `product_id`
  - `count` (number of users/positions holding it)

Notes:

- The daily job first reads `active_products`.
- If `active_products` is empty, it falls back to scanning `users/*/holdings`.

## Manual Steps You Need To Do (External Consoles)

These steps require your Firebase/GitHub account access, so I cannot do them from this workspace.

1. Create Firebase project

- Open Firebase Console.
- Enable Firestore Database (Native mode).
- Enable Authentication -> Google provider.

2. Create service account for GitHub Actions

- Firebase Console -> Project Settings -> Service Accounts.
- Generate a new private key JSON.
- Keep it secure.

3. Add GitHub Actions secret

- GitHub repo -> Settings -> Secrets and variables -> Actions.
- Add secret name: `FIREBASE_SERVICE_ACCOUNT_JSON`
- Paste entire service account JSON content as the secret value.

4. Push these code changes to `main`

- The existing daily workflow will detect the secret.
- If secret exists: it runs `--firebase-union` mode.
- If secret is missing: it runs legacy local mode.

## Firestore Security Rules (Starter)

Apply rules that isolate each user's holdings by UID.

```text
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId}/holdings/{holdingId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // Read-only to clients; maintained by trusted backend/admin contexts.
    match /active_products/{docId} {
      allow read: if request.auth != null;
      allow write: if false;
    }
  }
}
```

## Keeping `active_products` Updated

Two options:

1. App-side transaction write path updates index counts
2. Scheduled repair job recalculates index from `users/*/holdings`

For small scale, app-side updates are enough.

## Free Tier Notes

1. This avoids Cloud Scheduler/Functions billing for daily jobs by using GitHub Actions cron.
2. Firestore/Auth/GitHub Actions still have free-tier quotas.
3. Your external price source rate limits can still become the limiting factor.

## Local Test Command

With credentials set in shell env:

```bash
export FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
python daily_run.py --firebase-union
```

## Current Scope vs Next Scope

Implemented now:

1. Daily union fetch from Firestore in GitHub Actions
2. Backward-compatible fallback to existing local mode

Not yet implemented in this patch:

1. Full frontend migration from GitHub PAT flow to Firebase Auth + Firestore CRUD
2. Automatic `active_products` maintenance in client transaction writes

Those are the next logical steps once you confirm desired Firestore document formats for transaction history and holdings updates.
