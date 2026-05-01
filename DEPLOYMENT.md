# Deployment Runbook (GitHub Pages + Firestore)

This runbook prepares TCG Tracker as a personal app available from anywhere while staying on free tiers.

## Architecture

- Hosting/UI: GitHub Pages (free)
- Auth + database: Firebase Auth + Firestore (Spark free tier)
- Daily market-price updates: GitHub Actions cron (free minutes on public repos)
- Static shared assets: committed in `docs/data` and `docs/prices`

## Pre-Deploy Checklist

1. Confirm GitHub Pages source is `main` branch and `/docs` folder.
2. Confirm live URL opens at `https://<username>.github.io/<repo>/`.
3. Enable Google provider in Firebase Authentication.
4. Add `github.io` host to Firebase Authorized domains.
5. Publish Firestore rules from `FIRESTORE_RULES.md`.
6. Add GitHub Actions secret `FIREBASE_SERVICE_ACCOUNT_JSON`.
7. Run one manual GitHub Actions dispatch for `Daily Price Update`.
8. Verify your Google account can sign in, add a transaction, and see dashboard updates.

## Hosting

GitHub Pages is the only hosting path. Firebase is used for Google Auth and Firestore, not for hosting deploys.

## Production Verification

## User flow

1. Open the live site.
2. Sign in with Google.
3. Add one BUY transaction.
4. Confirm transaction appears on `transactions.html`.
5. Confirm holdings and chart update on `index.html`.

## Scheduler flow

1. Trigger `.github/workflows/daily-update.yml` manually.
2. Check logs show either:
   - `Firebase credentials detected: running Firestore-backed price update`, or
   - `No Firebase credentials: running legacy local mode`.
3. Confirm new/updated price files were committed under `prices/` and `docs/prices/`.

## Free-Tier Cost Controls

1. Firebase Console -> Usage and billing -> set budget alerts (50%, 90%, 100%).
2. In Firestore usage dashboard, watch read/write spikes weekly.
3. Keep large analytical reads out of client code.
4. Avoid public endpoints that can be scraped heavily.

## Reliability Controls

1. Keep Firestore rules default-deny outside required paths.
2. Keep GitHub Actions bot commits tagged with `[skip ci]` to prevent loops.
3. If a workflow push fails, workflows already retry with `git pull --rebase` + push.
4. Use `run_docs.sh` before major UI pushes to catch static-site issues early.

## Rollback Plan

1. Revert latest commit on `main`.
2. Re-run `Rebuild Docs on Code Change` workflow.
3. Hard refresh browser (`Cmd+Shift+R`) and verify auth + dashboard load.

## Recommended Next Improvements

1. Enable Firebase App Check for Firestore in web clients to reduce automated abuse.
2. Add a lightweight synthetic check that loads `index.html` and `transactions.html`.

## Other Free Hosting Options

If you want alternatives later (still free):

1. Cloudflare Pages + Firestore: similar static flow, strong CDN, custom domain support.
2. Netlify + Firestore: easy previews and deploys; works with this static architecture.
3. Firebase Hosting + Firestore: useful later if you decide to leave GitHub Pages.
