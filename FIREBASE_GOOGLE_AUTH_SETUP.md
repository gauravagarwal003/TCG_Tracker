# Firebase Setup for Google Auth + Firestore (Multi-User)

This guide walks you through setting up the complete Google Auth + Firestore infrastructure for TCG Tracker multi-user support.

## What Changed

- ✅ Replaced password auth with **Google Sign-In**
- ✅ Replaced GitHub commits with **Firestore per-user transactions**
- ✅ No more GitHub PAT required on the frontend
- ✅ Each user's data is isolated and private
- ✅ Daily union fetch still works via GitHub Actions (uses service account)

## Prerequisites

- Firebase project already created (tcg-tracker-b1fb3)
- Your GitHub repo is public
- Code changes are already committed to main

## Manual Steps (You Must Do These)

### Step 1: Enable Google Authentication in Firebase Console

1. Open [Firebase Console](https://console.firebase.google.com)
2. Select your project: **tcg-tracker-b1fb3**
3. Go to **Authentication** → **Sign-in method**
4. Click **Google** provider
5. Toggle **Enable** to ON
6. Click **Save**

### Step 2: Add Your GitHub Pages Domain to Authorized Domains

1. Still in **Authentication** → **Settings**
2. Scroll to **Authorized domains**
3. Click **Add domain**
4. Add your GitHub Pages domain: `yourusername.github.io`
5. Click **Add**

**Example**: If your repo is `gauravagarwal003/TCG_Tracker`, add:
- `gauravagarwal003.github.io`

### Step 3: Deploy to GitHub Pages

Push the code to main (it should already be committed):

```bash
git push origin main
```

GitHub Actions will deploy to GitHub Pages automatically.

### Step 4: Apply Firestore Security Rules

1. In Firebase Console, go to **Firestore Database** → **Rules**
2. Click **Edit rules**
3. Replace the entire ruleset with the rules in `FIRESTORE_RULES.md` (in this repo)
4. Click **Publish**

### Step 5: Test the Live Site

1. Wait 2-3 minutes for GitHub Pages to rebuild
2. Open your live site: `https://yourusername.github.io/TCG_Tracker/docs/index.html`
3. You should see a **Google Sign-In** prompt
4. Click "Sign in with Google"
5. You'll be redirected to Google login
6. After login, you should see:
   - Your email in the navbar
   - A logout button
   - The dashboard

### Step 6: Test Adding a Transaction

1. From the dashboard, go to **Transactions** page
2. Click **Add** button
3. Fill in the form (search for a product, etc.)
4. Click **Add Transaction**
5. Check your Firestore console to confirm the transaction was saved:
   - Go to **Firestore Database** → **Data**
   - Navigate to `users/{your-uid}/transactions`
   - You should see your new transaction document

## Architecture

### User Data Flow

```
User's Browser
    ↓ (Google OAuth)
Firebase Auth
    ↓ (ID token)
Firestore (per-user collections)
    ↓  
users/{uid}/transactions  (reads/writes own data)
users/{uid}/holdings      (future: derived view)
active_products           (shared, read-only index)
```

### Daily Price Fetch (GitHub Actions)

```
GitHub Actions (daily cron)
    ↓ (uses FIREBASE_SERVICE_ACCOUNT_JSON secret)
Firebase Admin SDK
    ↓ (server-side, bypasses security rules)
active_products collection
    ↓ (reads union of all products)
Fetch prices from tcgcsv.com
    ↓
Save to prices/ directory
    ↓ (commit to repo)
GitHub Pages static assets
```

## Firestore Collections Created Automatically

When you first login and add a transaction:

```
Firestore
├── users/
│   ├── user1uid/
│   │   └── transactions/
│   │       ├── txn1 { type, items, date_received, amount, ... }
│   │       ├── txn2 { ... }
│   │       └── ...
│   ├── user2uid/
│   │   └── transactions/
│   │       ├── txn1 { ... }
│   │       └── ...
│   └── ...
└── active_products/
    ├── 3_23237_502000 { categoryId: 3, group_id: 23237, product_id: 502000, count: 2, users: [uid1, uid2] }
    ├── 3_23286_512822 { ... }
    └── ...
```

## Troubleshooting

### "Sign in with Google" button not showing

- Wait 2-3 minutes for GitHub Pages to rebuild after push
- Hard refresh: **Cmd+Shift+R** (Mac) or **Ctrl+Shift+R** (Windows)
- Check browser console for errors: **F12 → Console**

### Login fails with "401 Unauthorized"

- Confirm Google provider is **Enabled** in Firebase Console
- Confirm your GitHub Pages domain is in **Authorized domains**
- Check Firebase project ID matches in code (`tcg-tracker-b1fb3`)

### Transaction not saved to Firestore

- Confirm you're logged in (should see email in navbar)
- Confirm Firestore rules are published (check `FIRESTORE_RULES.md`)
- Check browser console for Firestore errors
- In Firebase Console, go to `Firestore Database → Data` to see collections

### Daily price fetch not working in GitHub Actions

- Confirm `FIREBASE_SERVICE_ACCOUNT_JSON` secret is set in GitHub
- Confirm backend service account has Firestore write permissions
- Check GitHub Actions workflow logs: **Settings → Actions → Daily Price Update**

## What's Not Yet Implemented

- Dashboard stats currently still show static data (can be updated to read from Firestore later)
- Holdings view does not yet read live from user's Firestore transactions
- Transactions list still shows static JSON (can wire to Firestore per-user view)

These are future enhancements once users confirm the core auth/save flow is working.

## Rollback to GitHub-Only Mode

If you need to revert to GitHub commits only (without Firestore):

1. Comment out Firestore scripts in HTML files:
   - docs/firebase-config.js
   - docs/firebase-auth.js
   - docs/firestore-data.js
2. Restore old auth.js password prompts
3. Restore github-api.js for commits
4. Revert add-transaction.html form handler

## Next Steps

After testing:

1. Share your live site link with others
2. They sign in with their Google account
3. Each user's transactions are stored separately
4. Invite more users to build a shared portfolio tracker

