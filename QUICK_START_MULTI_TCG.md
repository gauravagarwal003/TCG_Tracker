# Quick Reference: Multi-TCG Support

## ✅ Migration Complete

Your Pokemon TCG Tracker now supports multiple TCG products!

## Category IDs
- **1** = Magic: The Gathering
- **2** = Yu-Gi-Oh!
- **3** = Pokemon TCG (default)
- **4** = Other TCG products

## What Changed?
✅ Historical prices folder now organized by categoryId: `historical_prices/{categoryId}/{group_id}/{product_id}/`  
✅ All 19,004 Pokemon price files migrated successfully  
✅ Price lookup functions updated to use categoryId  
✅ Backup created: `backup_20260204_154658/`  

## How to Add Non-Pokemon Products

### Via Web Form
1. Open the transaction form
2. Search for product (or enter manually if not found)
3. If entering manually, select the correct Category ID
4. Complete the transaction

The system will automatically:
- Store the categoryId in mappings.json
- Fetch prices from the correct TCG category
- Organize price history by categoryId

## Rollback (if needed)
```bash
# Restore all data files
cp backup_20260204_154658/* .
```

See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for detailed instructions.

## Verify Everything Works
All existing Pokemon data continues to work normally. The system defaults to categoryId 3 (Pokemon) for any product without an explicit categoryId.

## Documentation
- **MIGRATION_GUIDE.md** - Detailed migration and rollback instructions
- **MULTI_TCG_SUMMARY.md** - Complete technical summary of changes
- **README.md** - General project documentation

## Support
All changes are **fully reversible**. Your data is backed up in `backup_20260204_154658/`.
