"""
Purpose: SQLite schema, database connections and basic record counts.
Sample input: Database path from config.py.
Output: Initialized SQLite database with normalized source tables.
Dependencies: sqlite3, pathlib.
Architecture: CSV importer writes to SQLite; tax_service reads only from SQLite.
"""

import sqlite3
from pathlib import Path

TABLES = {
    "legal_entities": "01_legal_entity_master.csv",
    "tax_compliance": "02_tax_compliance_register.csv",
    "tax_audits": "03_tax_audits_litigation_register.csv",
    "compliance_artifacts": "04_compliance_artifact_index.csv",
    "country_master": "05_country_implementation_master.csv",
    "region_master": "06_region_reference.csv",
    "audit_stage_reference": "07_audit_stage_reference.csv",
    "audit_phase_reference": "08_audit_phase_reference.csv",
}

def connect_db(database_path: Path) -> sqlite3.Connection:
    """
    Open SQLite with row dictionaries and safe connection settings.
    Input: database_path.
    Output: sqlite3.Connection configured with sqlite3.Row.
    """
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def initialize_schema(connection: sqlite3.Connection) -> None:
    """
    Create application support tables.
    Input: Open SQLite connection.
    Output: users and audit_logs tables.
    """
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_user_id INTEGER PRIMARY KEY,
        display_name TEXT,
        role TEXT NOT NULL DEFAULT 'DEMO_EXECUTIVE',
        region_scope TEXT NOT NULL DEFAULT 'ALL',
        country_scope TEXT NOT NULL DEFAULT 'ALL',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_user_id INTEGER,
        event_type TEXT NOT NULL,
        query_text TEXT,
        result_summary TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    connection.commit()

def log_event(connection: sqlite3.Connection, user_id: int, event_type: str,
              query_text: str = "", result_summary: str = "") -> None:
    """Persist a user query or action for later audit review."""
    connection.execute(
        "INSERT INTO audit_logs (telegram_user_id,event_type,query_text,result_summary) VALUES (?,?,?,?)",
        (user_id, event_type, query_text[:2000], result_summary[:2000]),
    )
    connection.commit()
