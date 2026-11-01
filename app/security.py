"""
Purpose: Enforce Telegram user allowlisting and provide a minimal demo role.
Sample input: Telegram numeric user ID and configured allowlist.
Output: True only when the user is explicitly allowlisted.
Dependencies: config.py.
Architecture: Telegram update -> security check -> query service.
"""

from .config import Settings

def is_authorized(user_id: int | None, settings: Settings) -> bool:
    """
    Check whether a Telegram user is permitted to use the bot.
    Input: Telegram user ID and settings.
    Output: Boolean. Empty allowlist denies access (fail-closed).
    """
    return user_id is not None and user_id in settings.allowed_telegram_user_ids
