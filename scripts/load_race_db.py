#!/usr/bin/env python3
"""Example script to inspect a SQLite database in the raw data directory."""

from src.config import DEFAULT_SQLITE_DB
from src.data_loader import list_tables


def main() -> None:
    db_path = DEFAULT_SQLITE_DB
    print(f"Database path: {db_path}")
    tables = list_tables(db_path)
    if not tables:
        print("No tables found. Place the SQLite database at data/raw/race.db first.")
        return
    print("Tables:")
    for table in tables:
        print(f"- {table}")


if __name__ == "__main__":
    main()
