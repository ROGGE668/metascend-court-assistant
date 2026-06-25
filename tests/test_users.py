"""Tests for local user management."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Config
from src.users import User, UserStore


@pytest.fixture()
def user_store(tmp_path: Path) -> UserStore:
    store = UserStore(base_dir=tmp_path / "users")
    store.add_user("alice", display_name="Alice", role="admin")
    store.add_user("bob", display_name="Bob")
    return store


def test_default_user_created_when_empty(tmp_path: Path) -> None:
    store = UserStore(base_dir=tmp_path / "empty-users")
    user = store.ensure_default_user()
    assert user.username == "default"
    assert store.current_user().username == "default"


def test_list_users_returns_all_users(user_store: UserStore) -> None:
    users = user_store.list_users()
    assert [u.username for u in users] == ["alice", "bob"]


def test_add_user_rejects_duplicates(user_store: UserStore) -> None:
    with pytest.raises(ValueError, match="用户名已存在"):
        user_store.add_user("alice", display_name="Another Alice")


def test_current_user_can_switch(user_store: UserStore) -> None:
    alice = user_store.get_user_by_username("alice")
    assert alice is not None
    user_store.set_current_user(alice.user_id)
    current = user_store.current_user()
    assert current is not None
    assert current.username == "alice"


def test_delete_user_clears_current_user(user_store: UserStore) -> None:
    current = user_store.current_user()
    assert current is not None
    user_store.delete_user(current.user_id)
    assert user_store.current_user() is not None
    assert user_store.current_user().username != current.username


def test_update_user_changes_display_name(user_store: UserStore) -> None:
    user = user_store.get_user_by_username("alice")
    assert user is not None
    updated = user_store.update_user(user.user_id, display_name="Alice Updated")
    assert updated.display_name == "Alice Updated"
