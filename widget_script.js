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
const GITHUB_REPO = "Pokemon_Tracker";
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
    
    // Graph: Check if history exists
    if (data.history && data.history.length > 1) {
      w.addSpacer(8);
      // Draw graph (width: 400, height: 100)
      let chartImg = drawChart(data.history, 400, 100, profitColor);
      let chartStack = w.addStack();
      chartStack.addSpacer(); // Center it
      let img = chartStack.addImage(chartImg);
      img.imageSize = new Size(280, 50); // Scale down for display
      chartStack.addSpacer();
    }
    
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

function drawChart(history, width, height, lineColor) {
  let ctx = new DrawContext()
  ctx.size = new Size(width, height)
  ctx.opaque = false
  
  // Extract values and ensure they are numbers
  let values = history.map(h => parseFloat(h["Total Value"]))
  let min = Math.min(...values)
  let max = Math.max(...values)
  let delta = max - min
  
  if (delta === 0) delta = 1

  let path = new Path()
  let stepX = width / (values.length - 1)
  
  // Points logic: Y=0 is TOP, Y=height is BOTTOM
  // We want some padding so the line doesn't hit the absolute edge
  let drawableHeight = height * 0.8
  let padding = height * 0.1

  let points = values.map((val, index) => {
    let x = index * stepX
    let fraction = (val - min) / delta
    let y = (height - padding) - (fraction * drawableHeight)
    return new Point(x, y)
  })

  // 1. Draw Line Stroke
  if (points.length > 0) {
    path.move(points[0])
    for (let i = 1; i < points.length; i++) {
      path.addLine(points[i])
    }
    ctx.addPath(path)
    ctx.setStrokeColor(lineColor)
    ctx.setLineWidth(5)
    ctx.strokePath()
  }

  // 2. Draw Gradient Fill
  if (points.length > 0) {
    let fillPath = new Path()
    fillPath.move(points[0])
    for (let i = 1; i < points.length; i++) {
        fillPath.addLine(points[i])
    }
    // Close shape at bottom corners
    fillPath.addLine(new Point(width, height))
    fillPath.addLine(new Point(0, height))
    fillPath.closeSubpath()
    
    ctx.addPath(fillPath)
    let grad = new LinearGradient()
    grad.colors = [lineColor, new Color(lineColor.hex, 0.0)] // Fade to transparent
    grad.locations = [0, 1]
    grad.startPoint = new Point(0, 0)
    grad.endPoint = new Point(0, height)
    ctx.fillGradient(grad)
  }
  
  return ctx.getImage()
}
