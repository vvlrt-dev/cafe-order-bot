"""Settings read from environment variables (or a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file without overriding real environment variables."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_chat_id: int
    timezone: str = "Asia/Tashkent"
    opens_at: time = time(10, 0)
    closes_at: time = time(22, 0)
    prep_minutes: int = 20
    menu_path: Path = PROJECT_ROOT / "menu.json"
    db_path: Path = PROJECT_ROOT / "orders.sqlite3"
    api_url: str = "https://api.telegram.org"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        token = os.environ.get("BOT_TOKEN", "").strip()
        admin = os.environ.get("ADMIN_CHAT_ID", "").strip()
        if not token:
            raise SystemExit("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")
        if not admin.lstrip("-").isdigit():
            raise SystemExit("ADMIN_CHAT_ID must be a numeric Telegram chat id.")
        return cls(
            bot_token=token,
            admin_chat_id=int(admin),
            timezone=os.environ.get("TIMEZONE", cls.timezone),
            opens_at=_parse_hhmm(os.environ.get("OPENS_AT", "10:00")),
            closes_at=_parse_hhmm(os.environ.get("CLOSES_AT", "22:00")),
            prep_minutes=int(os.environ.get("PREP_MINUTES", cls.prep_minutes)),
            menu_path=Path(os.environ.get("MENU_PATH", cls.menu_path)),
            db_path=Path(os.environ.get("DB_PATH", cls.db_path)),
            api_url=os.environ.get("TELEGRAM_API_URL", cls.api_url),
        )
