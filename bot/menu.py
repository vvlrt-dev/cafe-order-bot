"""Menu model loaded from menu.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MenuItem:
    id: str
    name: str
    price: float
    description: str
    category_id: str


@dataclass(frozen=True)
class Category:
    id: str
    title: str
    items: tuple[MenuItem, ...]


class Menu:
    def __init__(self, cafe_name: str, currency: str, categories: list[Category]):
        self.cafe_name = cafe_name
        self.currency = currency
        self.categories = categories
        self._categories = {c.id: c for c in categories}
        self._items = {item.id: item for c in categories for item in c.items}

    @classmethod
    def load(cls, path: Path) -> "Menu":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        categories = []
        seen: set[str] = set()
        for raw_cat in data["categories"]:
            items = []
            for raw in raw_cat["items"]:
                if raw["id"] in seen:
                    raise ValueError(f"Duplicate menu item id: {raw['id']}")
                if float(raw["price"]) <= 0:
                    raise ValueError(f"Price must be positive: {raw['id']}")
                seen.add(raw["id"])
                items.append(
                    MenuItem(
                        id=raw["id"],
                        name=raw["name"],
                        price=float(raw["price"]),
                        description=raw.get("description", ""),
                        category_id=raw_cat["id"],
                    )
                )
            categories.append(Category(id=raw_cat["id"], title=raw_cat["title"], items=tuple(items)))
        return cls(data["cafe_name"], data.get("currency", "$"), categories)

    def category(self, category_id: str) -> Category | None:
        return self._categories.get(category_id)

    def item(self, item_id: str) -> MenuItem | None:
        return self._items.get(item_id)

    def money(self, amount: float) -> str:
        return f"{self.currency}{amount:,.2f}"
