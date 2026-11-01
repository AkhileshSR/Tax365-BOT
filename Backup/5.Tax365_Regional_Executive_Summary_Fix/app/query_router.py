"""
Purpose: Classify supported Tax365 intents before invoking deterministic registry services.
Sample input: "Compare tax compliance across India, Brazil and Germany."
Output: A registry-backed response, or None for non-registry conversational requests.
Dependencies: Python standard library (re, sqlite3), tax_service.py.
Architecture: Telegram -> intent classification -> tax_service -> SQLite.
"""

import re
import sqlite3
from . import tax_service

COUNTRIES = [
    "United Kingdom", "Germany", "France", "Netherlands", "Belgium", "Spain", "Italy", "Poland",
    "Switzerland", "Sweden", "Norway", "Denmark", "Ireland", "South Africa", "Kenya", "Nigeria",
    "Egypt", "United Arab Emirates", "Saudi Arabia", "Turkey", "Portugal", "Austria",
    "United States", "Canada", "Mexico", "China", "Japan", "South Korea", "Taiwan", "Hong Kong",
    "Mongolia", "Guatemala", "Costa Rica", "Panama", "Colombia", "Venezuela", "Dominican Republic",
    "Brazil", "Argentina", "Chile", "Peru", "Uruguay", "Paraguay", "Ecuador", "Bolivia", "India",
    "Singapore", "Australia", "New Zealand", "Thailand", "Vietnam", "Malaysia", "Indonesia",
    "Philippines", "Pakistan", "Bangladesh", "Sri Lanka", "Cambodia", "Myanmar", "Laos"
]

COUNTRY_ALIASES = {
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "usa": "United States",
    "u.s.a.": "United States",
    "us": "United States",
    "u.s.": "United States",
    "korea": "South Korea"
}


def _find_countries(question: str) -> list[str]:
    """Extract every country explicitly named, preserving mention order.

    Longest names are matched first to avoid partial overlaps such as Korea/South Korea.
    """
    q = question.lower()
    matches = []
    for country in sorted(COUNTRIES, key=len, reverse=True):
        if re.search(r"(?<![a-z])" + re.escape(country.lower()) + r"(?![a-z])", q):
            matches.append((q.find(country.lower()), country))
    for alias, canonical in COUNTRY_ALIASES.items():
        if re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", q):
            matches.append((q.find(alias), canonical))
    matches.sort(key=lambda item: item[0])
    result = []
    for _, country in matches:
        if country not in result:
            result.append(country)
    return result


def _threshold_usd(question: str) -> float:
    """Parse a simple USD exposure threshold; default to USD 1 million."""
    q = question.lower().replace(",", "")
    match = re.search(
        r"(?:above|over|exceed(?:ing)?|greater than)\s*(?:usd|us\$|\$)?\s*"
        r"(\d+(?:\.\d+)?)\s*(billion|bn|million|m|thousand|k)?",
        q
    )
    if not match:
        return 1_000_000.0
    value = float(match.group(1))
    unit = (match.group(2) or "").lower()
    multiplier = {"billion": 1_000_000_000, "bn": 1_000_000_000,
                  "million": 1_000_000, "m": 1_000_000,
                  "thousand": 1_000, "k": 1_000}.get(unit, 1)
    return value * multiplier


def _requested_limit(question: str, default: int = 10) -> int:
    """Extract a top-N limit and cap it to protect Telegram output."""
    match = re.search(r"\btop\s+(\d{1,3})\b", question.lower())
    return max(1, min(int(match.group(1)), 50)) if match else default


def route_question(connection: sqlite3.Connection, question: str) -> str | None:
    """Route supported registry intents to deterministic SQL services.

    Structured registry requests never fall through to an LLM merely because a
    particular report phrase was not implemented. None is reserved for general
    conversational requests outside the registry domain.
    """
    q = re.sub(r"\s+", " ", (question or "").strip().lower())
    if not q:
        return "Please enter a tax intelligence question. Use /help to see supported reports."

    countries = _find_countries(question)

    # Reference tables are deterministic and must not require conversational RAG.
    if any(term in q for term in ("five tax audit", "five audit stages", "five stages", "5 stages",
                                  "stage definitions", "explain the audit stages", "list all audit stages")):
        return tax_service.audit_stage_reference(connection)
    # Audit-phase reference requests must be distinguished from case reports that
    # merely ask for the current phase of individual cases.
    phase_reference_patterns = (
        r"\b(?:all|the)\s+(?:seven|7)\s+(?:audit\s+)?phases?\b",
        r"\b(?:list|show|display)\s+(?:all\s+)?(?:the\s+)?audit\s+phases?\b",
        r"\b(?:audit\s+)?phase\s+(?:reference|definitions?)\b",
        r"\b(?:audit\s+)?lifecycle\s+phases?\b",
        r"\bsequence\s+of\s+(?:the\s+)?(?:audit\s+)?phases?\b",
        r"\b(?:seven|7)\s+audit\s+phases?\b",
    )
    is_phase_reference_request = (
        any(re.search(pattern, q) for pattern in phase_reference_patterns)
        or (
            "audit" in q and "phase" in q
            and any(term in q for term in ("in sequence", "exact names", "phase definitions"))
            and any(term in q for term in ("all", "seven", "7", "list", "show", "display"))
        )
    )
    if is_phase_reference_request:
        return tax_service.audit_phase_reference(connection)

    # Consolidated executive snapshot: deterministic aggregation across all three registries.
    executive_terms = ("executive summary", "executive snapshot", "management summary",
                       "tax exposures and tax compliances", "tax exposure and compliance")
    asks_regional_executive = (
        any(term in q for term in ("audit", "dispute", "litigation"))
        and any(term in q for term in ("compliance", "compliances"))
        and any(term in q for term in ("active legal entit", "active entit"))
        and any(term in q for term in ("region", "regional"))
    )
    is_existing_regional_compliance_report = any(
        term in q for term in ("regional compliance", "compliance by region",
                               "summary by region", "regional tax compliance")
    )
    if asks_regional_executive or (
        not is_existing_regional_compliance_report and (
            any(term in q for term in executive_terms) or (
                "summary" in q and any(term in q for term in ("active entit", "tax exposure", "tax compliance"))
            )
        )
    ):
        return tax_service.executive_summary(connection)

    # Explicit global audit summaries must be tested before generic audit filters.
    if (("global" in q or "worldwide" in q) and
            any(term in q for term in ("audit summary", "litigation summary", "dispute summary", "audit and litigation")) and
            not any(term in q for term in ("top ", "above ", "over ", "exposure above"))):
        return tax_service.global_audit_summary(connection)

    if any(term in q for term in ("audit", "dispute", "litigation", "tax controversy")) and \
            any(term in q for term in ("above", "over", "exceed", "high-risk", "high risk", "threshold")):
        return tax_service.high_exposure_audits(connection, _threshold_usd(question), _requested_limit(question, 10))

    if any(term in q for term in ("top ", "highest exposure", "largest exposure")) and \
            any(term in q for term in ("audit", "dispute", "litigation", "case")):
        return tax_service.top_audit_cases(connection, _requested_limit(question))

    # Multi-country comparison precedes single-country routing.
    if len(countries) >= 2 and any(term in q for term in ("compare", "comparison", "across", "filing counts by status")):
        return tax_service.country_compliance_comparison(connection, countries)

    if any(term in q for term in ("regional compliance", "compliance by region", "summary by region", "regional tax compliance")):
        return tax_service.regional_compliance_summary(connection)

    if any(term in q for term in ("global cit", "cit filings globally", "corporate income tax filings globally",
                                  "corporate income tax globally", "grouped by country")) and \
            any(term in q for term in ("cit", "corporate income tax")):
        return tax_service.global_cit_filings(connection)

    if any(term in q for term in ("global", "worldwide", "across all countries")) and \
            any(term in q for term in ("compliance summary", "tax compliance", "filing summary",
                                       "filings summary", "global dashboard", "complaints summary")):
        return tax_service.global_summary(connection)

    if ("overdue" in q or "past due" in q) and \
            any(term in q for term in ("filing", "return", "tax", "compliance")):
        return tax_service.overdue_filings(connection)

    country = countries[0] if countries else None

    # Audit/litigation intent takes precedence over entity keywords that may appear
    # as requested output fields (for example, "audit cases including legal entity").
    if country and any(term in q for term in ("audit", "dispute", "litigation", "tax controversy")):
        return tax_service.country_audits(connection, country)

    if country and any(term in q for term in ("proof", "receipt", "artifact", "filing evidence")):
        keyword = "CIT" if ("cit" in q or "corporate income tax" in q) else ""
        if "vat" in q:
            keyword = "VAT"
        elif "gst" in q:
            keyword = "GST"
        elif "withholding" in q or "wht" in q:
            keyword = "WHT"
        return tax_service.country_artifact_lookup(connection, country, keyword)

    if country and any(term in q for term in ("entity profile", "subsidiary", "legal entit",
                                               "entities", "tax registration", "directors", "entity register")):
        return tax_service.country_entity_profile(connection, country)

    if country and any(term in q for term in ("filing", "compliance", "cit", "vat", "gst",
                                               "withholding", "wht", "return", "tax status")):
        keyword = ""
        if "cit" in q or "corporate income tax" in q:
            keyword = "CIT"
        elif "vat" in q:
            keyword = "VAT"
        elif "gst" in q:
            keyword = "GST"
        elif "withholding" in q or "wht" in q:
            keyword = "WHT"
        return tax_service.country_compliance(connection, country, keyword)

    # A registry-domain question should receive a clear deterministic limitation,
    # not an LLM-generated answer that could invent facts.
    structured_terms = (
        "tax", "filing", "compliance", "legal entity", "entity", "audit",
        "litigation", "dispute", "exposure", "tax id", "registration",
        "statutory due", "artifact", "receipt", "proof", "country", "region"
    )
    if any(term in q for term in structured_terms):
        return (
            "This request is within the Tax365 registry domain, but its report pattern "
            "is not yet supported. No result has been inferred. Please use /help for "
            "supported reports or ask an administrator to add this report."
        )

    return None
