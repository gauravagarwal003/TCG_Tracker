import os
import pandas as pd
from jinja2 import Environment, FileSystemLoader

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
OUTPUT_DIR = os.path.join(BASE_DIR, 'docs')

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Create .nojekyll file to disable Jekyll processing on GitHub Pages
with open(os.path.join(OUTPUT_DIR, '.nojekyll'), 'w') as f:
    pass

# Setup Jinja2 Environment
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

# Mock get_flashed_messages (return empty list)
env.globals['get_flashed_messages'] = lambda with_categories=False: []

# --- Helpers ---
def format_currency(value):
    try:
        return "${:,.2f}".format(float(value)) 
    except:
        return value

def format_int(value):
    try:
        return int(value)
    except:
        return value

# env.filters['format'] = format_currency # Remove this override to use default Jinja format

# --- 1. Load Data ---

# Load Holdings
holdings = []
total_value = 0.0
holdings_file = os.path.join(BASE_DIR, 'current_holdings.csv')
if os.path.exists(holdings_file):
    try:
        df = pd.read_csv(holdings_file)
        if not df.empty:
            holdings = df.to_dict('records')
            if 'Total Value' in df.columns:
                total_value = df['Total Value'].sum()
    except Exception as e:
        print(f"Error reading holdings: {e}")

# Load Transactions
transactions = []
transactions_file = os.path.join(BASE_DIR, 'transactions.csv')
if os.path.exists(transactions_file):
    try:
        df = pd.read_csv(transactions_file)
        df['id'] = df.index
        transactions = df.to_dict('records')
    except Exception as e:
        print(f"Error reading transactions: {e}")

# Load Graphs
graph_html = ""
graph_path = os.path.join(BASE_DIR, 'portfolio_graph.html')
if os.path.exists(graph_path):
    with open(graph_path, 'r') as f:
        graph_html = f.read()

performance_html = ""
perf_path = os.path.join(BASE_DIR, 'performance_graph.html')
if os.path.exists(perf_path):
    with open(perf_path, 'r') as f:
        performance_html = f.read()

# --- 2. Render Pages ---

# --- 2.5 Copy Static Files ---
import shutil

static_src = os.path.join(BASE_DIR, 'static')
static_dst = os.path.join(OUTPUT_DIR, 'static')

if os.path.exists(static_src):
    print("Copying static files...")
    # Remove existing static folder and copy fresh
    if os.path.exists(static_dst):
        shutil.rmtree(static_dst)
    shutil.copytree(static_src, static_dst)

# Mock url_for function for static and page links
def mock_url_for(endpoint, **kwargs):
    if endpoint == 'static':
        filename = kwargs.get('filename', '')
        return f"static/{filename}"
    elif endpoint == 'index':
        return 'index.html'
    elif endpoint == 'transactions':
        return 'transactions.html'
    else:
        return f"{endpoint}.html"

# -- Index --
print("Building index.html...")
template = env.get_template('index.html')
output_html = template.render(
    holdings=holdings,
    total_value=total_value,
    graph_html=graph_html,
    performance_html=performance_html,
    is_static=True,
    url_for=mock_url_for
)
with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w') as f:
    f.write(output_html)

# -- Transactions --
print("Building transactions.html...")
# We need to tweak the transactions template behavior for static site
# or just render it and accept links might be broken (we will fix links with url_for mock)
template = env.get_template('transactions.html')
output_html = template.render(
    transactions=transactions,
    is_static=True,
    url_for=mock_url_for
)

# Post-processing to remove Add/Edit buttons or make them point to GitHub?
# For now, let's keep it simple. The user can see the list.
# We might want to inject a banner saying "Static View".
with open(os.path.join(OUTPUT_DIR, 'transactions.html'), 'w') as f:
    f.write(output_html)

print("Build complete. Output in docs/")
