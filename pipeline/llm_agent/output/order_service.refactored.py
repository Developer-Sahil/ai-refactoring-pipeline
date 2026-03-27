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
        Creates a new order for a given customer with specified items.

        This method calculates the subtotal, tax, and total for the order,
        persists it to the database, and logs the creation.

        Args:
            customer_id: The unique identifier of the customer placing the order.
            items: A list of `OrderItem` objects included in the order.

        Returns:
            A dictionary representing the created and persisted order,
            including its newly generated `order_id`.
        """
        subtotal = self._calculate_subtotal(items)
        tax = round(subtotal * self.tax_rate, 2)
        total = round(subtotal + tax, 2)

        order = {
            "customer_id": customer_id,
            "items": [vars(i) for i in items],
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
            "status": "pending",
        }
        order_id = self.db.insert("orders", order)
        logger.info("Created order %s for customer %s (total: $%.2f)", order_id, customer_id, total)
        return {**order, "order_id": order_id}

    def _calculate_subtotal(self, items: list['OrderItem']) -> float:
        """
        Calculate the total subtotal for a list of order items.

        This method computes the extended price (quantity * unit_price) for each
        item in the provided list and then sums these extended prices. The final
        sum is rounded to two decimal places, which is appropriate for currency
        calculations.

        Args:
            items: A list of `OrderItem` objects. Each object is expected to have
                   `quantity` and `unit_price` attributes.

        Returns:
            The total subtotal as a float, rounded to two decimal places.
        """
        return round(sum(item.quantity * item.unit_price for item in items), 2)

    def cancel_order(self, order_id: str, reason: Optional[str] = None) -> bool:
        """
        Cancel an existing order by its ID.

        Attempts to change the status of an order to 'cancelled'. An order
        cannot be cancelled if it has already been shipped.

        Args:
            order_id: The unique identifier of the order to be cancelled.
            reason: An optional string explaining the reason for the cancellation.

        Returns:
            True if the order was successfully cancelled.
            False if the order could not be cancelled because it was already shipped.

        Raises:
            ValueError: If an order with the specified `order_id` is not found.
        """
        order = self.db.find_one("orders", {"order_id": order_id})

        if not order:
            raise ValueError(f"Order {order_id} not found")

        if order["status"] == "shipped":
            logger.warning("Cannot cancel shipped order %s", order_id)
            return False

        self.db.update(
            "orders",
            {"order_id": order_id},
            {"status": "cancelled", "cancel_reason": reason}
        )
        return True

    @staticmethod
    def format_receipt(order: dict) -> str:
        """
        Generate a plain-text receipt string for a given order.

        Args:
            order: A dictionary representing the order, expected to contain:
                   - 'order_id': A unique identifier for the order (e.g., str or int).
                   - 'items': A list of dictionaries, where each item dictionary
                              contains 'product_id' (str), 'quantity' (int),
                              and 'unit_price' (float).
                   - 'subtotal': The calculated subtotal for all items (float).
                   - 'tax': The calculated tax amount (float).
                   - 'total': The grand total for the order (float).

        Returns:
            A multi-line string formatted as a plain-text receipt.
        """
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
    Validates a list of order items for common data integrity issues.

    Checks each order item to ensure its quantity is positive,
    unit price is non-negative, and product ID is provided.

    Args:
        items: A list of `OrderItem` objects to be validated.

    Returns:
        A list of strings, where each string is a validation error message.
        The list is empty if all order items are valid according to the rules.
    """
    MIN_REQUIRED_QUANTITY = 1  # Quantity must be strictly greater than 0
    MIN_ALLOWED_UNIT_PRICE = 0  # Unit price must be greater than or equal to 0

    validation_errors: list[str] = []
    for index, item in enumerate(items):
        if item.quantity < MIN_REQUIRED_QUANTITY:
            validation_errors.append(f"Item {index}: quantity must be positive")
        if item.unit_price < MIN_ALLOWED_UNIT_PRICE:
            validation_errors.append(f"Item {index}: unit_price cannot be negative")
        if not item.product_id.strip():
            validation_errors.append(f"Item {index}: product_id is required")
    return validation_errors


async def fetch_product_prices(product_ids: list[str], pricing_api) -> dict[str, float]:
    """
    Asynchronously fetches current prices for a list of product identifiers.

    This function interacts with an external pricing API to retrieve the latest price
    for each product specified by its ID. Only products for which pricing data
    is successfully retrieved will be included in the returned dictionary.

    Args:
        product_ids: A list of unique product identifiers (strings) for which
                     prices are to be fetched.
        pricing_api: An asynchronous API client object with a `batch_get` method.
                     This method should accept a list of product IDs and return
                     a dictionary mapping product IDs to their raw pricing data.
                     For example, `{"product_id_1": {"price": 10.99, "currency": "USD"}}`.

    Returns:
        A dictionary where keys are product identifiers (str) and values are
        their corresponding prices (float). If a product ID from the input
        list is not found in the API response or its price cannot be extracted,
        it will be omitted from the returned dictionary.

    Raises:
        Exception: Any exception raised by `pricing_api.batch_get` (e.g.,
                   network errors, API authentication failures) will propagate
                   upwards.
    """
    # Asynchronously call the pricing API to get batch results for all product IDs.
    api_response = await pricing_api.batch_get(product_ids)

    # Build a dictionary of product IDs to their prices,
    # including only those products for which valid price data was returned.
    extracted_prices = {
        product_id: api_response[product_id]["price"]
        for product_id in product_ids
        if product_id in api_response and "price" in api_response[product_id]
    }
    return extracted_prices
