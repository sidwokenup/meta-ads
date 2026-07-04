"""
Session Manager

Stores per-user Telegram bot state in memory.
Each Telegram user ID maps to a UserSession object.

Stored per user:
  - profile_id   : AdsPower profile ID (e.g. "k1dvlyr0")
  - account_id   : Facebook ad account ID (e.g. "1559140139101704")
  - last_command : Last command issued
  - last_refresh : Timestamp of last data fetch

Session is in-memory only — resets when the bot restarts.
For persistence across restarts, extend with JSON/SQLite in a future phase.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class UserSession:
    """Per-user session state."""
    user_id: int
    profile_id: Optional[str] = None
    account_id: Optional[str] = None
    saved_profiles: list[str] = field(default_factory=list)
    saved_accounts: list[str] = field(default_factory=list)
    last_command: Optional[str] = None
    last_refresh: Optional[datetime] = None
    date_preset: str = "last_30d"
    menu_state: dict = field(default_factory=dict)

    def is_configured(self) -> bool:
        """True if both profile_id and account_id are set."""
        return bool(self.profile_id and self.account_id)

    def missing_config(self) -> str:
        """Return a message explaining what is missing."""
        if not self.profile_id and not self.account_id:
            return (
                "You need to configure your session first\\.\n\n"
                "1\\. Set your AdsPower profile:\n`/setprofile k1dvlyr0`\n\n"
                "2\\. Set your ad account:\n`/setaccount 1559140139101704`"
            )
        if not self.profile_id:
            return "AdsPower profile not set\\. Use `/setprofile <profile_id>`"
        return "Ad account not set\\. Use `/setaccount <account_id>`"

    def summary(self) -> str:
        """One-line session summary for /profile command."""
        profile = self.profile_id or "not set"
        account = self.account_id or "not set"
        preset = self.date_preset
        refresh = (
            self.last_refresh.strftime("%H:%M:%S") if self.last_refresh else "never"
        )
        saved_profiles = ", ".join(self.saved_profiles) if self.saved_profiles else "none"
        saved_accounts = ", ".join(self.saved_accounts) if self.saved_accounts else "none"
        return (
            f"*Profile ID:* `{profile}`\n"
            f"*Account ID:* `{account}`\n"
            f"*Saved Profiles:* `{saved_profiles}`\n"
            f"*Saved Accounts:* `{saved_accounts}`\n"
            f"*Date Preset:* `{preset}`\n"
            f"*Last Refresh:* `{refresh}`"
        )


class SessionStore:
    """
    In-memory store for all user sessions.
    Thread-safe for asyncio (single-threaded event loop).

    If ADSPOWER_PROFILE_ID, FACEBOOK_ACCOUNT_ID, and TELEGRAM_CHAT_ID are set
    in the environment, the owner's session is pre-configured automatically —
    no /setprofile or /setaccount needed on first use.
    """

    def __init__(self) -> None:
        self._sessions: dict[int, UserSession] = {}
        self._pre_configure_owner()

    def _pre_configure_owner(self) -> None:
        """Pre-configure session for the owner from environment variables."""
        import os
        chat_id_str = os.getenv("TELEGRAM_CHAT_ID", "")
        profile_id = os.getenv("ADSPOWER_PROFILE_ID", "")
        account_id = os.getenv("FACEBOOK_ACCOUNT_ID", "")
        if chat_id_str and profile_id and account_id:
            try:
                uid = int(chat_id_str)
                self.set_profile(uid, profile_id)
                self.set_account(uid, account_id)
            except ValueError:
                pass

    def get(self, user_id: int) -> UserSession:
        """Get or create a session for a user."""
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)
        return self._sessions[user_id]

    def set_profile(self, user_id: int, profile_id: str) -> None:
        session = self.get(user_id)
        profile_id = profile_id.strip()
        if not profile_id:
            return
        if profile_id not in session.saved_profiles:
            session.saved_profiles.append(profile_id)
        session.profile_id = profile_id

    def set_account(self, user_id: int, account_id: str) -> None:
        session = self.get(user_id)
        account_id = account_id.strip()
        if not account_id:
            return
        if account_id not in session.saved_accounts:
            session.saved_accounts.append(account_id)
        session.account_id = account_id

    def use_profile(self, user_id: int, profile_id: str) -> bool:
        session = self.get(user_id)
        profile_id = profile_id.strip()
        if profile_id in session.saved_profiles:
            session.profile_id = profile_id
            return True
        return False

    def use_account(self, user_id: int, account_id: str) -> bool:
        session = self.get(user_id)
        account_id = account_id.strip()
        if account_id in session.saved_accounts:
            session.account_id = account_id
            return True
        return False

    def set_preset(self, user_id: int, preset: str) -> None:
        session = self.get(user_id)
        session.date_preset = preset.strip()

    def touch(self, user_id: int, command: str) -> None:
        """Record that a command was run."""
        session = self.get(user_id)
        session.last_command = command
        session.last_refresh = datetime.now()

    def all_users(self) -> list[int]:
        return list(self._sessions.keys())


# Global singleton — imported by commands.py and handlers.py
store = SessionStore()
