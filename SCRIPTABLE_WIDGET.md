# Private Scriptable Widget

This setup publishes `widget_summary.json` to a private GitHub repository and lets Scriptable fetch it with a token stored in iOS Keychain.

## What Is Already Set Up

- Private widget data repo: `gauravagarwal003/TCG_Widget_Private`
- Private payload path: `widget_summary.json`
- Publisher script: `scripts/publish_widget_private_repo.py`
- Scriptable setup script: `scriptable/tcg-widget-setup.js`
- Scriptable widget script: `scriptable/tcg-private-widget.js`

The payload includes:

- `day_gain_loss`
- `day_gain_loss_pct`
- `day_value_change`
- `day_cost_basis_change`
- `total_value`
- `gain_loss`
- `latest_date`
- `previous_date`

## Steps I Cannot Do From Here

1. Create a GitHub token for the phone and Actions.
   - Create a fine-grained token for `gauravagarwal003/TCG_Widget_Private`.
   - Give it repository Contents read/write access if you use the same token for Actions.
   - If you want separate tokens, the phone token only needs Contents read access.

2. Add the token to this repo's Actions secrets.
   - In `gauravagarwal003/TCG_Tracker`, add secret `WIDGET_PRIVATE_REPO_TOKEN`.
   - I already added `WIDGET_PRIVATE_REPO` with value `gauravagarwal003/TCG_Widget_Private`.

3. Install the Scriptable scripts on your iPhone.
   - Add `tcg-widget-setup.js` to Scriptable and run it once.
   - Paste the GitHub token.
   - Use repo `gauravagarwal003/TCG_Widget_Private`, branch `main`, path `widget_summary.json`.
   - Add `tcg-private-widget.js` as the home screen widget script.

4. Turn off public widget JSON after the private widget works.
   - Add Actions secret `PUBLISH_PUBLIC_WIDGET_DATA` with value `0`.
   - Run `Daily Price Update` manually once.
   - After that, public `docs/data/holdings.json`, `daily_summary.json`, and `widget_summary.json` become empty placeholders.

## Notes

- The widget caches the last good payload in Scriptable Keychain.
- If GitHub is temporarily unreachable, it still shows the cached gain/loss instead of a blank widget.
- GitHub Pages cannot protect JSON files with a token; the private repo API is what makes this token-gated.
