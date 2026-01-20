// Pokemon Tracker Widget
// Modes:
// 1. "LOCAL": Connects to your computer running app.py (Computer must be ON).
// 2. "GITHUB": Connects to your GitHub repository (Computer can be OFF).

// --- CONFIGURATION ---
const MODE = "GITHUB"; // Set to "LOCAL" or "GITHUB"

// For LOCAL mode:
const LOCAL_IP = "192.168.1.X"; // Change this to your computer's IP
const LOCAL_URL = `http://${LOCAL_IP}:5001/api/summary`;

// For GITHUB mode:
// Replace <USERNAME> and <REPO> with your actual GitHub details
const GITHUB_USER = "gauravagarwal003"; 
const GITHUB_REPO = "Pokemon_Sealed_Tracker";
const GITHUB_BRANCH = "main";
const GITHUB_URL = `https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/${GITHUB_BRANCH}/summary.json`;
const GITHUB_REPO_URL = `https://github.com/${GITHUB_USER}/${GITHUB_REPO}`;

const API_URL = MODE === "LOCAL" ? LOCAL_URL : GITHUB_URL;

let widget = await createWidget();

// Handle interaction: Open the dashboard/repo when tapped
if (MODE === "LOCAL") {
    // Open the local Flask dashboard
    widget.url = `http://${LOCAL_IP}:5001/`;
} else {
    // Open the GitHub repository
    widget.url = GITHUB_REPO_URL;
}

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {

  widget.presentMedium();
}
Script.complete();

async function createWidget() {
  let w = new ListWidget();
  w.backgroundColor = new Color("#1c1c1e"); // Dark background

  // Title
  let titleStack = w.addStack();
  titleStack.layoutHorizontally();
  let titleTxt = titleStack.addText("Pokemon Tracker");
  titleTxt.textColor = new Color("#ffcb05"); // Pokemon Yellow
  titleTxt.font = Font.boldSystemFont(16);
  w.addSpacer(10);

  try {
    let req = new Request(API_URL);
    // Timeout after 5 seconds
    req.timeoutInterval = 5;
    let data = await req.loadJSON();
    
    // Row 1: Total Value
    let vStack = w.addStack();
    vStack.layoutVertically();
    
    let valLabel = vStack.addText("Total Value");
    valLabel.font = Font.mediumSystemFont(12);
    valLabel.textColor = Color.gray();
    
    let valText = vStack.addText(formatMoney(data.total_value));
    valText.font = Font.boldSystemFont(22);
    valText.textColor = Color.white();
    
    w.addSpacer(8);
    
    // Row 2: Profit/Loss
    let pStack = w.addStack();
    pStack.layoutVertically();
    
    let profitLabel = pStack.addText("Total Profit");
    profitLabel.font = Font.mediumSystemFont(12);
    profitLabel.textColor = Color.gray();
    
    let profitColor = data.profit >= 0 ? new Color("#32d74b") : new Color("#ff453a");
    let profitText = pStack.addText((data.profit >= 0 ? "+" : "") + formatMoney(data.profit));
    profitText.font = Font.boldSystemFont(18);
    profitText.textColor = profitColor;
    
    w.addSpacer();
    
    // Footer: Last Updated
    let footerStack = w.addStack();
    footerStack.layoutHorizontally();
    footerStack.addSpacer();
    let dateTxt = footerStack.addText(`Last: ${data.date}`);
    dateTxt.textColor = new Color("#8e8e93");
    dateTxt.font = Font.systemFont(10);

  } catch (e) {
    let errTxt = w.addText("Connection Error");
    errTxt.textColor = Color.red();
    errTxt.font = Font.boldSystemFont(14);
    
    w.addSpacer(4);
    let subErr = w.addText(MODE === "LOCAL" ? "Check app.py" : "Check GitHub URL");
    subErr.font = Font.systemFont(10);
    subErr.textColor = Color.gray();
    console.log(e);
  }

  return w;
}

function formatMoney(num) {
  return "$" + num.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
