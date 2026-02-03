import os
import pandas as pd
import shutil
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

# Copy static files
STATIC_SOURCE_DIR = os.path.join(BASE_DIR, 'static')
STATIC_DEST_DIR = os.path.join(OUTPUT_DIR, 'static')
if os.path.exists(STATIC_DEST_DIR):
    shutil.rmtree(STATIC_DEST_DIR)
shutil.copytree(STATIC_SOURCE_DIR, STATIC_DEST_DIR)
print("Copied static files to docs/static")

# Mock get_flashed_messages (return empty list)
env.globals['get_flashed_messages'] = lambda with_categories=False: []

# Copy JS files directly to docs folder
print("Copying JS files to docs/...")
js_files = ['auth.js', 'github-api.js', 'transaction-manager.js']
for js_file in js_files:
    src = os.path.join(OUTPUT_DIR, js_file)
    if os.path.exists(src):
        print(f"  - {js_file} already exists")
    else:
        # Check if there's a source to copy from (shouldn't happen, files should already be in docs)
        print(f"  - {js_file} needs to be created in docs/")

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

# Load mappings and add image URLs to transactions
import json
mappings_file = os.path.join(BASE_DIR, 'mappings.json')
mappings_dict = {}
if os.path.exists(mappings_file):
    with open(mappings_file, 'r') as f:
        mappings = json.load(f)
        mappings_dict = {m['product_id']: m.get('imageUrl', '') for m in mappings}

for tx in transactions:
    product_id = str(tx.get('product_id', ''))
    tx['Image URL'] = mappings_dict.get(product_id, '')

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
    url_for=mock_url_for,
    active_page='index'
)

# auth.js is already included via base.html template when is_static=True

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
    url_for=mock_url_for,
    active_page='transactions'
)

# Add GitHub API scripts after the auth.js that's already in the template
# We look for the auth.js script tag and add after it
github_scripts = '''<script src="auth.js"></script>
    <script src="github-api.js"></script>
    <script src="transaction-manager.js"></script>'''

output_html = output_html.replace('<script src="auth.js"></script>', github_scripts)

with open(os.path.join(OUTPUT_DIR, 'transactions.html'), 'w') as f:
    f.write(output_html)

print("Build complete. Output in docs/")
