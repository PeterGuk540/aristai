import time

import pytest

from api.services.action_store import ActionStore, ActionRecord


class FakeRedis:
    def __init__(self):
        self._store = {}

    def set(self, key, value, ex=None):
        expires_at = time.time() + ex if ex else None
        self._store[key] = (value, expires_at)

    def get(self, key):
        value, expires_at = self._store.get(key, (None, None))
        if value is None:
            return None
        if expires_at is not None and time.time() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def delete(self, key):
        self._store.pop(key, None)

    def ttl(self, key):
        value, expires_at = self._store.get(key, (None, None))
        if value is None:
            return -2
        if expires_at is None:
            return -1
        return int(expires_at - time.time())


def test_action_store_ownership():
    store = ActionStore(redis_client=FakeRedis(), ttl_seconds=60)
    record = store.create_action(
        user_id=1,
        tool_name="create_course",
        args={"title": "History"},
        preview={"affected": {"courses": 1}},
    )
    assert isinstance(record, ActionRecord)
    assert ActionStore.ensure_owner(record, 1) is None
    assert ActionStore.ensure_owner(record, 2) == "Action does not belong to the current user."


def test_action_store_ttl_expiry():
    store = ActionStore(redis_client=FakeRedis(), ttl_seconds=1)
    record = store.create_action(
        user_id=None,
        tool_name="create_course",
        args={"title": "History"},
        preview={"affected": {"courses": 1}},
    )
    assert store.get_action(record.action_id) is not None
    time.sleep(1.1)
    assert store.get_action(record.action_id) is None
