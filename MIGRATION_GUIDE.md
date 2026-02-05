# Multi-TCG Support Migration Guide

## Overview
This guide documents the migration from Pokemon-only TCG tracking to supporting multiple TCG products with different categoryIds.

**Migration Date:** February 4, 2026  
**Backup Location:** `backup_20260204_154658/`

## What Changed

### Before
- All products were Pokemon TCG (categoryId = 3)
- categoryId was hardcoded in many places
- Price fetching assumed Pokemon categoryId

### After
- Support for multiple TCG categories:
  - `1` - Magic: The Gathering
  - `2` - Yu-Gi-Oh!
  - `3` - Pokemon TCG (default)
  - `4` - Other TCG products
- categoryId stored in mappings.json for each product
- categoryId optionally included in CSV files for clarity
- Price fetching reads categoryId from mappings

## Files Modified

1. **transactions.csv** - Added optional `categoryId` column
2. **current_holdings.csv** - Added optional `categoryId` column  
3. **mappings.json** - Already has categoryId for each product
4. **functions.py** - Updated to read categoryId from mappings
5. **update_prices.py** - Updated to use correct categoryId per product
6. **app.py** - Already supports categoryId in forms

## How to Rollback

If something goes wrong, follow these steps:

### Step 1: Stop any running processes
```bash
# Stop any running Flask apps or scheduled jobs
pkill -f "python app.py"
pkill -f "python daily_run.py"
```

### Step 2: Restore from backup
```bash
cd /Users/gaurav/Downloads/Projects/Pokemon/Pokemon_Tracker

# Restore all critical files
cp backup_20260204_154658/transactions.csv .
cp backup_20260204_154658/current_holdings.csv .
cp backup_20260204_154658/mappings.json .
cp backup_20260204_154658/data.json .
cp backup_20260204_154658/summary.json .
cp backup_20260204_154658/daily_tracker.csv .
```

### Step 3: Remove categoryId columns from CSVs (if needed)
The system is backward compatible, but if you want to completely revert:

```python
import pandas as pd

# For transactions.csv
df = pd.read_csv('transactions.csv')
if 'categoryId' in df.columns:
    df = df.drop(columns=['categoryId'])
    df.to_csv('transactions.csv', index=False)

# For current_holdings.csv  
df = pd.read_csv('current_holdings.csv')
if 'categoryId' in df.columns:
    df = df.drop(columns=['categoryId'])
    df.to_csv('current_holdings.csv', index=False)
```

### Step 4: Restore original code (if needed)
```bash
git checkout functions.py update_prices.py
# Or manually restore from backup if not using git
```

### Step 5: Verify system works
```bash
python app.py
# Check that products load correctly
# Check that prices update correctly
```

## Testing After Migration

### Test 1: Verify existing Pokemon products still work
```bash
python update_prices.py
# Should fetch prices for all existing Pokemon products
```

### Test 2: Add a new Pokemon product
1. Go to transaction form
2. Add a Pokemon product manually
3. Verify categoryId defaults to 3

### Test 3: Add a non-Pokemon product
1. Go to transaction form  
2. Add a product with a different categoryId (e.g., Magic: The Gathering = 1)
3. Verify price fetching works with correct categoryId

### Test 4: Check data integrity
```bash
python -c "
import pandas as pd
import json

# Check transactions
df = pd.read_csv('transactions.csv')
print(f'Transactions: {len(df)} rows')

# Check mappings
with open('mappings.json') as f:
    mappings = json.load(f)
print(f'Mappings: {len(mappings)} products')
print(f'Categories: {set(m.get(\"categoryId\", 3) for m in mappings)}')
"
```

## Common Issues & Solutions

### Issue 1: Price fetching fails for non-Pokemon products
**Cause:** categoryId not properly read from mappings  
**Solution:** Check that mappings.json has correct categoryId for the product

### Issue 2: Historical prices folder structure incorrect
**Cause:** Different categoryIds create different folder paths  
**Solution:** Folder structure is `historical_prices/{categoryId}/{group_id}/{product_id}/`

### Issue 3: Old data shows wrong categoryId
**Cause:** CSV files have categoryId column but it wasn't updated  
**Solution:** Either remove the column or update values using mappings.json as source of truth

## Important Notes

- **mappings.json is the source of truth** for categoryId
- CSV categoryId columns are optional and for reference only
- The system is backward compatible - old data without categoryId columns will still work
- Historical price data folders will be organized by categoryId going forward
- All Pokemon products should keep categoryId = 3

## Support

If you encounter issues:
1. Check the backup directory is intact: `backup_20260204_154658/`
2. Review this migration guide
3. Test with the rollback procedure
4. Check logs in the terminal where apps are running
