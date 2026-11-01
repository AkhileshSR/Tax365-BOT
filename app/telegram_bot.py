"""
Purpose: Secure Telegram interface for the Tax365 executive demonstration.
Sample input: /start, /help, /whoami or a supported tax intelligence question.
Output: Approved-user response from the deterministic registry or optional conversational service.
Dependencies: python-telegram-bot, config.py, database.py, security.py and services.
Architecture: Telegram -> authorization -> intent router -> SQL services -> formatter -> Telegram.
"""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from .config import Settings
from .database import connect_db, log_event
from .security import is_authorized
from .query_router import route_question
from .anythingllm_client import ask_anythingllm
from .response_formatter import split_telegram_message

logger = logging.getLogger(__name__)

DEMO_NOTICE = (
    "DEMO ENVIRONMENT — This instance uses illustrative synthetic data. "
    "It does not represent actual client tax records."
)


def _get_connection(settings: Settings):
    """Open a short-lived SQLite connection for one Telegram update."""
    return connect_db(settings.database_path)


async def _reply(update: Update, message: str) -> None:
    """Send one or more Telegram-safe text chunks to the current chat."""
    if not update.message:
        return
    for chunk in split_telegram_message(message):
        await update.message.reply_text(chunk)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Introduce Tax365, disclose demo data and report the caller's authorization state."""
    user = update.effective_user
    if user is None:
        return
    settings: Settings = context.application.bot_data["settings"]
    authorized = is_authorized(user.id, settings)
    access_text = "Access: APPROVED" if authorized else (
        "Access: NOT APPROVED — an administrator must add your numeric Telegram ID "
        "to ALLOWED_TELEGRAM_USER_IDS in the local .env file."
    )
    await _reply(
        update,
        "TAX365 | GLOBAL TAX INTELLIGENCE\n"
        "Executive mobile assistant for legal entities, tax compliance, audits and litigations.\n\n"
        f"Telegram user ID: {user.id}\n"
        f"{access_text}\n\n"
        f"{DEMO_NOTICE}\n\n"
        "Use /help to see the available reports."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List supported deterministic reports and copy-ready example questions."""
    await _reply(
        update,
        "TAX365 | AVAILABLE REPORTS\n\n"
        "GLOBAL COMPLIANCE\n"
        "• Give me a global tax compliance summary with percentages.\n"
        "• List all overdue tax filings globally.\n"
        "• Show tax compliance by region.\n"
        "• Show all CIT filings globally grouped by country and status.\n\n"
        "COUNTRY REPORTS\n"
        "• Compare tax compliance across India, Brazil, Germany and the United States.\n"
        "• Show the legal entity register for Brazil.\n"
        "• Show tax compliance for Brazil.\n"
        "• Show all tax audits and litigations in India.\n"
        "• Find the CIT filing proof for Brazil.\n\n"
        "AUDITS & LITIGATIONS\n"
        "• Give me the global tax audit and litigation summary by region.\n"
        "• List the top 10 tax disputes by financial exposure.\n"
        "• List audit cases above USD 1 million.\n"
        "• Explain the five audit stages.\n"
        "• List the seven audit lifecycle phases.\n\n"
        "COMMANDS\n"
        "/start — Bot introduction and access status\n"
        "/whoami — Your Telegram numeric user ID\n"
        "/help — Supported questions\n\n"
        "For registry questions, answers are calculated from SQLite. "
        "AnythingLLM is optional and is not the source of financial figures."
    )


async def whoami_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return the Telegram numeric user ID without exposing registry data."""
    user = update.effective_user
    if user:
        await _reply(update, f"Telegram user ID: {user.id}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Authorize, classify and answer a text question using registry-backed services."""
    settings: Settings = context.application.bot_data["settings"]
    user = update.effective_user
    if user is None or update.message is None:
        return

    question = (update.message.text or "").strip()
    if not question:
        await _reply(update, "Please enter a question. Use /help for supported reports.")
        return

    if not is_authorized(user.id, settings):
        await _reply(
            update,
            "ACCESS DENIED\n"
            "Your Telegram account is not on the approved user list.\n"
            f"Your Telegram user ID: {user.id}\n"
            "Ask the Tax365 administrator to add this ID to ALLOWED_TELEGRAM_USER_IDS."
        )
        return

    connection = _get_connection(settings)
    try:
        answer = route_question(connection, question)

        if answer is None:
            try:
                answer = await ask_anythingllm(
                    question,
                    settings,
                    session_id=f"tax365-telegram-{user.id}"
                )
            except Exception:
                logger.exception("AnythingLLM request failed or is not configured")
                answer = (
                    "This question is not covered by the deterministic Tax365 reports, "
                    "and the optional conversational AI service is unavailable or disabled. "
                    "No registry answer has been inferred. Use /help for supported questions."
                )

        # Preserve a compact audit trail; never log credentials or bot tokens.
        try:
            log_event(connection, user.id, "QUESTION", question, answer[:1500])
        except Exception:
            logger.exception("Unable to write Tax365 question audit log")

        await _reply(update, f"{answer}\n\n{DEMO_NOTICE}")
    except Exception:
        logger.exception("Tax365 request processing failed")
        await _reply(
            update,
            "Tax365 could not complete this request because of an internal processing error. "
            "The event has been logged for administrator review."
        )
    finally:
        connection.close()


def build_application(settings: Settings) -> Application:
    """Construct the Telegram application and register all user-facing handlers."""
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["settings"] = settings
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("whoami", whoami_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application
