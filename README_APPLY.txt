TAX365 REGIONAL EXECUTIVE SUMMARY FIX

Files to replace in T365_Solution:
  app\tax_service.py
  app\query_router.py

This package preserves the validated audit-stage and audit-phase routing fixes and adds the requested regional executive report.

Apply:
1. Stop the bot with Ctrl+C.
2. Back up the two current files.
3. Extract this ZIP into T365_Solution, preserving the app folder.
4. Run:
   python -m py_compile .\app\tax_service.py .\app\query_router.py
   python validate_regional_executive.py ..\data
5. If validation passes, restart: python main.py

Do not replace CSV files, .env, database, telegram_bot.py, or other modules.

Report definitions:
- Audit/dispute count and exposure: all tax_audits cases, using financial_risk_amount_usd (USD), all statuses.
- Compliance count: all tax_compliance filing records. Compliance exposure is defined as late_filing_penalty_local and shown by local currency. No FX conversion or cross-currency sum is performed.
- Active legal entities: entity_status values Active or Active / Good Standing, grouped by regional_org. Latest last_verified_date is disclosed; no status-effective date exists in the source.

The data is synthetic. The report date is the machine's local date; it does not imply the source records were verified on that date.
