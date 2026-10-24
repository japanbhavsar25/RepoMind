"""Customer notification dispatch service."""

import logging
from typing import Optional
from models import Order
from utils import format_currency

logger = logging.getLogger("notifications")


class NotificationService:
    """Dispatches order confirmations and alerts to customers."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.sent_messages = []

    def send_order_confirmation(self, customer_email: str, order: Order, total_with_tax: int) -> bool:
        """Render and send an order confirmation email."""
        formatted_total = format_currency(total_with_tax)
        subject = f"Order Confirmation #{order.id}"
        body = (
            f"Thank you for your order!\n"
            f"Order ID: {order.id}\n"
            f"Items: {len(order.items)}\n"
            f"Total Paid: {formatted_total}\n"
        )
        return self._dispatch(customer_email, subject, body)

    def send_shipping_update(self, customer_email: str, order_id: str, tracking_number: str) -> bool:
        """Send tracking details for a shipped order."""
        subject = f"Your order #{order_id} has shipped!"
        body = f"Track your package with tracking number: {tracking_number}"
        return self._dispatch(customer_email, subject, body)

    def _dispatch(self, recipient: str, subject: str, message: str) -> bool:
        """Internal dispatch mock."""
        payload = {"to": recipient, "subject": subject, "body": message}
        self.sent_messages.append(payload)
        logger.info("Sent notification to %s: %s", recipient, subject)
        return True
