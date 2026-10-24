"""Utility functions for hashing, formatting, and calculations."""

import hashlib
import re
from typing import Any, Dict


def hash_token(token: str) -> str:
    """Generate a secure SHA-256 hash of an authentication token."""
    if not token:
        raise ValueError("Token cannot be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def format_currency(amount_cents: int, currency: str = "USD") -> str:
    """Format an integer amount in cents to a human-readable currency string."""
    dollars = amount_cents / 100.0
    return f"{currency} ${dollars:,.2f}"


def calculate_tax(subtotal_cents: int, tax_rate: float) -> int:
    """Calculate tax in cents given a subtotal and decimal tax rate."""
    if tax_rate < 0.0 or tax_rate > 1.0:
        raise ValueError("Tax rate must be between 0.0 and 1.0")
    return int(round(subtotal_cents * tax_rate))


def validate_email_format(email: str) -> bool:
    """Check if an email string conforms to standard email format."""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email.strip()))


def sanitize_dict_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively strip leading/trailing whitespace from dictionary keys."""
    cleaned = {}
    for k, v in data.items():
        clean_key = k.strip()
        if isinstance(v, dict):
            cleaned[clean_key] = sanitize_dict_keys(v)
        else:
            cleaned[clean_key] = v
    return cleaned
