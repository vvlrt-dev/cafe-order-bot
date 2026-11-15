"""Shopping cart kept per user while they order."""

from __future__ import annotations

from dataclasses import dataclass, field

from .menu import Menu, MenuItem

MAX_QTY_PER_ITEM = 20


@dataclass
class CartLine:
    item: MenuItem
    qty: int

    @property
    def total(self) -> float:
        return round(self.item.price * self.qty, 2)


@dataclass
class Cart:
    quantities: dict[str, int] = field(default_factory=dict)

    def add(self, item_id: str, qty: int = 1) -> int:
        new_qty = min(self.quantities.get(item_id, 0) + qty, MAX_QTY_PER_ITEM)
        self.quantities[item_id] = new_qty
        return new_qty

    def remove(self, item_id: str, qty: int = 1) -> int:
        new_qty = self.quantities.get(item_id, 0) - qty
        if new_qty <= 0:
            self.quantities.pop(item_id, None)
            return 0
        self.quantities[item_id] = new_qty
        return new_qty

    def clear(self) -> None:
        self.quantities.clear()

    @property
    def count(self) -> int:
        return sum(self.quantities.values())

    def is_empty(self) -> bool:
        return not self.quantities

    def lines(self, menu: Menu) -> list[CartLine]:
        """Cart lines in menu order; items no longer on the menu are dropped."""
        lines = []
        for category in menu.categories:
            for item in category.items:
                qty = self.quantities.get(item.id)
                if qty:
                    lines.append(CartLine(item, qty))
        return lines

    def total(self, menu: Menu) -> float:
        return round(sum(line.total for line in self.lines(menu)), 2)
