# Tax365V0 – Global Tax Intelligence Telegram Bot

## Purpose

A locally hosted Telegram assistant for a synthetic 60-country agri-food tax operating model. It provides deterministic access to legal entities, tax compliance, audits/litigations and artifact metadata, with optional AnythingLLM conversational fallback.

**Data warning:** The supplied CSVs are synthetic test data and are not actual Cargill records. Artifact filenames in the sample index are metadata only. No PDF binaries are included in the sample data pack.

## Architecture

```text
Telegram
   |
   v
Python Telegram middleware
   |-- Security allowlist
   |-- Query router
   |     |-- Deterministic SQL -> SQLite
   |     `-- Conversational fallback -> AnythingLLM -> local Ollama
   |-- Artifact verification -> local PDF repository
   `-- Audit logging
```

## Project location

Expected layout:

```text
Tax365V0/
  1_BOT/
    data/                 # Your existing eight CSV files
    T365_Solution/        # This project
```

The `.env.example` default `DATA_DIR=../data` is set for this layout.

## Setup – Windows PowerShell

1. Copy `.env.example` to `.env`.
2. Create a Telegram bot using `@BotFather` and put its token in `.env`.
3. Create the virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

4. Edit `.env` and set `TELEGRAM_BOT_TOKEN`.
5. Start the bot:

```powershell
python main.py
```

6. In Telegram, send `/start`, then copy your numeric user ID.
7. Stop the bot with Ctrl+C. Add your ID to `ALLOWED_TELEGRAM_USER_IDS` in `.env`, for example:

```text
ALLOWED_TELEGRAM_USER_IDS=123456789
```

8. Restart `python main.py`. The bot now allows only the listed Telegram IDs.

## Optional AnythingLLM connection

- Configure Ollama and the `Global-Tax-Intelligence` workspace in AnythingLLM.
- Create an AnythingLLM API key.
- Set `ANYTHINGLLM_ENABLED=true`, `ANYTHINGLLM_API_KEY`, and the correct workspace slug in `.env`.
- Restart the bot.

AnythingLLM is a fallback for questions not handled by deterministic SQL. Exact financial amounts and filing statuses should continue to come from SQLite.

## Initial supported questions

- `Give me a global tax compliance summary across all 60 countries.`
- `Show me overdue tax filings.`
- `Show me high-risk audits over $1 million.`
- `Give me the entity profile for Germany.`
- `Is the Brazil CIT return filed?`
- `Show me tax disputes in India.`

## Current starter limitations

- This is the first executable scaffold, not a production-ready enterprise application.
- Initial routing supports a defined set of question patterns; it is not a complete natural-language SQL engine.
- Country and region authorization is currently a Telegram user allowlist only. Do not add real tax data until row-level region/country authorization is implemented and tested.
- Artifact delivery is deliberately fail-closed. It requires a real PDF in `artifacts/`; sample metadata alone does not trigger file sending.
- The AnythingLLM API connection is optional and must be tested against the installed AnythingLLM version and workspace slug.
- The current CSV import replaces the imported tables at startup. Do not edit source CSVs while the bot is running.
- This implementation uses Telegram polling, so the host PC and bot process must remain online.

## Security before enterprise use

Implement individual roles, region/country row-level access, secret management, TLS/network boundaries, encrypted backups, retention controls, prompt-injection defenses for uploaded documents, robust artifact authorization, monitoring, and independent validation of financial outputs.
