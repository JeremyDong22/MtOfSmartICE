#!/usr/bin/env python3
"""
Add missing store mapping to Supabase master_restaurant table
"""
import os
from supabase import create_client

# Supabase credentials
SUPABASE_URL = "https://wdpeoyugsxqnpwwtkqsl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkcGVveXVnc3hxbnB3d3RrcXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNDgwNzgsImV4cCI6MjA1OTcyNDA3OH0.9bUpuZCOZxDSH3KsIu6FwWZyAvnV5xPJGNpO3luxWOE"

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# First, check existing stores to see the schema and brand_id
print("Checking existing stores to understand schema...")
sample = supabase.table("master_restaurant").select("*").limit(5).execute()
if sample.data:
    print(f"Sample store columns: {list(sample.data[0].keys())}")
    print(f"\nExisting stores:")
    for store in sample.data:
        print(f"  - {store['restaurant_name']}: brand_id={store['brand_id']}, org_code={store.get('meituan_org_code')}")

# Check if the store already exists
print("\nChecking for existing store with org_code MD00013...")
result = supabase.table("master_restaurant").select("*").eq("meituan_org_code", "MD00013").execute()

if result.data:
    print(f"Store already exists: {result.data[0]}")
else:
    print("Store not found. Adding new mapping...")

    # Get brand_id from an existing 宁桂杏 store
    existing_ningguixing = supabase.table("master_restaurant").select("brand_id").ilike("restaurant_name", "%宁桂杏%").limit(1).execute()

    if existing_ningguixing.data:
        brand_id = existing_ningguixing.data[0]['brand_id']
        print(f"Using brand_id from existing 宁桂杏 store: {brand_id}")
    else:
        print("ERROR: Could not find existing 宁桂杏 store to get brand_id")
        exit(1)

    # Add the missing store
    new_store = {
        "restaurant_name": "宁桂杏山野烤肉（常熟四丈湾店）",
        "meituan_org_code": "MD00013",
        "brand_id": brand_id,
        "city": "常熟"
    }

    result = supabase.table("master_restaurant").insert(new_store).execute()
    print(f"\nSuccessfully added store: {result.data[0]['restaurant_name']}")
    print(f"Restaurant ID: {result.data[0]['id']}")
    print(f"Meituan Org Code: {result.data[0]['meituan_org_code']}")
