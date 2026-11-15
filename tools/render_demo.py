"""Render demo screenshots of a scripted ordering session.

The script runs a customer and the cafe admin through the bot's real handlers
(with a recording client instead of the network) and draws the resulting
conversation as a Telegram-style chat. Requires Playwright with Chromium:

    python tools/render_demo.py
"""

from __future__ import annotations

import copy
import html
import itertools
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bot.config import Settings  # noqa: E402
from bot.handlers import OrderBot  # noqa: E402
from bot.menu import Menu  # noqa: E402
from bot.storage import OrderStore  # noqa: E402

CUSTOMER, ADMIN = 1001, 2002
TZ = ZoneInfo("Asia/Tashkent")


class Transcript:
    """Client that keeps each chat as a list of bubbles, applying edits in place."""

    def __init__(self):
        self.chats: dict[int, list[dict]] = {}
        self.frames: dict[str, list[dict]] = {}
        self._ids = itertools.count(1)

    def _chat(self, chat_id):
        return self.chats.setdefault(chat_id, [])

    def user_says(self, chat_id, text):
        self._chat(chat_id).append({"from": "user", "text": html.escape(text)})

    def send_message(self, chat_id, text, reply_markup=None):
        message_id = next(self._ids)
        self._chat(chat_id).append({"from": "bot", "id": message_id, "text": text, "markup": reply_markup})
        return {"message_id": message_id}

    def edit_message(self, chat_id, message_id, text, reply_markup=None):
        for bubble in self._chat(chat_id):
            if bubble.get("id") == message_id:
                bubble["text"], bubble["markup"] = text, reply_markup
        return {}

    def answer_callback(self, callback_id, text=None):
        pass

    def snapshot(self, name, chat_id, start_marker=None):
        """Freeze the chat as it looks right now, optionally from the first bubble containing start_marker."""
        bubbles = self._chat(chat_id)
        if start_marker:
            bubbles = bubbles[next(i for i, b in enumerate(bubbles) if start_marker in b["text"]):]
        self.frames[name] = copy.deepcopy(bubbles)

    def last_bot_id(self, chat_id):
        return next(b["id"] for b in reversed(self._chat(chat_id)) if b["from"] == "bot")


def run_session(tmp: Path) -> Transcript:
    settings = Settings(bot_token="demo", admin_chat_id=ADMIN, db_path=tmp / "demo.sqlite3")
    client = Transcript()
    clock = datetime(2026, 11, 14, 12, 7, tzinfo=TZ)
    bot = OrderBot(client, Menu.load(ROOT / "menu.json"), OrderStore(settings.db_path), settings, now=lambda: clock)
    updates = itertools.count(1)

    def say(text, user=CUSTOMER):
        client.user_says(user, text)
        bot.handle_update({"update_id": next(updates), "message": {
            "message_id": 0, "chat": {"id": user}, "from": {"id": user}, "text": text}})

    def tap(data, user=CUSTOMER):
        bot.handle_update({"update_id": next(updates), "callback_query": {
            "id": "q", "from": {"id": user}, "data": data,
            "message": {"message_id": client.last_bot_id(user), "chat": {"id": user}}}})

    say("/start")
    tap("menu")
    tap("cat:mains")
    tap("add:plov")
    tap("add:plov")
    client.snapshot("1-menu.png", CUSTOMER)
    tap("cat:bakery")  # the same message is edited in place, as in Telegram
    tap("add:samsa")
    tap("add:non")
    tap("cart")
    client.snapshot("2-cart.png", CUSTOMER)
    tap("checkout")
    say("Aziza")
    say("+998 90 123 45 67")
    tap("slot:1300")
    client.snapshot("3-confirm.png", CUSTOMER, start_marker="Step 1 of 3")
    tap("confirm")
    client.snapshot("4-admin-notification.png", ADMIN)
    tap("adm:accepted:1", user=ADMIN)
    client.snapshot("5-order-placed.png", CUSTOMER, start_marker="Order #1 received")
    return client


def keyboard_html(markup: dict | None) -> str:
    if not markup:
        return ""
    if "inline_keyboard" in markup:
        rows = "".join(
            '<div class="kb-row">' + "".join(
                f'<span class="kb-btn{" wide" if len(row) == 3 and i == 1 else ""}">{html.escape(b["text"])}</span>'
                for i, b in enumerate(row)) + "</div>"
            for row in markup["inline_keyboard"])
        return f'<div class="kb">{rows}</div>'
    return ""


def bubble_html(bubble: dict) -> str:
    text = bubble["text"].replace("\n", "<br>")
    if bubble["from"] == "user":
        return f'<div class="row right"><div class="bubble user">{text}</div></div>'
    if not re.sub(r"<[^>]+>", "", bubble["text"]).strip():
        return ""
    return f'<div class="row"><div class="msg"><div class="bubble bot">{text}</div>{keyboard_html(bubble.get("markup"))}</div></div>'


PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;font:15px/1.4 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:#d7e3ec}}
.phone{{width:420px;margin:0 auto;background:#c8d9e6;min-height:100vh}}
.top{{background:#517da2;color:#fff;padding:12px 16px;display:flex;gap:12px;align-items:center}}
.avatar{{width:38px;height:38px;border-radius:50%;background:#e8a33d;display:grid;place-items:center;font-weight:700}}
.top b{{display:block}} .top small{{opacity:.8}}
.chat{{padding:12px 10px 8px}}
.row{{display:flex;margin:6px 0}} .right{{justify-content:flex-end}}
.msg{{max-width:86%}}
.bubble{{padding:7px 11px;border-radius:12px;box-shadow:0 1px 1px rgba(0,0,0,.12);word-wrap:break-word}}
.bot{{background:#fff;border-bottom-left-radius:4px}}
.user{{background:#effdde;border-bottom-right-radius:4px;max-width:70%}}
.kb{{margin-top:4px}} .kb-row{{display:flex;gap:4px;margin-top:4px}}
.kb-btn.wide{{flex:3}}
.kb-btn{{flex:1;text-align:center;background:rgba(73,104,135,.55);color:#fff;border-radius:8px;padding:7px 6px;font-size:13.5px;font-weight:500}}
.note{{text-align:center;font-size:11.5px;color:#4a6276;padding:6px 10px 14px}}
</style></head><body><div class="phone">
<div class="top"><div class="avatar">{initial}</div><div><b>{title}</b><small>{subtitle}</small></div></div>
<div class="chat">{bubbles}</div>
<div class="note">Concept project · rendered from a scripted session run through the bot's handlers</div>
</div></body></html>"""


def render(transcript: Transcript, out_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    titles = {name: ("Kazan &amp; Tandoor · orders", "admin chat") if "admin" in name else ("Kazan &amp; Tandoor bot", "bot")
              for name in transcript.frames}
    pages = {name: (*titles[name], bubbles) for name, bubbles in transcript.frames.items()}
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 460, "height": 400}, device_scale_factor=2)
        for name, (title, subtitle, bubbles) in pages.items():
            page.set_content(PAGE.format(initial="K", title=title, subtitle=subtitle,
                                         bubbles="".join(bubble_html(b) for b in bubbles)))
            path = out_dir / name
            page.locator(".phone").screenshot(path=str(path))
            written.append(path)
        browser.close()
    return written


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        transcript = run_session(Path(tmp))
    for path in render(transcript, ROOT / "docs"):
        print("wrote", path.relative_to(ROOT))
