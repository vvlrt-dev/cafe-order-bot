import json

import pytest

from bot.cart import MAX_QTY_PER_ITEM, Cart
from bot.menu import Menu


def test_menu_loads_categories_and_items(menu):
    assert [c.id for c in menu.categories] == ["mains", "bakery", "drinks"]
    assert menu.item("plov").price == 9.5
    assert menu.item("plov").category_id == "mains"
    assert menu.item("missing") is None


def test_menu_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "menu.json"
    path.write_text(json.dumps({"cafe_name": "X", "categories": [
        {"id": "a", "title": "A", "items": [{"id": "x", "name": "X", "price": 1}]},
        {"id": "b", "title": "B", "items": [{"id": "x", "name": "Y", "price": 2}]},
    ]}))
    with pytest.raises(ValueError, match="Duplicate"):
        Menu.load(path)


def test_cart_totals_follow_menu_prices(menu):
    cart = Cart()
    cart.add("plov", 2)
    cart.add("samsa")
    assert cart.count == 3
    assert cart.total(menu) == 22.0
    assert [(l.item.id, l.qty) for l in cart.lines(menu)] == [("plov", 2), ("samsa", 1)]


def test_cart_remove_drops_line_at_zero():
    cart = Cart()
    cart.add("plov")
    assert cart.remove("plov") == 0
    assert cart.is_empty()
    assert cart.remove("plov") == 0


def test_cart_caps_quantity():
    cart = Cart()
    cart.add("plov", 50)
    assert cart.quantities["plov"] == MAX_QTY_PER_ITEM


def test_cart_ignores_items_removed_from_menu(menu):
    cart = Cart({"plov": 1, "old_item": 3})
    assert cart.total(menu) == 9.5
    assert len(cart.lines(menu)) == 1
