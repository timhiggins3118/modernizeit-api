#!/usr/bin/env python3
"""
Reset Databases Script

Clears all data from MongoDB and SQLite for clean testing.
Run from project root: python scripts/reset_databases.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def reset_mongodb():
    """Clear all collections in MongoDB."""
    from pymongo import MongoClient
    from config.settings import settings

    print(f"\n[MongoDB] Connecting to {settings.mongodb_uri}...")
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    # Get all collections
    collections = db.list_collection_names()

    if not collections:
        print("[MongoDB] No collections found - already clean")
        return

    print(f"[MongoDB] Found {len(collections)} collections:")
    for coll_name in collections:
        count = db[coll_name].count_documents({})
        print(f"  - {coll_name}: {count} documents")

    # Confirm deletion
    response = input("\n[MongoDB] Delete all documents? (yes/no): ")
    if response.lower() != "yes":
        print("[MongoDB] Skipped")
        return

    # Delete all documents from each collection
    total_deleted = 0
    for coll_name in collections:
        result = db[coll_name].delete_many({})
        total_deleted += result.deleted_count
        print(f"  - Deleted {result.deleted_count} from {coll_name}")

    print(f"[MongoDB] Total deleted: {total_deleted} documents")
    client.close()


def reset_sqlite():
    """Clear all jobs from SQLite."""
    from db.jobs import _get_db_path
    import sqlite3

    db_path = _get_db_path()
    print(f"\n[SQLite] Database: {db_path}")

    if not db_path.exists():
        print("[SQLite] Database file not found - already clean")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get table info
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        print("[SQLite] No tables found")
        conn.close()
        return

    print(f"[SQLite] Found {len(tables)} tables:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  - {table}: {count} rows")

    # Confirm deletion
    response = input("\n[SQLite] Delete all rows? (yes/no): ")
    if response.lower() != "yes":
        print("[SQLite] Skipped")
        conn.close()
        return

    # Delete all rows from each table
    total_deleted = 0
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        cursor.execute(f"DELETE FROM {table}")
        total_deleted += count
        print(f"  - Deleted {count} from {table}")

    conn.commit()
    conn.close()
    print(f"[SQLite] Total deleted: {total_deleted} rows")


def reset_all_no_confirm():
    """Reset everything without confirmation (for automation)."""
    from pymongo import MongoClient
    from config.settings import settings
    from db.jobs import _get_db_path
    import sqlite3

    # MongoDB
    print("\n[MongoDB] Resetting...")
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]
    collections = db.list_collection_names()
    total_mongo = 0
    for coll_name in collections:
        result = db[coll_name].delete_many({})
        total_mongo += result.deleted_count
    print(f"[MongoDB] Deleted {total_mongo} documents from {len(collections)} collections")
    client.close()

    # SQLite
    print("\n[SQLite] Resetting...")
    db_path = _get_db_path()
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        total_sqlite = 0
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            cursor.execute(f"DELETE FROM {table}")
            total_sqlite += count
        conn.commit()
        conn.close()
        print(f"[SQLite] Deleted {total_sqlite} rows from {len(tables)} tables")
    else:
        print("[SQLite] No database file found")

    print("\nDone!")


if __name__ == "__main__":
    print("=" * 50)
    print("  Database Reset Script")
    print("=" * 50)

    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        # No confirmation mode
        reset_all_no_confirm()
    else:
        # Interactive mode
        reset_mongodb()
        reset_sqlite()
        print("\nDone!")
