#!/usr/bin/env python3
"""
Migrate historical_prices folder structure from old to new format.

OLD: historical_prices/{group_id}/{product_id}/{date}.json
NEW: historical_prices/{categoryId}/{group_id}/{product_id}/{date}.json

This script:
1. Reads categoryId from mappings.json for each product
2. Creates new folder structure with categoryId
3. Copies files to new locations
4. Optionally removes old structure after verification
"""

import os
import shutil
import json
from pathlib import Path


def migrate_historical_prices(dry_run=True):
    """
    Migrate historical price files to new structure with categoryId.
    
    Args:
        dry_run: If True, only print what would be done without making changes
    """
    print("=" * 60)
    print("Historical Prices Migration to Multi-TCG Structure")
    print("=" * 60)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No files will be moved\n")
    else:
        print("⚠️  LIVE MODE - Files will be moved!\n")
    
    # Load mappings to get categoryId for each product
    mappings_file = "mappings.json"
    if not os.path.exists(mappings_file):
        print(f"❌ Error: {mappings_file} not found!")
        return False
    
    with open(mappings_file, 'r') as f:
        mappings = json.load(f)
    
    # Create lookup: (group_id, product_id) -> categoryId
    category_lookup = {}
    for item in mappings:
        g_id = str(item.get('group_id', ''))
        p_id = str(item.get('product_id', ''))
        c_id = str(item.get('categoryId', 3))  # Default to 3 (Pokemon)
        category_lookup[(g_id, p_id)] = c_id
    
    print(f"📊 Loaded {len(category_lookup)} product mappings\n")
    
    # Scan old structure
    old_base = Path("historical_prices")
    if not old_base.exists():
        print("❌ Error: historical_prices folder not found!")
        return False
    
    files_to_migrate = []
    unknown_products = []
    
    # Walk through old structure: historical_prices/{group_id}/{product_id}/*.json
    for group_dir in old_base.iterdir():
        if not group_dir.is_dir():
            continue
        
        group_id = group_dir.name
        
        # Skip if this is already the new structure (has numeric category folders)
        # New structure has categoryId as first level
        if len(group_id) <= 2 and group_id.isdigit():
            print(f"⏭️  Skipping directory '{group_id}' - appears to be new structure")
            continue
        
        for product_dir in group_dir.iterdir():
            if not product_dir.is_dir():
                continue
            
            product_id = product_dir.name
            key = (group_id, product_id)
            
            if key not in category_lookup:
                unknown_products.append(key)
                continue
            
            category_id = category_lookup[key]
            
            # Find all JSON files for this product
            for json_file in product_dir.glob("*.json"):
                old_path = json_file
                new_path = old_base / category_id / group_id / product_id / json_file.name
                files_to_migrate.append((old_path, new_path, category_id))
    
    print(f"📦 Found {len(files_to_migrate)} files to migrate")
    
    if unknown_products:
        print(f"⚠️  Warning: {len(unknown_products)} products not in mappings:")
        for g_id, p_id in unknown_products[:10]:  # Show first 10
            print(f"   - group_id: {g_id}, product_id: {p_id}")
        if len(unknown_products) > 10:
            print(f"   ... and {len(unknown_products) - 10} more")
        print()
    
    if not files_to_migrate:
        print("✅ No files to migrate - structure may already be updated")
        return True
    
    # Group by category for summary
    by_category = {}
    for _, _, cat_id in files_to_migrate:
        by_category[cat_id] = by_category.get(cat_id, 0) + 1
    
    print("📊 Files by category:")
    for cat_id, count in sorted(by_category.items()):
        category_names = {
            '1': 'Magic: The Gathering',
            '2': 'Yu-Gi-Oh!',
            '3': 'Pokemon TCG',
            '4': 'Other'
        }
        name = category_names.get(cat_id, f'Category {cat_id}')
        print(f"   - {name} (ID {cat_id}): {count} files")
    print()
    
    if dry_run:
        print("🔍 Sample migration (first 5 files):")
        for old_path, new_path, _ in files_to_migrate[:5]:
            print(f"   {old_path}")
            print(f"   → {new_path}\n")
        
        print(f"ℹ️  Run with dry_run=False to perform the migration")
        return True
    
    # Actually migrate files
    print("🚀 Starting migration...")
    migrated = 0
    errors = []
    
    for old_path, new_path, category_id in files_to_migrate:
        try:
            # Create new directory structure
            new_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file to new location
            shutil.copy2(old_path, new_path)
            migrated += 1
            
            if migrated % 100 == 0:
                print(f"   Migrated {migrated}/{len(files_to_migrate)} files...")
        
        except Exception as e:
            errors.append((old_path, str(e)))
    
    print(f"\n✅ Migration complete: {migrated}/{len(files_to_migrate)} files migrated")
    
    if errors:
        print(f"\n❌ {len(errors)} errors occurred:")
        for path, error in errors[:10]:
            print(f"   {path}: {error}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more")
        return False
    
    print("\n⚠️  Old files still exist. Verify the migration before removing:")
    print("   1. Test that price lookups work correctly")
    print("   2. Run: python3 migrate_historical_prices.py --cleanup")
    
    return True


def cleanup_old_structure():
    """
    Remove old structure folders after successful migration.
    ONLY run this after verifying the migration!
    """
    print("=" * 60)
    print("Cleaning up old structure")
    print("=" * 60)
    
    old_base = Path("historical_prices")
    removed_count = 0
    
    for group_dir in old_base.iterdir():
        if not group_dir.is_dir():
            continue
        
        group_id = group_dir.name
        
        # Only remove if NOT a category ID folder (old structure)
        # Category IDs are typically 1-4, group IDs are much larger
        if len(group_id) > 2:
            print(f"🗑️  Removing old structure: {group_dir}")
            shutil.rmtree(group_dir)
            removed_count += 1
    
    print(f"\n✅ Removed {removed_count} old directories")


if __name__ == "__main__":
    import sys
    
    if "--cleanup" in sys.argv:
        response = input("⚠️  Are you sure you want to remove old structure? (yes/no): ")
        if response.lower() == "yes":
            cleanup_old_structure()
        else:
            print("Cleanup cancelled")
    elif "--live" in sys.argv:
        response = input("⚠️  Are you sure you want to migrate files? (yes/no): ")
        if response.lower() == "yes":
            migrate_historical_prices(dry_run=False)
        else:
            print("Migration cancelled")
    else:
        # Default: dry run
        migrate_historical_prices(dry_run=True)
