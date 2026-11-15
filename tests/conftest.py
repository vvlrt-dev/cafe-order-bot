from __future__ import annotations

import itertools
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from bot.config import PROJECT_ROOT, Settings
from bot.handlers import OrderBot
from bot.menu import Menu
from bot.storage import OrderStore

TZ = ZoneInfo("Asia/Tashkent")
ADMIN = 999
USER = 42


class FakeClient:
    """Records every Bot API call instead of sending it."""

    def __init__(self):
        self.calls: list[dict] = []
        self._ids = itertools.count(100)

    def send_message(self, chat_id, text, reply_markup=None):
        message_id = next(self._ids)
        self.calls.append({"method": "send", "chat_id": chat_id, "text": text,
                           "markup": reply_markup, "message_id": message_id})
        return {"message_id": message_id}

    def edit_message(self, chat_id, message_id, text, reply_markup=None):
        self.calls.append({"method": "edit", "chat_id": chat_id, "text": text,
                           "markup": reply_markup, "message_id": message_id})
        return {}

    def answer_callback(self, callback_id, text=None):
        self.calls.append({"method": "answer", "text": text})

    def last(self, method=None, chat_id=None):
        for call in reversed(self.calls):
            if (method is None or call["method"] == method) and (chat_id is None or call.get("chat_id") == chat_id):
                return call
        raise AssertionError(f"No {method} call for chat {chat_id}")


class Driver:
    """Builds Telegram-shaped updates and feeds them to the bot."""

    def __init__(self, bot: OrderBot, client: FakeClient):
        self.bot, self.client = bot, client
        self._update_ids = itertools.count(1)
        self._query_ids = itertools.count(1)

    def text(self, text, user=USER):
        self.bot.handle_update({"update_id": next(self._update_ids), "message": {
            "message_id": 1, "chat": {"id": user}, "from": {"id": user}, "text": text}})

    def contact(self, phone, user=USER):
        self.bot.handle_update({"update_id": next(self._update_ids), "message": {
            "message_id": 1, "chat": {"id": user}, "from": {"id": user},
            "contact": {"phone_number": phone, "user_id": user}}})

    def tap(self, data, user=USER, chat=None, message_id=1):
        chat = chat if chat is not None else user
        self.bot.handle_update({"update_id": next(self._update_ids), "callback_query": {
            "id": str(next(self._query_ids)), "from": {"id": user}, "data": data,
            "message": {"message_id": message_id, "chat": {"id": chat}}}})


@pytest.fixture(autouse=True)
def fail_on_swallowed_errors(caplog):
    """handle_update logs and swallows exceptions in production; in tests they must fail loudly."""
    yield
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert not errors, f"Handler raised: {errors[0].getMessage()}\n{errors[0].exc_text}"


@pytest.fixture
def clock():
    state = {"now": datetime(2026, 11, 14, 12, 7, tzinfo=TZ)}
    return state


@pytest.fixture
def settings(tmp_path):
    return Settings(bot_token="test", admin_chat_id=ADMIN, db_path=tmp_path / "orders.sqlite3")


@pytest.fixture
def menu():
    return Menu.load(PROJECT_ROOT / "menu.json")


@pytest.fixture
def store(settings):
    s = OrderStore(settings.db_path)
    yield s
    s.close()


@pytest.fixture
def client():
    return FakeClient()


@pytest.fixture
def bot(client, menu, store, settings, clock):
    return OrderBot(client, menu, store, settings, now=lambda: clock["now"])


@pytest.fixture
def driver(bot, client):
    return Driver(bot, client)
