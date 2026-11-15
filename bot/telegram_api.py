"""Minimal Telegram Bot API client using only the standard library."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)


class TelegramError(RuntimeError):
    pass


class TelegramClient:
    """Wraps the handful of Bot API methods this bot needs."""

    def __init__(self, token: str, timeout: int = 35, api_url: str = "https://api.telegram.org"):
        self._base = f"{api_url.rstrip('/')}/bot{token}/"
        self._timeout = timeout

    def call(self, method: str, **params: Any) -> Any:
        payload = {k: v for k, v in params.items() if v is not None}
        request = urllib.request.Request(
            self._base + method,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8") or "{}")
        if not body.get("ok"):
            raise TelegramError(f"{method} failed: {body.get('description', 'unknown error')}")
        return body["result"]

    def get_updates(self, offset: int | None, timeout: int = 30) -> list[dict]:
        return self.call("getUpdates", offset=offset, timeout=timeout,
                         allowed_updates=["message", "callback_query"])

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> dict:
        return self.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                         reply_markup=reply_markup, disable_web_page_preview=True)

    def edit_message(self, chat_id: int, message_id: int, text: str, reply_markup: dict | None = None) -> dict:
        try:
            return self.call("editMessageText", chat_id=chat_id, message_id=message_id, text=text,
                             parse_mode="HTML", reply_markup=reply_markup)
        except TelegramError as exc:
            if "message is not modified" in str(exc):
                return {}
            raise

    def answer_callback(self, callback_id: str, text: str | None = None) -> None:
        self.call("answerCallbackQuery", callback_query_id=callback_id, text=text)
