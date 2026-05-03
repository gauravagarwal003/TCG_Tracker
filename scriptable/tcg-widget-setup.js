// Run once in Scriptable to store private widget settings in iOS Keychain.

const TOKEN_KEY = "TCG_WIDGET_GITHUB_TOKEN";
const REPO_KEY = "TCG_WIDGET_PRIVATE_REPO";
const BRANCH_KEY = "TCG_WIDGET_PRIVATE_BRANCH";
const PATH_KEY = "TCG_WIDGET_PRIVATE_PATH";

const alert = new Alert();
alert.title = "TCG Widget Setup";
alert.message = "Paste the GitHub token and private repo used by the widget.";
alert.addTextField("GitHub token", Keychain.contains(TOKEN_KEY) ? Keychain.get(TOKEN_KEY) : "");
alert.addTextField("Private repo (owner/name)", Keychain.contains(REPO_KEY) ? Keychain.get(REPO_KEY) : "gauravagarwal003/TCG_Widget_Private");
alert.addTextField("Branch", Keychain.contains(BRANCH_KEY) ? Keychain.get(BRANCH_KEY) : "main");
alert.addTextField("Path", Keychain.contains(PATH_KEY) ? Keychain.get(PATH_KEY) : "widget_summary.json");
alert.addAction("Save");
alert.addCancelAction("Cancel");

const result = await alert.present();
if (result === -1) {
  Script.complete();
}

const token = alert.textFieldValue(0).trim();
const repo = alert.textFieldValue(1).trim();
const branch = alert.textFieldValue(2).trim() || "main";
const path = alert.textFieldValue(3).trim() || "widget_summary.json";

if (!token || !repo) {
  throw new Error("Token and private repo are required.");
}

Keychain.set(TOKEN_KEY, token);
Keychain.set(REPO_KEY, repo);
Keychain.set(BRANCH_KEY, branch);
Keychain.set(PATH_KEY, path);

const done = new Alert();
done.title = "Saved";
done.message = "Your TCG widget can now read the private repo.";
done.addAction("OK");
await done.present();

Script.complete();
