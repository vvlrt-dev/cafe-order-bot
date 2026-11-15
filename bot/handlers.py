"""Bot logic: turns Telegram updates into API calls.

The class only talks to Telegram through the small client interface
(send_message / edit_message / answer_callback), so the whole flow can be
tested with a fake client and no network.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from . import keyboards as kb
from . import texts
from .cart import Cart
from .config import Settings
from .menu import Menu
from .storage import OrderStore
from .validation import ValidationError, clean_name, clean_phone, parse_pickup_time, pickup_slots

log = logging.getLogger(__name__)


class BotClient(Protocol):
    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> dict: ...
    def edit_message(self, chat_id: int, message_id: int, text: str, reply_markup: dict | None = None) -> dict: ...
    def answer_callback(self, callback_id: str, text: str | None = None) -> None: ...


@dataclass
class Session:
    cart: Cart = field(default_factory=Cart)
    state: str | None = None  # None, "name", "phone", "time", "confirm"
    name: str | None = None
    phone: str | None = None
    pickup_at: datetime | None = None

    def reset_checkout(self) -> None:
        self.state = None
        self.name = self.phone = None
        self.pickup_at = None


class OrderBot:
    def __init__(self, client: BotClient, menu: Menu, store: OrderStore, settings: Settings,
                 now: Callable[[], datetime] | None = None):
        self.client = client
        self.menu = menu
        self.store = store
        self.settings = settings
        tz = ZoneInfo(settings.timezone)
        self._now = now or (lambda: datetime.now(tz))
        self.sessions: dict[int, Session] = {}

    # ---- entry point -------------------------------------------------------

    def handle_update(self, update: dict) -> None:
        try:
            if "callback_query" in update:
                self._on_callback(update["callback_query"])
            elif "message" in update:
                self._on_message(update["message"])
        except Exception:  # keep polling alive; one bad update must not stop the bot
            log.exception("Failed to handle update %s", update.get("update_id"))

    def session(self, user_id: int) -> Session:
        return self.sessions.setdefault(user_id, Session())

    # ---- messages ----------------------------------------------------------

    def _on_message(self, message: dict) -> None:
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        session = self.session(user_id)
        text = (message.get("text") or "").strip()

        if text.startswith("/"):
            self._on_command(text.split()[0].split("@")[0].lower(), chat_id, session)
            return

        if session.state == "phone" and "contact" in message:
            self._take_phone(chat_id, session, message["contact"].get("phone_number", ""))
        elif session.state == "name":
            self._take_name(chat_id, session, text)
        elif session.state == "phone":
            self._take_phone(chat_id, session, text)
        elif session.state == "time":
            self._take_time(chat_id, session, text)
        else:
            self.client.send_message(chat_id, texts.use_buttons(), kb.home(session.cart, self.menu))

    def _on_command(self, command: str, chat_id: int, session: Session) -> None:
        if command == "/start":
            session.reset_checkout()
            self._send_home(chat_id, session)
        elif command == "/menu":
            self.client.send_message(chat_id, texts.categories(), kb.categories(self.menu, session.cart))
        elif command == "/cart":
            self.client.send_message(chat_id, texts.cart(session.cart, self.menu), kb.cart_view(session.cart, self.menu))
        elif command == "/cancel":
            session.reset_checkout()
            self.client.send_message(chat_id, texts.checkout_cancelled(), kb.remove_reply_keyboard())
            self._send_home(chat_id, session)
        elif command == "/help":
            self.client.send_message(chat_id, texts.help_text())
        else:
            self.client.send_message(chat_id, texts.use_buttons(), kb.home(session.cart, self.menu))

    def _send_home(self, chat_id: int, session: Session) -> None:
        text = texts.welcome(self.menu, self.settings.opens_at, self.settings.closes_at)
        self.client.send_message(chat_id, text, kb.home(session.cart, self.menu))

    # ---- callbacks ---------------------------------------------------------

    def _on_callback(self, query: dict) -> None:
        data = query.get("data", "")
        message = query.get("message") or {}
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        user_id = query["from"]["id"]

        if data.startswith("adm:"):
            self._on_admin(query, data, chat_id, message_id)
            return

        session = self.session(user_id)
        menu, cart = self.menu, session.cart
        alert = None

        if data == "menu":
            self.client.edit_message(chat_id, message_id, texts.categories(), kb.categories(menu, cart))
        elif data.startswith("cat:"):
            category = menu.category(data[4:])
            if category:
                self.client.edit_message(chat_id, message_id, texts.category(category, menu),
                                         kb.category_items(category, menu, cart))
        elif data.startswith("add:"):
            item = menu.item(data[4:])
            if item:
                qty = cart.add(item.id)
                alert = f"{item.name} added ({qty} in cart)"
                category = menu.category(item.category_id)
                self.client.edit_message(chat_id, message_id, texts.category(category, menu),
                                         kb.category_items(category, menu, cart))
        elif data == "cart":
            self._show_cart(chat_id, message_id, session)
        elif data.startswith(("inc:", "dec:")):
            item_id = data[4:]
            if menu.item(item_id):
                cart.add(item_id) if data.startswith("inc:") else cart.remove(item_id)
            self._show_cart(chat_id, message_id, session)
        elif data == "clear":
            cart.clear()
            self._show_cart(chat_id, message_id, session)
        elif data == "checkout":
            if cart.is_empty():
                alert = texts.empty_cart_alert()
            else:
                session.reset_checkout()
                session.state = "name"
                self.client.send_message(chat_id, texts.ask_name(), kb.cancel_checkout())
        elif data.startswith("slot:") and session.state == "time":
            self._take_time(chat_id, session, f"{data[5:7]}:{data[7:9]}")
        elif data == "confirm" and session.state == "confirm":
            self._place_order(chat_id, message_id, user_id, session)
        elif data == "cancel":
            session.reset_checkout()
            self.client.send_message(chat_id, texts.checkout_cancelled(), kb.remove_reply_keyboard())
            self._send_home(chat_id, session)

        self.client.answer_callback(query["id"], alert)

    def _show_cart(self, chat_id: int, message_id: int, session: Session) -> None:
        self.client.edit_message(chat_id, message_id, texts.cart(session.cart, self.menu),
                                 kb.cart_view(session.cart, self.menu))

    # ---- checkout steps ----------------------------------------------------

    def _take_name(self, chat_id: int, session: Session, text: str) -> None:
        try:
            session.name = clean_name(text)
        except ValidationError as err:
            self.client.send_message(chat_id, str(err), kb.cancel_checkout())
            return
        session.state = "phone"
        self.client.send_message(chat_id, texts.ask_phone(), kb.share_phone())

    def _take_phone(self, chat_id: int, session: Session, text: str) -> None:
        try:
            session.phone = clean_phone(text)
        except ValidationError as err:
            self.client.send_message(chat_id, str(err), kb.share_phone())
            return
        session.state = "time"
        self.client.send_message(chat_id, texts.phone_saved(), kb.remove_reply_keyboard())
        s = self.settings
        slots = pickup_slots(self._now(), s.opens_at, s.closes_at, s.prep_minutes)
        if not slots:
            session.reset_checkout()
            self.client.send_message(chat_id, texts.closed_today(s.opens_at, s.closes_at),
                                     kb.home(session.cart, self.menu))
            return
        self.client.send_message(chat_id, texts.ask_time(f"{slots[0]:%H:%M}"), kb.pickup_slots(slots))

    def _take_time(self, chat_id: int, session: Session, text: str) -> None:
        s = self.settings
        try:
            session.pickup_at = parse_pickup_time(text, self._now(), s.opens_at, s.closes_at, s.prep_minutes)
        except ValidationError as err:
            self.client.send_message(chat_id, str(err), kb.cancel_checkout())
            return
        session.state = "confirm"
        items, total = self._snapshot(session)
        self.client.send_message(
            chat_id,
            texts.summary(items, total, session.name, session.phone, f"{session.pickup_at:%H:%M}", self.menu),
            kb.confirm_order(),
        )

    def _snapshot(self, session: Session) -> tuple[list[dict], float]:
        lines = session.cart.lines(self.menu)
        items = [{"id": l.item.id, "name": l.item.name, "qty": l.qty, "price": l.item.price, "total": l.total}
                 for l in lines]
        return items, session.cart.total(self.menu)

    def _place_order(self, chat_id: int, message_id: int, user_id: int, session: Session) -> None:
        items, total = self._snapshot(session)
        if not items:
            session.reset_checkout()
            self.client.send_message(chat_id, texts.cart(session.cart, self.menu), kb.home(session.cart, self.menu))
            return
        order = self.store.create(user_id=user_id, chat_id=chat_id, name=session.name, phone=session.phone,
                                  pickup_at=session.pickup_at, items=items, total=total, created_at=self._now())
        session.cart.clear()
        session.reset_checkout()
        self.client.edit_message(chat_id, message_id, texts.order_confirmed(order, self.menu))
        self.client.send_message(self.settings.admin_chat_id, texts.admin_order(order, self.menu),
                                 kb.admin_order(order.id, order.status))
        log.info("Order #%s placed by user %s, total %.2f", order.id, user_id, total)

    # ---- admin -------------------------------------------------------------

    def _on_admin(self, query: dict, data: str, chat_id: int, message_id: int) -> None:
        if chat_id != self.settings.admin_chat_id:
            self.client.answer_callback(query["id"], "Not allowed")
            return
        _, status, raw_id = data.split(":")
        order = self.store.get(int(raw_id))
        if order is None:
            self.client.answer_callback(query["id"], "Order not found")
            return
        allowed = {"new": {"accepted", "cancelled"}, "accepted": {"ready", "cancelled"}}
        if status not in allowed.get(order.status, set()):
            self.client.answer_callback(query["id"], f"Order is already {order.status}")
            return
        order = self.store.set_status(order.id, status)
        self.client.edit_message(chat_id, message_id, texts.admin_order(order, self.menu),
                                 kb.admin_order(order.id, order.status))
        note = texts.customer_status(order)
        if note:
            self.client.send_message(order.chat_id, note)
        self.client.answer_callback(query["id"], texts.STATUS_LABELS[order.status])
