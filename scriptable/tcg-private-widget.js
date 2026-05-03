// TCG Tracker private Scriptable widget.
// Requires scriptable/tcg-widget-setup.js to store the private repo and token.

const TOKEN_KEY = "TCG_WIDGET_GITHUB_TOKEN";
const REPO_KEY = "TCG_WIDGET_PRIVATE_REPO";
const BRANCH_KEY = "TCG_WIDGET_PRIVATE_BRANCH";
const PATH_KEY = "TCG_WIDGET_PRIVATE_PATH";
const CACHE_KEY = "TCG_WIDGET_LAST_PAYLOAD";

const palette = {
  background: new Color("#0f172a"),
  panel: new Color("#111827"),
  text: Color.white(),
  muted: new Color("#94a3b8"),
  green: new Color("#22c55e"),
  red: new Color("#ef4444"),
  amber: new Color("#f59e0b"),
};

function money(value) {
  const number = Number(value || 0);
  const sign = number < 0 ? "-" : "";
  return `${sign}$${Math.abs(number).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function signedMoney(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? "+" : "-"}$${Math.abs(number).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function pct(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function addLine(widget, text, font, color = palette.text) {
  const line = widget.addText(text);
  line.font = font;
  line.textColor = color;
  line.lineLimit = 1;
  line.minimumScaleFactor = 0.7;
  return line;
}

async function fetchPrivatePayload() {
  if (!Keychain.contains(TOKEN_KEY) || !Keychain.contains(REPO_KEY)) {
    throw new Error("Run tcg-widget-setup.js first.");
  }

  const token = Keychain.get(TOKEN_KEY);
  const repo = Keychain.get(REPO_KEY);
  const branch = Keychain.contains(BRANCH_KEY) ? Keychain.get(BRANCH_KEY) : "main";
  const path = Keychain.contains(PATH_KEY) ? Keychain.get(PATH_KEY) : "widget_summary.json";

  const encodedPath = path.split("/").map(encodeURIComponent).join("/");
  const request = new Request(`https://api.github.com/repos/${repo}/contents/${encodedPath}?ref=${encodeURIComponent(branch)}`);
  request.headers = {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${token}`,
    "X-GitHub-Api-Version": "2022-11-28",
  };

  const file = await request.loadJSON();
  if (!file || !file.content) {
    throw new Error(`Missing ${path} in private repo.`);
  }

  const raw = Data.fromBase64String(String(file.content).replace(/\s/g, "")).toRawString();
  const payload = JSON.parse(raw);
  Keychain.set(CACHE_KEY, JSON.stringify(payload));
  return { payload, cached: false };
}

async function loadPayload() {
  try {
    return await fetchPrivatePayload();
  } catch (error) {
    if (Keychain.contains(CACHE_KEY)) {
      return { payload: JSON.parse(Keychain.get(CACHE_KEY)), cached: true, error };
    }
    throw error;
  }
}

function renderError(message) {
  const widget = new ListWidget();
  widget.backgroundColor = palette.background;
  widget.setPadding(14, 14, 14, 14);
  addLine(widget, "TCG Tracker", Font.semiboldSystemFont(13), palette.muted);
  widget.addSpacer(8);
  addLine(widget, "Could not load", Font.boldSystemFont(20), palette.red);
  widget.addSpacer(4);
  const detail = widget.addText(message);
  detail.font = Font.systemFont(11);
  detail.textColor = palette.muted;
  detail.lineLimit = 3;
  return widget;
}

function renderWidget(payload, cached) {
  const dayGain = Number(payload.day_gain_loss || 0);
  const dayColor = dayGain >= 0 ? palette.green : palette.red;
  const widget = new ListWidget();
  widget.backgroundColor = palette.background;
  widget.setPadding(14, 14, 14, 14);

  const top = widget.addStack();
  top.layoutHorizontally();
  const title = top.addText("TCG Tracker");
  title.font = Font.semiboldSystemFont(13);
  title.textColor = palette.muted;
  top.addSpacer();
  const status = top.addText(cached ? "cached" : payload.latest_date || "");
  status.font = Font.mediumSystemFont(11);
  status.textColor = cached ? palette.amber : palette.muted;

  widget.addSpacer(10);
  addLine(widget, signedMoney(dayGain), Font.boldSystemFont(30), dayColor);
  addLine(widget, `${pct(payload.day_gain_loss_pct)} today`, Font.mediumSystemFont(13), dayColor);

  widget.addSpacer(10);
  const row = widget.addStack();
  row.layoutHorizontally();
  const valueStack = row.addStack();
  valueStack.layoutVertically();
  const label = valueStack.addText("Value");
  label.font = Font.mediumSystemFont(10);
  label.textColor = palette.muted;
  const value = valueStack.addText(money(payload.total_value));
  value.font = Font.semiboldSystemFont(15);
  value.textColor = palette.text;

  row.addSpacer();
  const totalStack = row.addStack();
  totalStack.layoutVertically();
  const gainLabel = totalStack.addText("All-time");
  gainLabel.font = Font.mediumSystemFont(10);
  gainLabel.textColor = palette.muted;
  const totalGain = totalStack.addText(signedMoney(payload.gain_loss));
  totalGain.font = Font.semiboldSystemFont(15);
  totalGain.textColor = Number(payload.gain_loss || 0) >= 0 ? palette.green : palette.red;

  widget.addSpacer();
  const foot = `${payload.holdings_count || 0} holdings`;
  addLine(widget, foot, Font.mediumSystemFont(10), palette.muted);
  return widget;
}

let widget;
try {
  const result = await loadPayload();
  widget = renderWidget(result.payload, result.cached);
} catch (error) {
  widget = renderError(error.message || String(error));
}

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentMedium();
}

Script.complete();
