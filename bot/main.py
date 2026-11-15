"""Run the bot with long polling: python -m bot.main"""

from __future__ import annotations

import logging
import time

from .config import Settings
from .handlers import OrderBot
from .menu import Menu
from .storage import OrderStore
from .telegram_api import TelegramClient, TelegramError

log = logging.getLogger("cafe_bot")


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    client = TelegramClient(settings.bot_token, api_url=settings.api_url)
    bot = OrderBot(client, Menu.load(settings.menu_path), OrderStore(settings.db_path), settings)

    me = client.call("getMe")
    log.info("Running as @%s. Press Ctrl+C to stop.", me.get("username"))

    offset = None
    while True:
        try:
            for update in client.get_updates(offset):
                offset = update["update_id"] + 1
                bot.handle_update(update)
        except KeyboardInterrupt:
            log.info("Stopped.")
            break
        except (TelegramError, OSError) as exc:
            log.warning("Polling error: %s. Retrying in 5 s.", exc)
            time.sleep(5)


if __name__ == "__main__":
    run()
