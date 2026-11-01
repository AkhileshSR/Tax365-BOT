"""
Purpose: Start Tax365, initialize SQLite and launch Telegram long polling.
Sample input: Valid .env file and eight source CSVs in ../data.
Output: Running Telegram bot and populated local SQLite database.
Dependencies: app.config, app.database, app.data_loader, app.telegram_bot.
Architecture: main -> settings -> database/schema -> CSV import -> Telegram polling.
"""

import logging
from app.config import load_settings
from app.database import connect_db, initialize_schema
from app.data_loader import import_csv_directory
from app.telegram_bot import build_application

def main() -> None:
    """
    Initialize the local application and start Telegram polling.
    Input: Environment configuration and source CSV directory.
    Output: Long-running Telegram bot process.
    """
    settings = load_settings()
    if not settings.telegram_bot_token:
        raise ValueError("Set TELEGRAM_BOT_TOKEN in .env before starting the bot.")

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=settings.log_dir / "tax365.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    connection = connect_db(settings.database_path)
    try:
        initialize_schema(connection)
        counts = import_csv_directory(connection, settings.data_dir)
        print("Tax365 data import complete:")
        for table, count in counts.items():
            print(f"  {table}: {count} rows")
    finally:
        connection.close()

    application = build_application(settings)
    print("Tax365 Telegram bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=["message"])

if __name__ == "__main__":
    main()
