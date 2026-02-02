# GitHub Pages Setup Guide

## Setup Instructions

### 1. Configure GitHub Repository Info

Edit `docs/github-api.js` and update these values:

```javascript
const GITHUB_CONFIG = {
    owner: 'YOUR_GITHUB_USERNAME',     // Change to your GitHub username
    repo: 'Pokemon_Tracker',           // Change if your repo name is different
    branch: 'main',                    // Change if using 'master' or another branch
    clientId: ''                       // Leave empty (not used with Personal Access Token)
};
```

### 2. Create a GitHub Personal Access Token

1. Go to GitHub Settings: https://github.com/settings/tokens
2. Click "Developer settings" (bottom left)
3. Click "Personal access tokens" → "Tokens (classic)"
4. Click "Generate new token" → "Generate new token (classic)"
5. Give it a name like "Pokemon Tracker"
6. Select scopes:
   - ✅ **repo** (Full control of private repositories)
7. Click "Generate token"
8. **IMPORTANT**: Copy the token immediately (you won't see it again!)

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
