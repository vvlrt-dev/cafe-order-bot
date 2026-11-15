"""Checks the HTTP client against a local fake of the Bot API."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from bot.telegram_api import TelegramClient, TelegramError


class FakeApi(BaseHTTPRequestHandler):
    received: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        method = self.path.rsplit("/", 1)[-1]
        FakeApi.received.append((self.path, body))
        if method == "editMessageText":
            self._reply(400, {"ok": False, "description": "Bad Request: message is not modified"})
        elif method == "sendMessage" and body.get("chat_id") == -1:
            self._reply(403, {"ok": False, "description": "Forbidden: bot was blocked by the user"})
        else:
            self._reply(200, {"ok": True, "result": {"message_id": 7}})

    def _reply(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def api():
    FakeApi.received = []
    server = HTTPServer(("127.0.0.1", 0), FakeApi)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield TelegramClient("TOKEN", timeout=5, api_url=f"http://127.0.0.1:{server.server_port}")
    server.shutdown()


def test_send_message_posts_json(api):
    result = api.send_message(42, "<b>Hi</b>", {"inline_keyboard": []})
    assert result == {"message_id": 7}
    path, body = FakeApi.received[-1]
    assert path == "/botTOKEN/sendMessage"
    assert body["chat_id"] == 42 and body["parse_mode"] == "HTML"
    assert body["reply_markup"] == {"inline_keyboard": []}


def test_none_params_are_not_sent(api):
    api.answer_callback("abc")
    assert FakeApi.received[-1][1] == {"callback_query_id": "abc"}


def test_not_modified_edit_is_ignored(api):
    assert api.edit_message(42, 1, "same text") == {}


def test_api_errors_raise(api):
    with pytest.raises(TelegramError, match="blocked by the user"):
        api.send_message(-1, "hello")
