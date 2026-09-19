// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: green; icon-glyph: chart-line;

/**
 * TCG Tracker iOS Home Screen Widget for Scriptable
 * 
 * Instructions:
 * 1. Install "Scriptable" from the App Store (free).
 * 2. Open Scriptable, tap "+" to create a new script.
 * 3. Paste this entire file and rename it "TCG Tracker".
 * 4. Add a Scriptable widget to your iOS home screen (Small or Medium).
 * 5. Long-press widget -> Edit Widget -> Select "TCG Tracker" as Script.
 */

const DATA_URL = "https://gauravagarwal003.github.io/TCG_Tracker/data/widget_summary.json";
const DASHBOARD_URL = "https://gauravagarwal003.github.io/TCG_Tracker/";

async function fetchData() {
    try {
        const req = new Request(DATA_URL + "?cb=" + Date.now());
        req.timeoutInterval = 10;
        return await req.loadJSON();
    } catch (e) {
        return null;
    }
}

function fmtUSD(val) {
    return "$" + Number(val || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function drawSparkline(points, width, height, strokeColor = "#10b981") {
    const dc = new DrawContext();
    dc.size = new Size(width, height);
    dc.opaque = false;
    dc.respectScreenScale = true;

    if (!points || points.length < 2) return dc.getImage();

    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = max - min || 1;
    const padding = 4;

    const path = new Path();
    for (let i = 0; i < points.length; i++) {
        const x = padding + (i / (points.length - 1)) * (width - 2 * padding);
        const y = height - padding - ((points[i] - min) / range) * (height - 2 * padding);
        if (i === 0) path.move(new Point(x, y));
        else path.addLine(new Point(x, y));
    }

    dc.addPath(path);
    dc.setStrokeColor(new Color(strokeColor, 1.0));
    dc.setLineWidth(2.5);
    dc.strokePath();

    return dc.getImage();
}

async function createWidget(data) {
    const widget = new ListWidget();
    widget.backgroundColor = new Color("#0f172a");
    widget.url = DASHBOARD_URL;

    if (!data) {
        const errText = widget.addText("TCG Tracker");
        errText.textColor = Color.white();
        errText.font = Font.boldSystemFont(14);
        widget.addSpacer(4);
        const sub = widget.addText("Unable to load data.");
        sub.textColor = Color.gray();
        sub.font = Font.systemFont(12);
        return widget;
    }

    const isSmall = config.widgetFamily === "small";

    // Header
    const headerStack = widget.addStack();
    headerStack.layoutHorizontally();
    headerStack.centerAlignContent();

    const title = headerStack.addText("TCG TRACKER");
    title.textColor = new Color("#94a3b8");
    title.font = Font.boldSystemFont(10);

    headerStack.addSpacer();

    const returnBadge = headerStack.addText((data.return_pct >= 0 ? "+" : "") + data.return_pct.toFixed(1) + "%");
    returnBadge.textColor = data.return_pct >= 0 ? new Color("#10b981") : new Color("#ef4444");
    returnBadge.font = Font.boldSystemFont(11);

    widget.addSpacer(4);

    // Main Value
    const valText = widget.addText(fmtUSD(data.total_value));
    valText.textColor = Color.white();
    valText.font = Font.boldSystemFont(isSmall ? 19 : 22);

    // 24h change
    const daySign = data.day_value_change >= 0 ? "+" : "";
    const dayColor = data.day_value_change >= 0 ? new Color("#10b981") : new Color("#ef4444");
    const dayText = widget.addText(`${daySign}${fmtUSD(data.day_value_change)} (${daySign}${data.day_gain_loss_pct.toFixed(1)}%) 24h`);
    dayText.textColor = dayColor;
    dayText.font = Font.mediumSystemFont(11);

    widget.addSpacer(isSmall ? 6 : 8);

    // Sparkline Chart
    const sparklineData = data.sparkline_7d || [];
    if (sparklineData.length > 1) {
        const sparklineWidth = isSmall ? 130 : 280;
        const sparklineHeight = isSmall ? 35 : 40;
        const sparkImg = drawSparkline(sparklineData, sparklineWidth, sparklineHeight, data.day_value_change >= 0 ? "#10b981" : "#ef4444");
        const imgEl = widget.addImage(sparkImg);
        imgEl.imageSize = new Size(sparklineWidth, sparklineHeight);
    }

    // Medium Widget Extra: Top Gainer Item
    if (!isSmall && data.top_gainer) {
        widget.addSpacer(6);
        const gainerStack = widget.addStack();
        gainerStack.layoutHorizontally();
        gainerStack.centerAlignContent();

        const tag = gainerStack.addText("TOP GAINER: ");
        tag.textColor = new Color("#94a3b8");
        tag.font = Font.boldSystemFont(10);

        const gainerName = gainerStack.addText(data.top_gainer.name);
        gainerName.textColor = Color.white();
        gainerName.font = Font.systemFont(11);
        gainerName.lineLimit = 1;

        gainerStack.addSpacer();

        const gainerPct = gainerStack.addText("+" + Number(data.top_gainer.change_pct).toFixed(1) + "%");
        gainerPct.textColor = new Color("#10b981");
        gainerPct.font = Font.boldSystemFont(11);
    }

    return widget;
}

const data = await fetchData();
const widget = await createWidget(data);

if (config.runsInWidget) {
    Script.setWidget(widget);
} else {
    widget.presentMedium();
}
Script.complete();

