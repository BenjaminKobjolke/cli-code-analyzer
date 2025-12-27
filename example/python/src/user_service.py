"""
Sample Python module demonstrating a user service.
This file intentionally exceeds 300 lines to demonstrate the code analyzer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import json
import hashlib
import re


class UserRole(Enum):
    """User role enumeration."""
    GUEST = "guest"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class UserStatus(Enum):
    """User account status."""
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


@dataclass
class Address:
    """User address information."""
    street: str
    city: str
    state: str
    postal_code: str
    country: str

    def to_dict(self) -> Dict[str, str]:
        """Convert address to dictionary."""
        return {
            "street": self.street,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "Address":
        """Create address from dictionary."""
        return cls(
            street=data.get("street", ""),
            city=data.get("city", ""),
            state=data.get("state", ""),
            postal_code=data.get("postal_code", ""),
            country=data.get("country", ""),
        )


@dataclass
class UserProfile:
    """Extended user profile information."""
    bio: str = ""
    avatar_url: str = ""
    website: str = ""
    social_links: Dict[str, str] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary."""
        return {
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "website": self.website,
            "social_links": self.social_links,
            "preferences": self.preferences,
        }


@dataclass
class User:
    """Main user data class."""
    id: str
    username: str
    email: str
    password_hash: str
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.PENDING
    profile: UserProfile = field(default_factory=UserProfile)
    address: Optional[Address] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "status": self.status.value,
            "profile": self.profile.to_dict(),
            "address": self.address.to_dict() if self.address else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class ValidationError(Exception):
    """Custom validation error."""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class UserNotFoundError(Exception):
    """Raised when user is not found."""
    pass


class DuplicateUserError(Exception):
    """Raised when attempting to create duplicate user."""
    pass


class UserService:
    """Service class for user management operations."""

    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_]{3,30}$')
    PASSWORD_MIN_LENGTH = 8

    def __init__(self):
        """Initialize user service with empty storage."""
        self._users: Dict[str, User] = {}
        self._email_index: Dict[str, str] = {}
        self._username_index: Dict[str, str] = {}

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        """
        Create a new user account.

        Args:
            username: Unique username
            email: User email address
            password: Plain text password (will be hashed)
            role: User role (default: USER)

        Returns:
            Created User object

        Raises:
            ValidationError: If validation fails
            DuplicateUserError: If username or email already exists
        """
        # Validate input
        self._validate_username(username)
        self._validate_email(email)
        self._validate_password(password)

        # Check for duplicates
        if username.lower() in self._username_index:
            raise DuplicateUserError(f"Username '{username}' already exists")
        if email.lower() in self._email_index:
            raise DuplicateUserError(f"Email '{email}' already registered")

        # Create user
        user_id = self._generate_user_id()
        password_hash = self._hash_password(password)

        user = User(
            id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            status=UserStatus.PENDING,
        )

        # Store user
        self._users[user_id] = user
        self._email_index[email.lower()] = user_id
        self._username_index[username.lower()] = user_id

        return user

    def get_user_by_id(self, user_id: str) -> User:
        """Get user by ID."""
        if user_id not in self._users:
            raise UserNotFoundError(f"User with ID '{user_id}' not found")
        return self._users[user_id]

    def get_user_by_email(self, email: str) -> User:
        """Get user by email address."""
        email_lower = email.lower()
        if email_lower not in self._email_index:
            raise UserNotFoundError(f"User with email '{email}' not found")
        user_id = self._email_index[email_lower]
        return self._users[user_id]

    def get_user_by_username(self, username: str) -> User:
        """Get user by username."""
        username_lower = username.lower()
        if username_lower not in self._username_index:
            raise UserNotFoundError(f"User with username '{username}' not found")
        user_id = self._username_index[username_lower]
        return self._users[user_id]

    def update_user(
        self,
        user_id: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
        profile: Optional[UserProfile] = None,
        address: Optional[Address] = None,
    ) -> User:
        """
        Update user information.

        Args:
            user_id: ID of user to update
            username: New username (optional)
            email: New email (optional)
            profile: New profile data (optional)
            address: New address data (optional)

        Returns:
            Updated User object
        """
        user = self.get_user_by_id(user_id)

        if username is not None and username != user.username:
            self._validate_username(username)
            if username.lower() in self._username_index:
                raise DuplicateUserError(f"Username '{username}' already exists")
            del self._username_index[user.username.lower()]
            self._username_index[username.lower()] = user_id
            user.username = username

        if email is not None and email != user.email:
            self._validate_email(email)
            if email.lower() in self._email_index:
                raise DuplicateUserError(f"Email '{email}' already registered")
            del self._email_index[user.email.lower()]
            self._email_index[email.lower()] = user_id
            user.email = email

        if profile is not None:
            user.profile = profile

        if address is not None:
            user.address = address

        user.updated_at = datetime.now()
        return user

    def delete_user(self, user_id: str) -> None:
        """Delete user by ID."""
        user = self.get_user_by_id(user_id)
        del self._username_index[user.username.lower()]
        del self._email_index[user.email.lower()]
        del self._users[user_id]

    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str,
    ) -> None:
        """Change user password."""
        user = self.get_user_by_id(user_id)

        if not self._verify_password(old_password, user.password_hash):
            raise ValidationError("password", "Current password is incorrect")

        self._validate_password(new_password)
        user.password_hash = self._hash_password(new_password)
        user.updated_at = datetime.now()

    def authenticate(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user with email and password.

        Returns:
            User object if authentication successful, None otherwise
        """
        try:
            user = self.get_user_by_email(email)
        except UserNotFoundError:
            return None

        if user.status != UserStatus.ACTIVE:
            return None

        if not self._verify_password(password, user.password_hash):
            return None

        user.last_login = datetime.now()
        return user

    def activate_user(self, user_id: str) -> User:
        """Activate a pending user account."""
        user = self.get_user_by_id(user_id)
        if user.status != UserStatus.PENDING:
            raise ValidationError("status", "User is not in pending status")
        user.status = UserStatus.ACTIVE
        user.updated_at = datetime.now()
        return user

    def suspend_user(self, user_id: str) -> User:
        """Suspend a user account."""
        user = self.get_user_by_id(user_id)
        user.status = UserStatus.SUSPENDED
        user.updated_at = datetime.now()
        return user

    def change_role(self, user_id: str, new_role: UserRole) -> User:
        """Change user role."""
        user = self.get_user_by_id(user_id)
        user.role = new_role
        user.updated_at = datetime.now()
        return user

    def list_users(
        self,
        role: Optional[UserRole] = None,
        status: Optional[UserStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[User]:
        """
        List users with optional filtering.

        Args:
            role: Filter by role
            status: Filter by status
            limit: Maximum number of users to return
            offset: Number of users to skip

        Returns:
            List of User objects
        """
        users = list(self._users.values())

        if role is not None:
            users = [u for u in users if u.role == role]

        if status is not None:
            users = [u for u in users if u.status == status]

        users.sort(key=lambda u: u.created_at, reverse=True)
        return users[offset:offset + limit]

    def search_users(self, query: str) -> List[User]:
        """Search users by username or email."""
        query_lower = query.lower()
        results = []

        for user in self._users.values():
            if (query_lower in user.username.lower() or
                query_lower in user.email.lower()):
                results.append(user)

        return results

    def get_user_count(self) -> int:
        """Get total number of users."""
        return len(self._users)

    def get_active_user_count(self) -> int:
        """Get number of active users."""
        return sum(1 for u in self._users.values() if u.status == UserStatus.ACTIVE)

    def export_users_json(self) -> str:
        """Export all users as JSON."""
        users_data = [user.to_dict() for user in self._users.values()]
        return json.dumps(users_data, indent=2)

    def _validate_username(self, username: str) -> None:
        """Validate username format."""
        if not self.USERNAME_REGEX.match(username):
            raise ValidationError(
                "username",
                "Username must be 3-30 characters, alphanumeric and underscores only"
            )

    def _validate_email(self, email: str) -> None:
        """Validate email format."""
        if not self.EMAIL_REGEX.match(email):
            raise ValidationError("email", "Invalid email format")

    def _validate_password(self, password: str) -> None:
        """Validate password strength."""
        if len(password) < self.PASSWORD_MIN_LENGTH:
            raise ValidationError(
                "password",
                f"Password must be at least {self.PASSWORD_MIN_LENGTH} characters"
            )
        if not any(c.isupper() for c in password):
            raise ValidationError("password", "Password must contain uppercase letter")
        if not any(c.islower() for c in password):
            raise ValidationError("password", "Password must contain lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValidationError("password", "Password must contain a digit")

    def _generate_user_id(self) -> str:
        """Generate unique user ID."""
        import uuid
        return str(uuid.uuid4())

    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        return self._hash_password(password) == password_hash
