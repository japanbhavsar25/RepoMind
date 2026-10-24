"""In-memory database and storage repository for e-commerce entities."""

from typing import Dict, List, Optional
from models import Order, Product, User, PaymentTransaction


class DatabaseConnection:
    """Simulates a thread-safe database connection pool."""

    def __init__(self, connection_string: str = "sqlite:///:memory:"):
        self.connection_string = connection_string
        self.is_connected = False
        self._users: Dict[str, User] = {}
        self._products: Dict[str, Product] = {}
        self._orders: Dict[str, Order] = {}
        self._transactions: List[PaymentTransaction] = []

    def connect(self) -> bool:
        """Establish connection to data store."""
        self.is_connected = True
        return self.is_connected

    def disconnect(self) -> None:
        """Close connection pool."""
        self.is_connected = False

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Fetch user by primary key."""
        return self._users.get(user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Fetch user by unique email address."""
        for user in self._users.values():
            if user.email.lower() == email.lower():
                return user
        return None

    def save_user(self, user: User) -> None:
        """Insert or update user record."""
        self._users[user.id] = user

    def get_product(self, product_id: str) -> Optional[Product]:
        """Fetch product by ID."""
        return self._products.get(product_id)

    def save_product(self, product: Product) -> None:
        """Insert or update product."""
        self._products[product.id] = product

    def get_order(self, order_id: str) -> Optional[Order]:
        """Fetch order by ID."""
        return self._orders.get(order_id)

    def save_order(self, order: Order) -> None:
        """Insert or update order."""
        self._orders[order.id] = order

    def record_transaction(self, tx: PaymentTransaction) -> None:
        """Append payment transaction record."""
        self._transactions.append(tx)

    def get_transactions_for_order(self, order_id: str) -> List[PaymentTransaction]:
        """Return all transaction attempts for an order."""
        return [t for t in self._transactions if t.order_id == order_id]


# Global shared instance
db = DatabaseConnection()
