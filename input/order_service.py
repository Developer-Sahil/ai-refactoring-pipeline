"""
order_service.py
~~~~~~~~~~~~~~~~
Example Python module for cAST chunking demonstration.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

TAX_RATE = 0.08


@dataclass
class OrderItem:
    """A single line-item within an order."""
    product_id: str
    quantity: int
    unit_price: float


class OrderService:
    """Handles order creation, pricing, and lifecycle management."""

    def __init__(self, db_conn, tax_rate: float = TAX_RATE):
        self.db = db_conn
        self.tax_rate = tax_rate
        self._cache: dict[str, float] = {}

    def create_order(self, customer_id: str, items: list[OrderItem]) -> dict:
        """
        Create a new order for *customer_id* containing *items*.

        Returns the persisted order document.
        """
        subtotal = self._calculate_subtotal(items)
        tax      = round(subtotal * self.tax_rate, 2)
        total    = round(subtotal + tax, 2)

        order = {
            "customer_id": customer_id,
            "items":       [vars(i) for i in items],
            "subtotal":    subtotal,
            "tax":         tax,
            "total":       total,
            "status":      "pending",
        }
        order_id = self.db.insert("orders", order)
        logger.info("Created order %s for customer %s (total: $%.2f)", order_id, customer_id, total)
        return {**order, "order_id": order_id}

    def _calculate_subtotal(self, items: list[OrderItem]) -> float:
        """Sum the price of all line items."""
        return round(sum(i.quantity * i.unit_price for i in items), 2)

    def cancel_order(self, order_id: str, reason: Optional[str] = None) -> bool:
        """Cancel an existing order.  Returns True on success."""
        order = self.db.find_one("orders", {"order_id": order_id})
        if not order:
            raise ValueError(f"Order {order_id} not found")
        if order["status"] == "shipped":
            logger.warning("Cannot cancel shipped order %s", order_id)
            return False
        self.db.update("orders", {"order_id": order_id}, {"status": "cancelled", "cancel_reason": reason})
        return True

    @staticmethod
    def format_receipt(order: dict) -> str:
        """Render a plain-text receipt string for *order*."""
        lines = [f"Order #{order['order_id']}", "-" * 40]
        for item in order["items"]:
            lines.append(f"  {item['product_id']} x{item['quantity']}  ${item['unit_price']:.2f}")
        lines += [
            "-" * 40,
            f"  Subtotal : ${order['subtotal']:.2f}",
            f"  Tax      : ${order['tax']:.2f}",
            f"  TOTAL    : ${order['total']:.2f}",
        ]
        return "\n".join(lines)


def validate_order_items(items: list[OrderItem]) -> list[str]:
    """
    Validate a list of order items.

    Returns a list of validation error messages (empty list = valid).
    """
    errors: list[str] = []
    for i, item in enumerate(items):
        if item.quantity <= 0:
            errors.append(f"Item {i}: quantity must be positive")
        if item.unit_price < 0:
            errors.append(f"Item {i}: unit_price cannot be negative")
        if not item.product_id.strip():
            errors.append(f"Item {i}: product_id is required")
    return errors


async def fetch_product_prices(product_ids: list[str], pricing_api) -> dict[str, float]:
    """Asynchronously fetch current prices for all *product_ids*."""
    results = await pricing_api.batch_get(product_ids)
    return {pid: results[pid]["price"] for pid in product_ids if pid in results}
