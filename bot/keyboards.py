"""Inline and reply keyboards. Callback data stays well under Telegram's 64-byte limit."""

from __future__ import annotations

from datetime import datetime

from .cart import Cart
from .menu import Category, Menu


def _button(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data}


def _inline(rows: list[list[dict]]) -> dict:
    return {"inline_keyboard": rows}


def cart_label(cart: Cart, menu: Menu) -> str:
    return f"🛒 Cart · {menu.money(cart.total(menu))}" if cart.count else "🛒 Cart"


def home(cart: Cart, menu: Menu) -> dict:
    return _inline([[_button("🍽 Menu", "menu"), _button(cart_label(cart, menu), "cart")]])


def categories(menu: Menu, cart: Cart) -> dict:
    rows = [[_button(c.title, f"cat:{c.id}")] for c in menu.categories]
    rows.append([_button(cart_label(cart, menu), "cart")])
    return _inline(rows)


def category_items(category: Category, menu: Menu, cart: Cart) -> dict:
    rows = []
    for item in category.items:
        qty = cart.quantities.get(item.id, 0)
        badge = f" ({qty})" if qty else ""
        rows.append([_button(f"➕ {item.name} · {menu.money(item.price)}{badge}", f"add:{item.id}")])
    rows.append([_button("⬅ Categories", "menu"), _button(cart_label(cart, menu), "cart")])
    return _inline(rows)


def cart_view(cart: Cart, menu: Menu) -> dict:
    rows = []
    for line in cart.lines(menu):
        rows.append([
            _button("➖", f"dec:{line.item.id}"),
            _button(f"{line.item.name} × {line.qty}", "noop"),
            _button("➕", f"inc:{line.item.id}"),
        ])
    if rows:
        rows.append([_button("🧹 Clear", "clear"), _button("✅ Checkout", "checkout")])
    rows.append([_button("⬅ Menu", "menu")])
    return _inline(rows)


def cancel_checkout() -> dict:
    return _inline([[_button("✖ Cancel checkout", "cancel")]])


def share_phone() -> dict:
    return {
        "keyboard": [[{"text": "📱 Share my phone number", "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
        "input_field_placeholder": "+998 90 123 45 67",
    }


def remove_reply_keyboard() -> dict:
    return {"remove_keyboard": True}


def pickup_slots(slots: list[datetime]) -> dict:
    row = [_button(s.strftime("%H:%M"), f"slot:{s:%H%M}") for s in slots]
    rows = [row[i:i + 2] for i in range(0, len(row), 2)]
    rows.append([_button("✖ Cancel checkout", "cancel")])
    return _inline(rows)


def confirm_order() -> dict:
    return _inline([[_button("✅ Confirm order", "confirm"), _button("✖ Cancel", "cancel")]])


def admin_order(order_id: int, status: str) -> dict | None:
    if status == "new":
        return _inline([[_button("👍 Accept", f"adm:accepted:{order_id}"), _button("✖ Cancel", f"adm:cancelled:{order_id}")]])
    if status == "accepted":
        return _inline([[_button("🍽 Ready for pickup", f"adm:ready:{order_id}"), _button("✖ Cancel", f"adm:cancelled:{order_id}")]])
    return None
