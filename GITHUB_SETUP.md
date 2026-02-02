# GitHub Pages Setup Guide

## Setup Instructions

### 1. Create a GitHub Personal Access Token (REQUIRED)

**You MUST do this before using the site:**

1. Go to: https://github.com/settings/tokens
2. Click "Personal access tokens" → "Tokens (classic)"
3. Click "Generate new token" → "Generate new token (classic)"
4. Fill in:
   - **Note**: "Pokemon Tracker" (or any name)
   - **Expiration**: "No expiration" (or choose a duration)
   - **Select scopes**: ✅ **repo** (check this box - it's required!)
5. Scroll down and click "Generate token"
6. **COPY THE TOKEN IMMEDIATELY** (you'll never see it again!)
7. Keep it somewhere safe (you'll need to paste it when using the site)

### 2. Configure GitHub Repository (Already Done)

The repository info is already set in `docs/github-api.js`:
- Owner: `gauravagarwal003`
- Repo: `Pokemon_Tracker`
- Branch: `main`

### 3. Enable GitHub Pages

1. Go to your repository Settings
2. Click "Pages" in the left sidebar
3. Under "Source", select:
   - Branch: `main`
   - Folder: `/docs`
4. Click "Save"
5. Your site will be live at: `https://YOUR_USERNAME.github.io/Pokemon_Tracker/`

### 4. Enable GitHub Actions

The workflows are already created in `.github/workflows/`. They will:
- Run daily at 6 AM UTC to fetch new prices
- Run automatically when you edit transactions.csv

Make sure Actions are enabled:
1. Go to repository Settings
2. Click "Actions" → "General"
3. Ensure "Allow all actions and reusable workflows" is selected

## How to Use

### First Time:
1. Visit your GitHub Pages site
2. Click "Authenticate with GitHub" 
3. Paste your Personal Access Token
4. Token is stored in your browser session (per device)

### Add/Edit/Delete Transactions:
1. Click "Add Transaction" button
2. Fill in the form
3. Click "Add Transaction"
4. GitHub Actions automatically updates data within 1-2 minutes

### Daily Updates:
- Every day at 6 AM UTC, GitHub Actions fetches new price data
- No manual action needed

## Security Notes

- Your Personal Access Token is stored in **sessionStorage** (cleared when you close the browser)
- Only you can see/use the token (it's not visible to others viewing your site)
- The password in `docs/auth.js` still protects your site from public viewing
- Never commit your Personal Access Token to the repository

## Troubleshooting

**"Failed to load transactions"**
- Check your token has `repo` scope
- Verify GITHUB_CONFIG values are correct
- Check browser console for errors

**"GitHub Actions not running"**
- Ensure Actions are enabled in repository settings
- Check the Actions tab for error messages
- Verify workflows exist in `.github/workflows/`

**"Transaction not updating"**
- Wait 1-2 minutes for GitHub Actions to complete
- Check Actions tab to see workflow progress
- Refresh the page after workflow completes
