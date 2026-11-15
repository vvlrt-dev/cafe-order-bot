"""Message texts. All user-provided values are HTML-escaped before they reach Telegram."""

from __future__ import annotations

from datetime import time
from html import escape

from .cart import Cart
from .menu import Category, Menu
from .storage import Order

STATUS_LABELS = {
    "new": "🆕 New",
    "accepted": "👍 Accepted",
    "ready": "🍽 Ready for pickup",
    "cancelled": "✖ Cancelled",
}


def welcome(menu: Menu, opens_at: time, closes_at: time) -> str:
    return (
        f"<b>{escape(menu.cafe_name)}</b>\n"
        "Order plov, samsa and drinks for pickup.\n"
        f"Open daily {opens_at:%H:%M}–{closes_at:%H:%M}. Pay when you collect."
    )


def help_text() -> str:
    return (
        "/menu — browse the menu\n"
        "/cart — see your cart\n"
        "/cancel — cancel checkout\n"
        "/start — main screen"
    )


def categories() -> str:
    return "Choose a category:"


def category(cat: Category, menu: Menu) -> str:
    lines = [f"<b>{escape(cat.title)}</b>", ""]
    for item in cat.items:
        lines.append(f"<b>{escape(item.name)}</b> — {menu.money(item.price)}")
        if item.description:
            lines.append(f"<i>{escape(item.description)}</i>")
    lines += ["", "Tap an item to add it to your cart."]
    return "\n".join(lines)


def cart(cart: Cart, menu: Menu) -> str:
    lines = cart.lines(menu)
    if not lines:
        return "Your cart is empty. Open the menu to add something."
    body = [f"{line.qty} × {escape(line.item.name)} — {menu.money(line.total)}" for line in lines]
    return "<b>Your cart</b>\n\n" + "\n".join(body) + f"\n\n<b>Total: {menu.money(cart.total(menu))}</b>"


def ask_name() -> str:
    return "<b>Step 1 of 3.</b> What name should we put on the order?"


def ask_phone() -> str:
    return "<b>Step 2 of 3.</b> Your phone number? Tap the button below or type it."


def phone_saved() -> str:
    return "Thanks, number saved."


def ask_time(earliest: str) -> str:
    return (
        "<b>Step 3 of 3.</b> When will you pick it up?\n"
        f"Choose a time or type one as HH:MM (earliest {earliest})."
    )


def closed_today(opens_at: time, closes_at: time) -> str:
    return (
        f"We're closed for today. Orders can be placed for {opens_at:%H:%M}–{closes_at:%H:%M}. "
        "Your cart is saved — come back tomorrow."
    )


def order_lines(items: list[dict], menu: Menu) -> str:
    return "\n".join(f"{i['qty']} × {escape(i['name'])} — {menu.money(i['total'])}" for i in items)


def summary(items: list[dict], total: float, name: str, phone: str, pickup: str, menu: Menu) -> str:
    return (
        "<b>Check your order</b>\n\n"
        f"{order_lines(items, menu)}\n\n"
        f"<b>Total: {menu.money(total)}</b>\n"
        f"Name: {escape(name)}\n"
        f"Phone: {escape(phone)}\n"
        f"Pickup today at {pickup}"
    )


def order_confirmed(order: Order, menu: Menu) -> str:
    return (
        f"✅ <b>Order #{order.id} received</b>\n\n"
        f"{order_lines(order.items, menu)}\n\n"
        f"<b>Total: {menu.money(order.total)}</b> · pay at pickup\n"
        f"Pickup today at {order.pickup_at:%H:%M}. We'll message you when it's ready."
    )


def admin_order(order: Order, menu: Menu) -> str:
    return (
        f"<b>Order #{order.id}</b> · {STATUS_LABELS[order.status]}\n\n"
        f"{order_lines(order.items, menu)}\n\n"
        f"<b>Total: {menu.money(order.total)}</b>\n"
        f"Customer: {escape(order.name)}\n"
        f"Phone: {escape(order.phone)}\n"
        f"Pickup: {order.pickup_at:%H:%M}\n"
        f"Placed: {order.created_at:%Y-%m-%d %H:%M}"
    )


def customer_status(order: Order) -> str | None:
    return {
        "accepted": f"👍 Order #{order.id} is accepted and being prepared.",
        "ready": f"🍽 Order #{order.id} is ready! See you at the counter.",
        "cancelled": f"✖ Sorry, order #{order.id} was cancelled by the cafe. Please call us if you have questions.",
    }.get(order.status)


def checkout_cancelled() -> str:
    return "Checkout cancelled. Your cart is still saved."


def empty_cart_alert() -> str:
    return "Your cart is empty"


def use_buttons() -> str:
    return "Please use the buttons below, or /help for commands."
