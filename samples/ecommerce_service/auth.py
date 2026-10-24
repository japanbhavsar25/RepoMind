"""Authentication and access control service."""

import secrets
import time
from typing import Optional
from database import db
from models import User, UserRole
from utils import hash_token, validate_email_format


class AuthenticationService:
    """Handles credentials verification and token issuance."""

    def __init__(self, token_expiry_seconds: int = 3600):
        self.token_expiry_seconds = token_expiry_seconds
        self._active_tokens = {}  # token_hash -> (user_id, expiry_timestamp)

    def register_user(self, email: str, password_plain: str, role: UserRole = UserRole.CUSTOMER) -> User:
        """Create and persist a new user account."""
        if not validate_email_format(email):
            raise ValueError(f"Invalid email address: {email}")
        
        if db.get_user_by_email(email):
            raise ValueError("User with this email already exists")

        user_id = f"usr_{secrets.token_hex(6)}"
        hashed_pw = hash_token(password_plain)
        user = User(id=user_id, email=email, hashed_password=hashed_pw, role=role)
        db.save_user(user)
        return user

    def authenticate(self, email: str, password_plain: str) -> Optional[str]:
        """Verify user credentials and return an API session token."""
        user = db.get_user_by_email(email)
        if not user or not user.is_active:
            return None

        expected_hash = hash_token(password_plain)
        if user.hashed_password != expected_hash:
            return None

        # Issue token
        raw_token = secrets.token_urlsafe(32)
        thash = hash_token(raw_token)
        expiry = time.time() + self.token_expiry_seconds
        self._active_tokens[thash] = (user.id, expiry)
        return raw_token

    def verify_token(self, token: str) -> Optional[User]:
        """Validate an API token and return the associated user if valid."""
        thash = hash_token(token)
        if thash not in self._active_tokens:
            return None

        user_id, expiry = self._active_tokens[thash]
        if time.time() > expiry:
            del self._active_tokens[thash]
            return None

        return db.get_user_by_id(user_id)

    def revoke_token(self, token: str) -> bool:
        """Invalidate an active session token."""
        thash = hash_token(token)
        if thash in self._active_tokens:
            del self._active_tokens[thash]
            return True
        return False
