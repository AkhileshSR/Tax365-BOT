"""Purpose: Regression-test Tax365 routing and reporting fixes against supplied synthetic CSVs.
Sample input: CSV folder path.
Output: PASS/FAIL assertions and report excerpts.
Dependencies: Python standard library only.
Architecture: CSV -> SQLite test database -> query_router -> tax_service.
"""
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else (Path('..') / 'data').resolve()
sys.path.insert(0, str(ROOT))
from app.query_router import route_question

TABLE_FILES = {
    'legal_entities': '01_legal_entity_master.csv',
    'tax_compliance': '02_tax_compliance_register.csv',
    'tax_audits': '03_tax_audits_litigation_register.csv',
    'compliance_artifacts': '04_compliance_artifact_index.csv',
    'country_master': '05_country_implementation_master.csv',
    'region_master': '06_region_reference.csv',
    'audit_stage_reference': '07_audit_stage_reference.csv',
    'audit_phase_reference': '08_audit_phase_reference.csv',
}

def load_csv(conn, table, path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        quoted = ', '.join('"' + c.replace('"', '""') + '" TEXT' for c in columns)
        conn.execute(f'CREATE TABLE "{table}" ({quoted})')
        insert = f'INSERT INTO "{table}" VALUES ({", ".join("?" for _ in columns)})'
        conn.executemany(insert, ([row.get(c) for c in columns] for row in reader))

conn = sqlite3.connect(':memory:')
conn.row_factory = sqlite3.Row
for table, filename in TABLE_FILES.items():
    load_csv(conn, table, DATA / filename)

cases = [
    ('overdue all records', 'List all overdue tax filings globally. Show country, legal entity name, legal entity ID, tax type, due date, and filing status.'),
    ('India audit intent precedence', 'Show all tax audits and litigations in India, including case reference, tax authority, legal entity, disputed amount, audit stage, current phase, and next action if recorded.'),
    ('threshold count and limit', 'Identify all tax audit and litigation cases with financial exposure above USD 1 million. Rank them by exposure and show country, entity, and current stage.'),
    ('stage reference transparency', 'Explain all five tax audit and litigation stages configured in Tax365. Give the exact stage names and descriptions.'),
]
answers = {}
for name, question in cases:
    answer = route_question(conn, question)
    if answer is None:
        raise AssertionError(f'{name}: router returned None')
    answers[name] = answer

# Assertions grounded in the supplied CSV pack.
overdue_count = conn.execute("SELECT COUNT(*) FROM tax_compliance WHERE filing_status='Overdue'").fetchone()[0]
assert f'Total overdue records: {overdue_count:,}' in answers['overdue all records']
assert f'Records displayed: {overdue_count:,} of {overdue_count:,}' in answers['overdue all records']
assert answers['overdue all records'].count('Filing status: Overdue') == overdue_count
assert 'TAX AUDITS & LITIGATIONS — India' in answers['India audit intent precedence']
assert 'LEGAL ENTITY REGISTER — India' not in answers['India audit intent precedence']
assert 'TAX AUDIT / LITIGATION CASES ABOVE' in answers['threshold count and limit']
match_count = conn.execute("SELECT COUNT(*) FROM tax_audits WHERE CAST(COALESCE(financial_risk_amount_usd,0) AS REAL)>1000000").fetchone()[0]
assert f'Total matching cases: {match_count:,}' in answers['threshold count and limit']
assert 'Records displayed: 10 of ' in answers['threshold count and limit']
assert 'Description: Not separately recorded in the supplied reference data.' in answers['stage reference transparency']
assert answers['stage reference transparency'].count('Stage ') == 5

print('PASS: all overdue filings returned:', overdue_count)
print('PASS: India audit intent correctly routed; cases:', conn.execute("SELECT COUNT(*) FROM tax_audits WHERE country='India'").fetchone()[0])
print('PASS: threshold matching cases:', match_count, '| top 10 display disclosed')
print('PASS: five stage names returned; missing descriptions explicitly disclosed')
print('\n--- OVERDUE HEADER ---')
print('\n'.join(answers['overdue all records'].splitlines()[:5]))
print('\n--- INDIA AUDIT HEADER ---')
print('\n'.join(answers['India audit intent precedence'].splitlines()[:8]))
print('\n--- THRESHOLD HEADER ---')
print('\n'.join(answers['threshold count and limit'].splitlines()[:5]))
print('\n--- STAGE REFERENCE ---')
print(answers['stage reference transparency'])
