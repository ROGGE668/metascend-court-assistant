"""Local user management for the courtroom assistant.

All data is stored on disk under ``data/users/users.json``.  This module
does not implement secure authentication; it is intended for local
profile switching only.  Passwords are stored in plain text so users
understand this is convenience data, not a security boundary.
"""

from __future__ import annotations

import json
import logging
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import Config

logger = logging.getLogger(__name__)


def _generate_user_id() -> str:
    return "USR-" + "".join(secrets.choice(string.digits) for _ in range(6))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class User:
    """Minimal user profile stored locally."""

    def __init__(
        self,
        user_id: str,
        username: str,
        display_name: str = "",
        role: str = "user",
        password: str = "",
        created_at: str = "",
        updated_at: str = "",
    ) -> None:
        self.user_id = user_id
        self.username = username.strip()
        self.display_name = display_name.strip() or self.username
        self.role = role.strip().lower() or "user"
        self.password = password
        self.created_at = created_at or _utcnow()
        self.updated_at = updated_at or _utcnow()

    @property
    def summary(self) -> str:
        return self.display_name or self.username

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "password": self.password,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> User:
        return cls(
            user_id=data.get("user_id", _generate_user_id()),
            username=data.get("username", ""),
            display_name=data.get("display_name", ""),
            role=data.get("role", "user"),
            password=data.get("password", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class UserStore:
    """Persist and manage local users."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Config.DATA_DIR / "users"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.base_dir / "users.json"

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"users": [], "current_user_id": ""}
        try:
            with open(self._path, encoding="utf-8") as fp:
                data = json.load(fp)
            if not isinstance(data, dict):
                data = {"users": [], "current_user_id": ""}
            data.setdefault("users", [])
            data.setdefault("current_user_id", "")
            return data
        except Exception as exc:
            logger.exception("Failed to read user store")
            raise RuntimeError(f"Failed to read user store: {exc}") from exc

    def _write(self, data: dict[str, Any]) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.exception("Failed to write user store")
            raise RuntimeError(f"Failed to write user store: {exc}") from exc

    def list_users(self) -> list[User]:
        data = self._read()
        return [User.from_dict(item) for item in data.get("users", []) if isinstance(item, dict)]

    def get_user(self, user_id: str) -> User | None:
        for user in self.list_users():
            if user.user_id == user_id:
                return user
        return None

    def get_user_by_username(self, username: str) -> User | None:
        target = username.strip().lower()
        for user in self.list_users():
            if user.username.lower() == target:
                return user
        return None

    def current_user(self) -> User | None:
        data = self._read()
        user_id = data.get("current_user_id")
        if not user_id:
            return None
        return self.get_user(user_id)

    def add_user(self, username: str, display_name: str = "", password: str = "", role: str = "user") -> User:
        if not username.strip():
            raise ValueError("用户名不能为空")
        if self.get_user_by_username(username):
            raise ValueError(f"用户名已存在：{username}")
        user = User(
            user_id=_generate_user_id(),
            username=username.strip(),
            display_name=display_name.strip(),
            role=role.strip().lower() or "user",
            password=password,
        )
        data = self._read()
        data.setdefault("users", []).append(user.to_dict())
        if not data.get("current_user_id"):
            data["current_user_id"] = user.user_id
        self._write(data)
        logger.info("Added user %s", user.user_id)
        return user

    def update_user(self, user_id: str, **updates: Any) -> User:
        data = self._read()
        users = data.setdefault("users", [])
        for idx, item in enumerate(users):
            if isinstance(item, dict) and item.get("user_id") == user_id:
                merged = dict(item)
                merged.update(updates)
                merged["updated_at"] = _utcnow()
                users[idx] = merged
                self._write(data)
                return User.from_dict(merged)
        raise ValueError(f"用户不存在：{user_id}")

    def delete_user(self, user_id: str) -> None:
        data = self._read()
        users = data.get("users", [])
        filtered = [item for item in users if not (isinstance(item, dict) and item.get("user_id") == user_id)]
        if len(filtered) == len(users):
            raise ValueError(f"用户不存在：{user_id}")
        data["users"] = filtered
        if data.get("current_user_id") == user_id:
            data["current_user_id"] = filtered[0].get("user_id", "") if filtered else ""
        self._write(data)
        logger.info("Deleted user %s", user_id)

    def set_current_user(self, user_id: str) -> User:
        user = self.get_user(user_id)
        if user is None:
            raise ValueError(f"用户不存在：{user_id}")
        data = self._read()
        data["current_user_id"] = user.user_id
        self._write(data)
        logger.info("Switched current user to %s", user.user_id)
        return user

    def ensure_default_user(self) -> User:
        users = self.list_users()
        if users:
            return self.current_user() or users[0]
        return self.add_user("default", display_name="默认用户", role="admin")
