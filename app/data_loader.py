"""
Purpose: Load the eight supplied CSV files into SQLite without changing source files.
Sample input: DATA_DIR containing the eight named CSV files.
Output: Eight SQLite tables populated from the CSV source files.
Dependencies: csv, sqlite3, pathlib, database.py.
Architecture: Existing CSVs -> data_loader -> SQLite -> tax_service.
"""

import csv
import sqlite3
from pathlib import Path
from .database import TABLES

def import_csv_directory(connection: sqlite3.Connection, data_dir: Path) -> dict[str, int]:
    """
    Import each configured CSV into its corresponding SQLite table.
    Input: SQLite connection and directory containing the eight CSVs.
    Output: Dictionary mapping table names to imported row counts.
    Notes: Replaces each imported table on each explicit import run.
    """
    counts = {}
    for table_name, filename in TABLES.items():
        csv_path = data_dir / filename
        if not csv_path.exists():
            raise FileNotFoundError(f"Required source CSV not found: {csv_path}")
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = reader.fieldnames
            if not columns:
                raise ValueError(f"CSV has no header row: {csv_path}")
            safe_columns = [f'"{column.replace(chr(34), "")}"' for column in columns]
            connection.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            connection.execute(
                f'CREATE TABLE "{table_name}" ({", ".join(col + " TEXT" for col in safe_columns)})'
            )
            placeholders = ",".join("?" for _ in columns)
            insert_sql = f'INSERT INTO "{table_name}" ({", ".join(safe_columns)}) VALUES ({placeholders})'
            count = 0
            for row in reader:
                connection.execute(insert_sql, [row.get(column, "") for column in columns])
                count += 1
            counts[table_name] = count
    connection.commit()
    return counts
