"""Payment gateway integration and processing."""

import abc
import secrets
from datetime import datetime
from typing import Dict, Any
from models import PaymentTransaction
from database import db


class PaymentGateway(abc.ABC):
    """Abstract payment processor interface."""

    @abc.abstractmethod
    def charge(self, order_id: str, amount_cents: int, payment_token: str) -> PaymentTransaction:
        """Process a customer charge."""
        pass


class StripeAdapter(PaymentGateway):
    """Adapter for processing charges via Stripe API."""

    def __init__(self, api_key: str = "sk_test_mock_stripe"):
        self.api_key = api_key

    def charge(self, order_id: str, amount_cents: int, payment_token: str) -> PaymentTransaction:
        """Simulate Stripe payment charge."""
        tx_id = f"tx_str_{secrets.token_hex(8)}"
        
        # Test card failure condition
        if payment_token == "tok_fail":
            tx = PaymentTransaction(
                transaction_id=tx_id,
                order_id=order_id,
                amount_cents=amount_cents,
                provider="stripe",
                success=False,
                error_message="Card declined by issuer",
            )
        else:
            tx = PaymentTransaction(
                transaction_id=tx_id,
                order_id=order_id,
                amount_cents=amount_cents,
                provider="stripe",
                success=True,
                error_message=None,
            )
        db.record_transaction(tx)
        return tx


class PayPalAdapter(PaymentGateway):
    """Adapter for processing charges via PayPal."""

    def __init__(self, client_id: str = "client_mock_paypal"):
        self.client_id = client_id

    def charge(self, order_id: str, amount_cents: int, payment_token: str) -> PaymentTransaction:
        """Simulate PayPal checkout charge."""
        tx_id = f"tx_pp_{secrets.token_hex(8)}"
        tx = PaymentTransaction(
            transaction_id=tx_id,
            order_id=order_id,
            amount_cents=amount_cents,
            provider="paypal",
            success=True,
            error_message=None,
        )
        db.record_transaction(tx)
        return tx
