"""Utilities for loading SQLite data from the raw data directory."""

import sqlite3
from pathlib import Path

import pandas as pd

from src.config import DEFAULT_SQLITE_DB


def get_connection(db_path: str | Path = DEFAULT_SQLITE_DB) -> sqlite3.Connection:
    """Open a SQLite connection to a database file."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def list_tables(db_path: str | Path = DEFAULT_SQLITE_DB) -> list[str]:
    """Return the list of tables in a SQLite database."""
    with get_connection(db_path) as conn:
        query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        rows = conn.execute(query).fetchall()
        return [row["name"] for row in rows]


def read_table(table_name: str, db_path: str | Path = DEFAULT_SQLITE_DB) -> pd.DataFrame:
    """Read a SQLite table into a pandas DataFrame."""
    with get_connection(db_path) as conn:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
