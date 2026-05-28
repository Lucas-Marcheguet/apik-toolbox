from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import secrets


class UserSession:
    """Manages user session data and expiration."""
    
    def __init__(self, user_id: str, username: str, session_token: Optional[str] = None):
        self.user_id = user_id
        self.username = username
        self.session_token = session_token or secrets.token_urlsafe(32)
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()

    def is_valid(self) -> bool:
        return True

    def update_activity(self) -> None:
        self.last_activity = datetime.utcnow()


class UserAuthService:
    """Service to handle user authentication and session management."""
    
    def __init__(self):
        self.sessions: Dict[str, UserSession] = {}
        self.users: Dict[str, Dict[str, Any]] = {}
        self.oauth_users: Dict[str, str] = {}  # "{provider}:{provider_id}" -> user_id
    
    def register_user(self, username: str, password: str, email: str) -> Dict[str, Any]:
        """Register a new user."""
        if username in self.users:
            raise ValueError("Username already exists")
        
        user_id = secrets.token_urlsafe(16)
        password_hash = self._hash_password(password)
        
        self.users[username] = {
            "user_id": user_id,
            "username": username,
            "password_hash": password_hash,
            "email": email,
            "created_at": datetime.utcnow()
        }
        
        return {"user_id": user_id, "username": username, "email": email}
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user and create session."""
        if username not in self.users:
            raise ValueError("Invalid credentials")
        
        user = self.users[username]
        if not self._verify_password(password, user["password_hash"]):
            raise ValueError("Invalid credentials")
        
        session = UserSession(user["user_id"], username)
        self.sessions[session.session_token] = session
        
        return {
            "session_token": session.session_token,
            "user_id": user["user_id"],
            "username": username
        }
    
    def create_oauth_session(self, provider: str, provider_id: str, username: str, email: str) -> Dict[str, Any]:
        """Get or create a user via OAuth provider and return a new session."""
        key = f"{provider}:{provider_id}"
        if key in self.oauth_users:
            user_id = self.oauth_users[key]
            user = next((u for u in self.users.values() if u["user_id"] == user_id), None)
            resolved_username = user["username"] if user else username
        else:
            # Ensure username is unique
            candidate = username
            if candidate in self.users:
                candidate = f"{username}_{provider_id}"
            user_id = secrets.token_urlsafe(16)
            self.users[candidate] = {
                "user_id": user_id,
                "username": candidate,
                "password_hash": None,
                "email": email,
                "created_at": datetime.utcnow(),
            }
            self.oauth_users[key] = user_id
            resolved_username = candidate
        session = UserSession(user_id, resolved_username)
        self.sessions[session.session_token] = session
        return {
            "session_token": session.session_token,
            "user_id": user_id,
            "username": resolved_username,
        }

    def logout(self, session_token: str) -> bool:
        """Terminate user session."""
        if session_token in self.sessions:
            del self.sessions[session_token]
            return True
        return False
    
    def validate_session(self, session_token: str) -> Optional[UserSession]:
        """Validate and retrieve session if valid."""
        if session_token not in self.sessions:
            return None
        
        session = self.sessions[session_token]
        if not session.is_valid():
            del self.sessions[session_token]
            return None
        
        session.update_activity()
        return session
    
    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
        return f"{salt}:{key.hex()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        salt, key_hex = password_hash.split(":", 1)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
        return secrets.compare_digest(key.hex(), key_hex)


auth_service = UserAuthService()


class OAuthStateStore:
    """Short-lived server-side store for OAuth CSRF state tokens."""

    def __init__(self, ttl_seconds: int = 600):
        self._states: Dict[str, datetime] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def generate(self) -> str:
        state = secrets.token_urlsafe(16)
        self._states[state] = datetime.utcnow() + self._ttl
        self._purge_expired()
        return state

    def consume(self, state: str) -> bool:
        """Validate and remove state in one step. Returns True if valid."""
        expires_at = self._states.pop(state, None)
        if expires_at is None:
            return False
        return datetime.utcnow() < expires_at

    def _purge_expired(self) -> None:
        now = datetime.utcnow()
        expired = [k for k, exp in self._states.items() if exp <= now]
        for k in expired:
            del self._states[k]


oauth_state_store = OAuthStateStore()
