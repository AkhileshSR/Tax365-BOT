"""
Purpose: Deterministic, auditable tax intelligence queries over the SQLite registry.
Sample input: Country, region, tax type, exposure threshold or reporting request.
Output: Executive-ready text generated exclusively from registry records.
Dependencies: Python standard library (sqlite3, re).
Architecture: Telegram -> query_router -> tax_service -> SQLite -> response_formatter.
"""

import sqlite3
from typing import Iterable

NOT_FOUND = "Data not found in the tracking registry."
STATUS_ORDER = ("Filed & Approved", "Pending Local Review", "Overdue")


def _rows(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Execute a parameterized SELECT and return all matching rows.

    Args:
        connection: Open SQLite connection.
        sql: Read-only SQL statement with placeholders.
        params: Bound SQL parameters.
    Returns:
        Matching rows as sqlite3.Row objects.
    """
    return connection.execute(sql, params).fetchall()


def _count(connection: sqlite3.Connection, table: str) -> int:
    """Return row count for a fixed internal table name."""
    allowed = {"legal_entities", "country_master", "tax_compliance", "tax_audits"}
    if table not in allowed:
        raise ValueError("Unsupported registry table.")
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _money(value, currency: str = "USD") -> str:
    """Format a numeric amount without changing its currency denomination."""
    if value is None or value == "":
        return "Not recorded"
    return f"{float(value):,.2f} {currency}"


def _status_counts(connection: sqlite3.Connection, where_sql: str = "", params: tuple = ()) -> dict:
    """Return filing counts by the three controlled status categories."""
    sql = "SELECT filing_status, COUNT(*) AS n FROM tax_compliance"
    if where_sql:
        sql += " WHERE " + where_sql
    sql += " GROUP BY filing_status"
    rows = _rows(connection, sql, params)
    return {row["filing_status"]: int(row["n"]) for row in rows}


def _status_lines(counts: dict, total: int) -> list[str]:
    """Format controlled status counts and percentages in a stable order."""
    lines = []
    for status in STATUS_ORDER:
        count = counts.get(status, 0)
        pct = (count / total * 100.0) if total else 0.0
        lines.append(f"{status}: {count:,} ({pct:.1f}%)")
    return lines


def global_summary(connection: sqlite3.Connection) -> str:
    """Summarize entity, country, filing and audit records with status percentages."""
    entities = _count(connection, "legal_entities")
    countries = _count(connection, "country_master")
    filings = _count(connection, "tax_compliance")
    audits = _count(connection, "tax_audits")
    counts = _status_counts(connection)
    lines = [
        "GLOBAL TAX COMPLIANCE SUMMARY",
        f"Countries in implementation master: {countries:,}",
        f"Legal entity records: {entities:,}",
        f"Tax compliance records: {filings:,}",
        f"Tax audit / litigation records: {audits:,}",
        "",
        "FILING STATUS BREAKDOWN",
        *_status_lines(counts, filings),
        "Note: Percentages are calculated against all tax compliance records."
    ]
    return "\n".join(lines)


def regional_compliance_summary(connection: sqlite3.Connection) -> str:
    """Aggregate filing counts and controlled statuses by regional_org."""
    rows = _rows(connection, """
        SELECT regional_org, COUNT(*) AS total,
               SUM(CASE WHEN filing_status = 'Filed & Approved' THEN 1 ELSE 0 END) AS approved,
               SUM(CASE WHEN filing_status = 'Pending Local Review' THEN 1 ELSE 0 END) AS pending,
               SUM(CASE WHEN filing_status = 'Overdue' THEN 1 ELSE 0 END) AS overdue
        FROM tax_compliance
        GROUP BY regional_org
        ORDER BY regional_org
    """)
    if not rows:
        return NOT_FOUND
    lines = ["REGIONAL TAX COMPLIANCE SUMMARY"]
    grand_total = grand_approved = grand_pending = grand_overdue = 0
    for row in rows:
        total = int(row["total"])
        approved, pending, overdue = int(row["approved"] or 0), int(row["pending"] or 0), int(row["overdue"] or 0)
        grand_total += total
        grand_approved += approved
        grand_pending += pending
        grand_overdue += overdue
        lines.extend([
            "",
            f"{row['regional_org'] or 'Unassigned'}",
            f"Total filings: {total:,}",
            f"Filed & Approved: {approved:,} ({approved / total * 100:.1f}%)",
            f"Pending Local Review: {pending:,} ({pending / total * 100:.1f}%)",
            f"Overdue: {overdue:,} ({overdue / total * 100:.1f}%)"
        ])
    lines.extend([
        "",
        "GLOBAL TOTAL",
        f"Total filings: {grand_total:,}",
        f"Filed & Approved: {grand_approved:,}",
        f"Pending Local Review: {grand_pending:,}",
        f"Overdue: {grand_overdue:,}"
    ])
    return "\n".join(lines)


def country_compliance_comparison(connection: sqlite3.Connection, countries: Iterable[str]) -> str:
    """Compare compliance statuses for multiple requested countries in one result."""
    countries = list(dict.fromkeys(countries))
    if not countries:
        return NOT_FOUND
    placeholders = ",".join("?" for _ in countries)
    rows = _rows(connection, f"""
        SELECT country, COUNT(*) AS total,
               SUM(CASE WHEN filing_status = 'Filed & Approved' THEN 1 ELSE 0 END) AS approved,
               SUM(CASE WHEN filing_status = 'Pending Local Review' THEN 1 ELSE 0 END) AS pending,
               SUM(CASE WHEN filing_status = 'Overdue' THEN 1 ELSE 0 END) AS overdue
        FROM tax_compliance
        WHERE LOWER(country) IN ({placeholders})
        GROUP BY country
    """, tuple(country.lower() for country in countries))
    by_country = {row["country"].lower(): row for row in rows}
    lines = ["COUNTRY TAX COMPLIANCE COMPARISON"]
    for country in countries:
        row = by_country.get(country.lower())
        if row is None:
            lines.extend(["", country, NOT_FOUND])
            continue
        total = int(row["total"])
        lines.extend([
            "",
            country,
            f"Total filings: {total:,}",
            f"Filed & Approved: {int(row['approved'] or 0):,}",
            f"Pending Local Review: {int(row['pending'] or 0):,}",
            f"Overdue: {int(row['overdue'] or 0):,}"
        ])
    return "\n".join(lines)


def global_cit_filings(connection: sqlite3.Connection) -> str:
    """List all Corporate Income Tax records grouped by country and filing status."""
    rows = _rows(connection, """
        SELECT country, filing_status, COUNT(*) AS n
        FROM tax_compliance
        WHERE UPPER(COALESCE(tax_code, '')) = 'CIT'
           OR LOWER(COALESCE(tax_type, '')) LIKE '%corporate income tax%'
        GROUP BY country, filing_status
        ORDER BY country, filing_status
    """)
    if not rows:
        return NOT_FOUND
    by_country = {}
    total = 0
    for row in rows:
        by_country.setdefault(row["country"], {})
        by_country[row["country"]][row["filing_status"]] = int(row["n"])
        total += int(row["n"])
    lines = [f"GLOBAL CORPORATE INCOME TAX FILINGS", f"Total CIT records: {total:,}"]
    for country, statuses in by_country.items():
        country_total = sum(statuses.values())
        lines.extend(["", f"{country} — {country_total:,} filing(s)"])
        for status in STATUS_ORDER:
            lines.append(f"  {status}: {statuses.get(status, 0):,}")
    return "\n".join(lines)


def overdue_filings(connection: sqlite3.Connection, limit: int | None = None) -> str:
    """Return the overdue filing register with an explicit total and completeness indicator.

    By default, return every overdue filing. If a caller supplies a limit, disclose
    both the total matching records and the number displayed.
    """
    total = int(connection.execute(
        "SELECT COUNT(*) FROM tax_compliance WHERE filing_status = ?", ("Overdue",)
    ).fetchone()[0])
    if total == 0:
        return NOT_FOUND

    sql = """
        SELECT c.country, c.legal_entity_id, e.legal_entity_name,
               c.tax_type, c.tax_period, c.statutory_due_date, c.filing_status
        FROM tax_compliance c
        LEFT JOIN legal_entities e ON e.legal_entity_id = c.legal_entity_id
        WHERE c.filing_status = ?
        ORDER BY c.statutory_due_date, c.country, c.legal_entity_id
    """
    params: tuple = ("Overdue",)
    if limit is not None:
        safe_limit = max(1, min(int(limit), 1000))
        sql += " LIMIT ?"
        params += (safe_limit,)
    rows = _rows(connection, sql, params)
    shown = len(rows)
    lines = [
        "OVERDUE TAX FILINGS",
        f"Total overdue records: {total:,}",
        f"Records displayed: {shown:,} of {total:,}",
        "" if shown == total else "NOTICE: This is a partial result; additional overdue records are not displayed.",
    ]
    for row in rows:
        lines.extend([
            "",
            f"{row['country']} | {row['tax_type']} | {row['tax_period']}",
            f"Legal entity: {row['legal_entity_name'] or row['legal_entity_id']}",
            f"Entity ID: {row['legal_entity_id']}",
            f"Due date: {row['statutory_due_date'] or 'Not recorded'}",
            f"Filing status: {row['filing_status']}"
        ])
    return "\n".join(line for line in lines if line is not None)


def high_exposure_audits(connection: sqlite3.Connection, threshold_usd: float = 1_000_000, limit: int = 10) -> str:
    """Count every case above a USD threshold and display the highest exposures.

    financial_risk_amount_usd is the source field used for the threshold and ranking.
    The response always distinguishes total matches from records displayed.
    """
    threshold = float(threshold_usd)
    total = int(connection.execute("""
        SELECT COUNT(*)
        FROM tax_audits
        WHERE CAST(COALESCE(financial_risk_amount_usd, 0) AS REAL) > ?
    """, (threshold,)).fetchone()[0])
    if total == 0:
        return f"No tax audit or litigation cases have financial exposure above {_money(threshold, 'USD')}."

    safe_limit = max(1, min(int(limit), 100))
    rows = _rows(connection, """
        SELECT a.country, a.legal_entity_id, e.legal_entity_name, a.tax_authority,
               a.dispute_type, a.current_stage, a.current_phase, a.case_id,
               a.financial_risk_amount_usd, a.case_status, a.next_action
        FROM tax_audits a
        LEFT JOIN legal_entities e ON e.legal_entity_id = a.legal_entity_id
        WHERE CAST(COALESCE(a.financial_risk_amount_usd, 0) AS REAL) > ?
        ORDER BY CAST(a.financial_risk_amount_usd AS REAL) DESC, a.case_id
        LIMIT ?
    """, (threshold, safe_limit))

    lines = [
        f"TAX AUDIT / LITIGATION CASES ABOVE {_money(threshold, 'USD')}",
        f"Total matching cases: {total:,}",
        f"Records displayed: {len(rows):,} of {total:,}",
    ]
    if len(rows) < total:
        lines.append("Showing the highest-exposure cases first; additional qualifying cases are not displayed.")
    for row in rows:
        lines.extend([
            "",
            f"{row['country']} | {row['dispute_type']} | {row['case_id']}",
            f"Legal entity: {row['legal_entity_name'] or row['legal_entity_id']}",
            f"Entity ID: {row['legal_entity_id'] or 'Not recorded'}",
            f"Tax authority: {row['tax_authority'] or 'Not recorded'}",
            f"Financial risk: {_money(row['financial_risk_amount_usd'], 'USD')}",
            f"Stage: {row['current_stage'] or 'Not recorded'}",
            f"Phase: {row['current_phase'] or 'Not recorded'}",
            f"Case status: {row['case_status'] or 'Not recorded'}",
            f"Next action: {row['next_action'] or 'Not recorded'}"
        ])
    return "\n".join(lines)


def global_audit_summary(connection: sqlite3.Connection) -> str:
    """Summarize audit case count and normalized USD exposure by region."""
    rows = _rows(connection, """
        SELECT regional_org, COUNT(*) AS cases,
               SUM(CAST(COALESCE(financial_risk_amount_usd, 0) AS REAL)) AS exposure
        FROM tax_audits
        GROUP BY regional_org
        ORDER BY regional_org
    """)
    if not rows:
        return NOT_FOUND
    total_cases = sum(int(row["cases"]) for row in rows)
    total_exposure = sum(float(row["exposure"] or 0) for row in rows)
    lines = [
        "GLOBAL TAX AUDIT & LITIGATION SUMMARY",
        f"Total cases: {total_cases:,}",
        f"Total financial risk exposure: {_money(total_exposure, 'USD')}",
        "",
        "EXPOSURE BY REGION"
    ]
    for row in rows:
        exposure = float(row["exposure"] or 0)
        pct = exposure / total_exposure * 100 if total_exposure else 0
        lines.append(f"{row['regional_org'] or 'Unassigned'}: {int(row['cases']):,} cases | {_money(exposure, 'USD')} ({pct:.1f}%)")
    return "\n".join(lines)


def top_audit_cases(connection: sqlite3.Connection, limit: int = 10) -> str:
    """Return exactly up to the requested number of highest-exposure audit cases."""
    rows = _rows(connection, """
        SELECT a.country, a.legal_entity_id, e.legal_entity_name, a.case_id,
               a.tax_authority, a.dispute_type, a.financial_risk_amount_usd,
               a.current_stage, a.current_phase, a.case_status, a.next_action
        FROM tax_audits a
        LEFT JOIN legal_entities e ON e.legal_entity_id = a.legal_entity_id
        ORDER BY CAST(COALESCE(a.financial_risk_amount_usd, 0) AS REAL) DESC
        LIMIT ?
    """, (max(1, min(int(limit), 100)),))
    if not rows:
        return NOT_FOUND
    lines = [f"TOP {len(rows)} TAX AUDIT / LITIGATION CASES BY USD EXPOSURE"]
    for index, row in enumerate(rows, 1):
        lines.extend([
            "",
            f"{index}. {row['country']} | {row['dispute_type']} | {row['case_id']}",
            f"Legal entity: {row['legal_entity_name'] or row['legal_entity_id']}",
            f"Entity ID: {row['legal_entity_id']}",
            f"Tax authority: {row['tax_authority'] or 'Not recorded'}",
            f"Financial risk: {_money(row['financial_risk_amount_usd'], 'USD')}",
            f"Stage: {row['current_stage']}",
            f"Phase: {row['current_phase']}",
            f"Case status: {row['case_status']}",
            f"Next action: {row['next_action'] or 'Not recorded'}"
        ])
    return "\n".join(lines)


def country_entity_profile(connection: sqlite3.Connection, country: str) -> str:
    """Retrieve legal entity registration, tax, director and parent details for a country."""
    rows = _rows(connection, """
        SELECT country, legal_entity_name, legal_entity_id, le_level, entity_status,
               local_company_registration_id, local_tax_id, vat_gst_registration_id,
               managing_director_1, managing_director_2, functional_currency,
               direct_parent_name, registered_address, last_verified_date
        FROM legal_entities
        WHERE LOWER(country) = LOWER(?)
        ORDER BY legal_entity_id
    """, (country,))
    if not rows:
        return NOT_FOUND
    lines = [f"LEGAL ENTITY REGISTER — {country}", f"Entity records: {len(rows):,}"]
    for row in rows:
        directors = ", ".join(x for x in (row["managing_director_1"], row["managing_director_2"]) if x) or "Not recorded"
        lines.extend([
            "",
            row["legal_entity_name"],
            f"Entity ID: {row['legal_entity_id']}",
            f"Entity level: {row['le_level']}",
            f"Entity status: {row['entity_status']}",
            f"Company registration ID: {row['local_company_registration_id'] or 'Not recorded'}",
            f"Tax ID: {row['local_tax_id'] or 'Not recorded'}",
            f"VAT/GST ID: {row['vat_gst_registration_id'] or 'Not recorded'}",
            f"Managing directors: {directors}",
            f"Functional currency: {row['functional_currency'] or 'Not recorded'}",
            f"Direct parent: {row['direct_parent_name'] or 'Not recorded'}",
            f"Registered address: {row['registered_address'] or 'Not recorded'}",
            f"Last verified: {row['last_verified_date'] or 'Not recorded'}"
        ])
    return "\n".join(lines)


def country_compliance(connection: sqlite3.Connection, country: str, tax_keyword: str = "") -> str:
    """Return all compliance details for a country, optionally filtered by tax code/type."""
    sql = """
        SELECT country, legal_entity_id, tax_type, tax_code, tax_period, statutory_due_date,
               filing_status, submission_date, approval_date, uploaded_by,
               proof_available, artifact_filename
        FROM tax_compliance WHERE LOWER(country) = LOWER(?)
    """
    params = (country,)
    if tax_keyword:
        sql += " AND (LOWER(tax_type) LIKE ? OR LOWER(tax_code) LIKE ?)"
        params += (f"%{tax_keyword.lower()}%", f"%{tax_keyword.lower()}%")
    sql += " ORDER BY statutory_due_date, tax_type"
    rows = _rows(connection, sql, params)
    if not rows:
        return NOT_FOUND
    lines = [f"TAX COMPLIANCE REGISTER — {country}", f"Filing records: {len(rows):,}"]
    for row in rows:
        lines.extend([
            "",
            f"{row['tax_type']} | {row['tax_period']}",
            f"Entity ID: {row['legal_entity_id']}",
            f"Filing status: {row['filing_status']}",
            f"Statutory due date: {row['statutory_due_date']}",
            f"Submission date: {row['submission_date'] or 'Not recorded'}",
            f"Approval date: {row['approval_date'] or 'Not recorded'}",
            f"Proof listed in compliance register: {row['proof_available'] or 'Not recorded'}",
            f"Artifact filename: {row['artifact_filename'] or 'Not recorded'}"
        ])
    return "\n".join(lines)


def country_audits(connection: sqlite3.Connection, country: str) -> str:
    """List country audit cases with authority, entity, exposure, stage, phase and next action."""
    rows = _rows(connection, """
        SELECT a.case_id, a.legal_entity_id, e.legal_entity_name, a.tax_authority,
               a.dispute_type, a.current_stage, a.current_phase, a.case_status,
               a.financial_risk_amount_usd, a.financial_risk_currency,
               a.next_action, a.next_hearing_or_milestone, a.response_due_date
        FROM tax_audits a
        LEFT JOIN legal_entities e ON e.legal_entity_id = a.legal_entity_id
        WHERE LOWER(a.country) = LOWER(?)
        ORDER BY CAST(COALESCE(a.financial_risk_amount_usd, 0) AS REAL) DESC
    """, (country,))
    if not rows:
        return NOT_FOUND
    lines = [f"TAX AUDITS & LITIGATIONS — {country}", f"Case records: {len(rows):,}"]
    for row in rows:
        lines.extend([
            "",
            f"{row['case_id']} | {row['dispute_type']}",
            f"Legal entity: {row['legal_entity_name'] or row['legal_entity_id']}",
            f"Entity ID: {row['legal_entity_id']}",
            f"Tax authority: {row['tax_authority'] or 'Not recorded'}",
            f"Financial risk: {_money(row['financial_risk_amount_usd'], row['financial_risk_currency'] or 'Not recorded')}",
            f"Audit stage: {row['current_stage']}",
            f"Current phase: {row['current_phase']}",
            f"Case status: {row['case_status']}",
            f"Response due date: {row['response_due_date'] or 'Not recorded'}",
            f"Next milestone: {row['next_hearing_or_milestone'] or 'Not recorded'}",
            f"Next action: {row['next_action'] or 'Not recorded'}"
        ])
    return "\n".join(lines)



def executive_summary(connection: sqlite3.Connection) -> str:
    """Build a concise regional executive snapshot from the three source registries.

    Audit exposure is summed from the USD-normalized source field. Compliance
    penalty exposure is shown by local currency because the source register has
    no normalized USD compliance exposure. Entity status is current registry
    status; the latest last_verified_date is disclosed as its verification watermark.
    """
    from datetime import date

    as_of = date.today().strftime("%d %B %Y")
    region_names = {
        row["regional_code"]: row["regional_name"]
        for row in _rows(connection, "SELECT regional_code, regional_name FROM region_master")
    }

    entity_rows = _rows(connection, """
        SELECT regional_org,
               COUNT(*) AS total_entities,
               SUM(CASE WHEN LOWER(TRIM(COALESCE(entity_status, '')))
                         IN ('active', 'active / good standing') THEN 1 ELSE 0 END) AS active_entities,
               MAX(last_verified_date) AS latest_verified
        FROM legal_entities
        GROUP BY regional_org
        ORDER BY regional_org
    """)

    compliance_rows = _rows(connection, """
        SELECT regional_org, currency,
               COUNT(*) AS filing_count,
               SUM(CAST(COALESCE(late_filing_penalty_local, 0) AS REAL)) AS penalty_exposure
        FROM tax_compliance
        GROUP BY regional_org, currency
        ORDER BY regional_org, currency
    """)
    compliance_by_region = {}
    for row in compliance_rows:
        compliance_by_region.setdefault(row["regional_org"], {"count": 0, "penalties": []})
        item = compliance_by_region[row["regional_org"]]
        item["count"] += int(row["filing_count"] or 0)
        penalty = float(row["penalty_exposure"] or 0)
        if penalty:
            item["penalties"].append((row["currency"] or "Currency not recorded", penalty))

    audit_rows = _rows(connection, """
        SELECT regional_org, COUNT(*) AS case_count,
               SUM(CAST(COALESCE(financial_risk_amount_usd, 0) AS REAL)) AS exposure_usd
        FROM tax_audits
        GROUP BY regional_org
        ORDER BY regional_org
    """)

    lines = [f"TAX365 REGIONAL EXECUTIVE SNAPSHOT — {as_of}", ""]
    lines.append("1. TAX AUDITS & DISPUTES — CASE COUNT AND RECORDED USD EXPOSURE")
    total_cases = 0
    total_audit_exposure = 0.0
    for row in audit_rows:
        code = row["regional_org"] or "Unassigned"
        name = region_names.get(code, code)
        count = int(row["case_count"] or 0)
        exposure = float(row["exposure_usd"] or 0)
        total_cases += count
        total_audit_exposure += exposure
        lines.append(f"{name}: {count:,} cases | USD {exposure:,.0f}")
    lines.append(f"Global: {total_cases:,} cases | USD {total_audit_exposure:,.0f}")

    lines.extend(["", "2. TAX COMPLIANCE — FILING COUNT AND LATE-FILING PENALTY EXPOSURE"])
    total_filings = 0
    for code in sorted(compliance_by_region):
        item = compliance_by_region[code]
        name = region_names.get(code, code)
        total_filings += item["count"]
        penalty_text = "; ".join(
            f"{currency} {amount:,.0f}" for currency, amount in item["penalties"]
        ) or "No penalty amount recorded"
        lines.append(f"{name}: {item['count']:,} filings | Penalties: {penalty_text}")
    lines.append(f"Global: {total_filings:,} filings")

    lines.extend(["", "3. ACTIVE LEGAL ENTITIES — CURRENT REGISTRY STATUS"])
    total_active = total_entities = 0
    verification_dates = []
    for row in entity_rows:
        code = row["regional_org"] or "Unassigned"
        name = region_names.get(code, code)
        active = int(row["active_entities"] or 0)
        total = int(row["total_entities"] or 0)
        total_active += active
        total_entities += total
        if row["latest_verified"]:
            verification_dates.append(str(row["latest_verified"]))
        lines.append(f"{name}: {active:,} active of {total:,}")
    latest_verified = max(verification_dates) if verification_dates else "Not recorded"
    lines.append(f"Global: {total_active:,} active of {total_entities:,} registered entities")
    lines.append(f"Latest entity verification date in source: {latest_verified}")

    lines.extend([
        "",
        "BASIS & LIMITATIONS",
        "Audit exposure uses financial_risk_amount_usd and includes all case statuses.",
        "Compliance exposure is late_filing_penalty_local, shown by currency; local currencies are not consolidated.",
        "Active counts reflect entity_status in the registry; the source has no status-effective date.",
        "DEMO ENVIRONMENT — Illustrative synthetic data; not actual client tax records."
    ])
    return "\n".join(lines)

def audit_stage_reference(connection: sqlite3.Connection) -> str:
    """Read stage names and only use descriptions if the source table contains them."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(audit_stage_reference)")}
    description_column = next((name for name in ("stage_description", "description") if name in columns), None)
    selected = "stage_order, stage_name" + (f", {description_column}" if description_column else "")
    rows = _rows(connection, f"SELECT {selected} FROM audit_stage_reference ORDER BY stage_order")
    if not rows:
        return NOT_FOUND
    lines = ["TAX AUDIT & LITIGATION STAGES"]
    for row in rows:
        lines.append(f"{int(row['stage_order'])}. {row['stage_name']}")
        if description_column and row[description_column]:
            lines.append(f"   Description: {row[description_column]}")
        else:
            lines.append("   Description: Not separately recorded in the supplied reference data.")
    return "\n".join(lines)


def audit_phase_reference(connection: sqlite3.Connection) -> str:
    """Read the seven configured audit lifecycle phases in source-defined order."""
    rows = _rows(connection, "SELECT phase_order, phase_name FROM audit_phase_reference ORDER BY phase_order")
    if not rows:
        return NOT_FOUND
    return "TAX AUDIT LIFECYCLE PHASES\n" + "\n".join(
        f"{int(row['phase_order'])}. {row['phase_name']}" for row in rows
    )


def country_artifact_lookup(connection: sqlite3.Connection, country: str, tax_keyword: str = "") -> str:
    """Return artifact index metadata and clearly state that no PDF binary is included."""
    sql = """
        SELECT country, legal_entity_id, filing_id, artifact_type, artifact_filename,
               document_format, document_status, document_date, repository_path,
               access_classification
        FROM compliance_artifacts
        WHERE LOWER(country) = LOWER(?)
    """
    params = (country,)
    if tax_keyword:
        sql += """ AND filing_id IN (
            SELECT filing_id FROM tax_compliance
            WHERE LOWER(country) = LOWER(?)
              AND (LOWER(tax_type) LIKE ? OR LOWER(tax_code) LIKE ?)
        )"""
        params += (country.lower(), f"%{tax_keyword.lower()}%", f"%{tax_keyword.lower()}%")
    sql += " ORDER BY document_date DESC"
    rows = _rows(connection, sql, params)
    if not rows:
        # Distinguish a filing with no indexed evidence from an unknown filing.
        compliance_sql = """
            SELECT country, legal_entity_id, filing_id, tax_type, tax_period,
                   filing_status, proof_available, artifact_filename
            FROM tax_compliance
            WHERE LOWER(country) = LOWER(?)
        """
        compliance_params = (country,)
        if tax_keyword:
            compliance_sql += " AND (LOWER(tax_type) LIKE ? OR LOWER(tax_code) LIKE ?)"
            compliance_params += (f"%{tax_keyword.lower()}%", f"%{tax_keyword.lower()}%")
        compliance_rows = _rows(connection, compliance_sql, compliance_params)
        if not compliance_rows:
            return NOT_FOUND
        lines = [f"COMPLIANCE EVIDENCE CHECK — {country}"]
        for item in compliance_rows:
            lines.extend([
                "",
                f"{item['tax_type']} | {item['tax_period']}",
                f"Entity ID: {item['legal_entity_id']}",
                f"Filing ID: {item['filing_id']}",
                f"Filing status: {item['filing_status']}",
                f"Proof available in compliance register: {item['proof_available'] or 'Not recorded'}",
                f"Artifact filename: {item['artifact_filename'] or 'Not recorded'}"
            ])
        lines.append("No matching artifact-index record was found; no PDF has been delivered.")
        return "\\n".join(lines)
    lines = [f"COMPLIANCE ARTIFACT INDEX — {country}", f"Indexed records: {len(rows):,}"]
    for row in rows:
        lines.extend([
            "",
            f"Filename: {row['artifact_filename'] or 'Not recorded'}",
            f"Filing ID: {row['filing_id']}",
            f"Artifact type: {row['artifact_type']}",
            f"Document status: {row['document_status']}",
            f"Document date: {row['document_date'] or 'Not recorded'}",
            f"Repository reference: {row['repository_path'] or 'Not recorded'}",
            f"Access classification: {row['access_classification'] or 'Not recorded'}"
        ])
    lines.extend([
        "",
        "DEMO LIMITATION: The supplied artifact index identifies metadata only. PDF binaries were not included in the demo dataset; no document has been delivered."
    ])
    return "\n".join(lines)
