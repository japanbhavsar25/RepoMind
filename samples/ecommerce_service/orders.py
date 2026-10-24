"""Order management and checkout processing."""

import secrets
from typing import List, Optional
from models import Order, OrderItem, OrderStatus, Product
from database import db
from payments import PaymentGateway, StripeAdapter
from notifications import NotificationService
from utils import calculate_tax


class OrderProcessingError(Exception):
    """Raised when an order fails business rule validation or payment."""
    pass


class OrderService:
    """Orchestrates order creation, inventory reservation, and checkout."""

    def __init__(
        self,
        payment_gateway: Optional[PaymentGateway] = None,
        notification_service: Optional[NotificationService] = None,
        tax_rate: float = 0.08,
    ):
        self.payment_gateway = payment_gateway or StripeAdapter()
        self.notification_service = notification_service or NotificationService()
        self.tax_rate = tax_rate

    def create_order(self, user_id: str, items: List[OrderItem], shipping_address: str) -> Order:
        """Create a new pending order and validate stock."""
        if not items:
            raise OrderProcessingError("Cannot create an empty order")

        # Verify inventory
        for item in items:
            product = db.get_product(item.product_id)
            if not product:
                raise OrderProcessingError(f"Product {item.product_id} not found")
            if not product.is_in_stock(item.quantity):
                raise OrderProcessingError(f"Insufficient stock for {product.name}")

        order_id = f"ord_{secrets.token_hex(6)}"
        order = Order(
            id=order_id,
            user_id=user_id,
            items=items,
            status=OrderStatus.PENDING,
            shipping_address=shipping_address,
        )
        db.save_order(order)
        return order

    def checkout(self, order_id: str, customer_email: str, payment_token: str) -> bool:
        """Execute payment and finalize the order."""
        order = db.get_order(order_id)
        if not order:
            raise OrderProcessingError(f"Order {order_id} not found")

        if order.status != OrderStatus.PENDING:
            raise OrderProcessingError(f"Order {order_id} cannot be checked out (status: {order.status})")

        subtotal = order.subtotal_cents()
        tax = calculate_tax(subtotal, self.tax_rate)
        total = subtotal + tax

        # Charge via payment gateway
        tx = self.payment_gateway.charge(order.id, total, payment_token)
        if not tx.success:
            order.status = OrderStatus.CANCELLED
            db.save_order(order)
            raise OrderProcessingError(f"Payment failed: {tx.error_message}")

        # Deduct inventory
        for item in order.items:
            product = db.get_product(item.product_id)
            if product:
                product.stock_quantity -= item.quantity
                db.save_product(product)

        order.status = OrderStatus.PAID
        db.save_order(order)

        # Notify customer
        self.notification_service.send_order_confirmation(customer_email, order, total)
        return True
