"""
Purpose: Basic smoke test for the source CSV data and SQLite importer.
Sample input: Run `python -m unittest discover -s tests`.
Output: Pass/fail checks for required CSVs and imported record counts.
Dependencies: Python standard library and app modules.
"""

import unittest
from app.config import load_settings
from app.database import connect_db, initialize_schema
from app.data_loader import import_csv_directory

class Tax365SmokeTests(unittest.TestCase):
    """Validate that the configured data source can be imported."""
    def test_import_expected_dataset(self):
        settings = load_settings()
        connection = connect_db(settings.database_path)
        try:
            initialize_schema(connection)
            counts = import_csv_directory(connection, settings.data_dir)
            self.assertEqual(counts["legal_entities"], 120)
            self.assertEqual(counts["tax_compliance"], 180)
            self.assertEqual(counts["tax_audits"], 120)
            self.assertEqual(counts["country_master"], 60)
        finally:
            connection.close()

if __name__ == "__main__":
    unittest.main()
