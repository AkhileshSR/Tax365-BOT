"""
Purpose: Verify artifact metadata and physical PDF presence before Telegram delivery.
Sample input: Country and tax keyword, or an indexed filename.
Output: Existing local PDF path, or None. Never fabricates a file.
Dependencies: pathlib, sqlite3.
Architecture: compliance lookup -> artifact index -> physical file check -> Telegram send_document.
Security: Call only after the requesting user's country/region permissions are checked.
"""

import sqlite3
from pathlib import Path

def find_local_artifact(connection: sqlite3.Connection, artifacts_dir: Path,
                        country: str, tax_keyword: str = "") -> tuple[str, Path] | None:
    """
    Find a matching indexed artifact and verify its local binary exists.
    Input: DB connection, local artifact root, country and optional tax keyword.
    Output: (filename, verified_path) or None if metadata/binary is unavailable.
    """
    sql = """SELECT artifact_filename FROM compliance_artifacts
             WHERE LOWER(country) = LOWER(?) AND artifact_filename <> ''"""
    params: tuple = (country,)
    if tax_keyword:
        sql += " AND LOWER(artifact_filename) LIKE ?"
        params += (f"%{tax_keyword.lower()}%",)
    sql += " ORDER BY artifact_filename LIMIT 1"
    row = connection.execute(sql, params).fetchone()
    if not row:
        return None
    filename = row["artifact_filename"]
    # Match only the basename under the configured local repository; reject path traversal.
    safe_name = Path(filename).name
    if safe_name != filename:
        return None
    for candidate in artifacts_dir.rglob(safe_name):
        if candidate.is_file() and candidate.suffix.lower() == ".pdf":
            return filename, candidate.resolve()
    return None
