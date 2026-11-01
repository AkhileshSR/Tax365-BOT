from pathlib import Path
import sqlite3, sys
import pandas as pd

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('../data')
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from app import tax_service, query_router

files = {
    'legal_entities': '01_legal_entity_master.csv',
    'tax_compliance': '02_tax_compliance_register.csv',
    'tax_audits': '03_tax_audits_litigation_register.csv',
    'region_master': '06_region_reference.csv',
    'audit_phase_reference': '08_audit_phase_reference.csv',
    'audit_stage_reference': '07_audit_stage_reference.csv',
    'country_master': '05_country_implementation_master.csv',
    'compliance_artifacts': '04_compliance_artifact_index.csv',
}
con = sqlite3.connect(':memory:')
con.row_factory = sqlite3.Row
for table, filename in files.items():
    frame = pd.read_csv(DATA / filename)
    frame = frame.astype(object).where(pd.notna(frame), None)
    frame.to_sql(table, con, index=False, if_exists='replace')

question = ('Generate a very short executive summary to publish for Total Count & Exposure '
            'of Tax Audit & Disputes by regions, Total Count & Exposure of tax compliances '
            'by region and also total number of Active Legal entities as of today, by region')
result = query_router.route_question(con, question)
assert result and 'TAX365 REGIONAL EXECUTIVE SNAPSHOT' in result, result
for name in ['Europe, Middle East, and Africa', 'North America', 'North Asia',
             'North Latin America', 'South Latin America', 'South & Southeast Asia']:
    assert name in result, f'Missing region: {name}'
assert 'Global: 120 cases | USD 359,506,460' in result, result
assert 'Global: 180 filings' in result, result
assert 'Global: 120 active of 120 registered entities' in result, result
assert 'local currencies are not consolidated' in result, result
assert 'Latest entity verification date in source: 2026-10-15' in result, result
assert 'TAX AUDIT LIFECYCLE PHASES' not in result
# Confirm the earlier audit-phase route remains intact.
phase = query_router.route_question(con, 'Show all seven audit phases in sequence, including their exact names.')
assert phase.startswith('TAX AUDIT LIFECYCLE PHASES') and '7. Phase 7: Appeal Evaluation' in phase, phase
print(result)
print('PASS: regional executive report routing and source totals validated.')
print('PASS: existing seven-phase routing preserved.')

# Guard against hijacking existing regional-compliance report requests.
regional_compliance = query_router.route_question(con, 'Show regional tax compliance summary by region.')
assert regional_compliance.startswith('REGIONAL TAX COMPLIANCE SUMMARY'), regional_compliance
print('PASS: existing regional-compliance report routing preserved.')

# Regression checks for the previously fixed critical reports.
overdue = query_router.route_question(con, 'List all overdue tax filings globally.')
assert 'Total overdue records: 60' in overdue and 'Records displayed: 60 of 60' in overdue
print('PASS: all 60 overdue filings returned.')

india_audits = query_router.route_question(con, 'Show all tax audits and litigations in India, including case reference and legal entity.')
assert 'TAX AUDITS & LITIGATIONS — India' in india_audits and 'Case records: 2' in india_audits
print('PASS: India audit routing returns two cases.')

high_exposure = query_router.route_question(con, 'Identify all tax audit and litigation cases with financial exposure above USD 1 million.')
assert 'Total matching cases: 103' in high_exposure and 'Records displayed: 10 of 103' in high_exposure
print('PASS: high-exposure count and display disclosure preserved.')

stages = query_router.route_question(con, 'Show all five audit stages and their descriptions.')
assert stages.startswith('TAX AUDIT & LITIGATION STAGES') and 'Not separately recorded' in stages
print('PASS: audit-stage reference routing preserved.')
