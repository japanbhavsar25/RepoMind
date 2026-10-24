"""Data models and entities for the e-commerce microservice."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"


class UserRole(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    SUPPORT = "support"


@dataclass
class User:
    """Represents a customer or admin account."""
    id: str
    email: str
    hashed_password: str
    role: UserRole = UserRole.CUSTOMER
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_admin(self) -> bool:
        """Check if the user has administrative privileges."""
        return self.role == UserRole.ADMIN and self.is_active


@dataclass
class Product:
    """Represents an item in the product catalog."""
    id: str
    name: str
    price_cents: int
    stock_quantity: int
    sku: str
    description: Optional[str] = None

    def is_in_stock(self, quantity: int = 1) -> bool:
        """Check if sufficient quantity is available."""
        return self.stock_quantity >= quantity


@dataclass
class OrderItem:
    """An individual line item within an order."""
    product_id: str
    quantity: int
    unit_price_cents: int

    @property
    def total_cents(self) -> int:
        """Calculate line item total."""
        return self.quantity * self.unit_price_cents


@dataclass
class Order:
    """A customer purchase order."""
    id: str
    user_id: str
    items: List[OrderItem]
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    shipping_address: str = ""

    def subtotal_cents(self) -> int:
        """Calculate total before taxes and discounts."""
        return sum(item.total_cents for item in self.items)


@dataclass
class PaymentTransaction:
    """Record of a payment attempt."""
    transaction_id: str
    order_id: str
    amount_cents: int
    provider: str
    success: bool
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
