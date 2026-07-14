"""Unit tests for the top-level ``storage.py`` module — encrypted host and
service-port records.

``storage.py`` is shadowed on the import path by the ``storage/`` package, so
it is loaded here directly from its file. ``STORAGE_FILE`` and ``KEY_FILE`` are
redirected into a temp directory per test to avoid touching the repo and to
keep runs isolated.
"""
import importlib.util
import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STORAGE_PY = os.path.join(_ROOT, "storage.py")


def _load_storage(tmp_path):
    spec = importlib.util.spec_from_file_location("_storage_flat", _STORAGE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.STORAGE_FILE = str(tmp_path / "data.json")
    mod.KEY_FILE = str(tmp_path / ".storage_key")
    return mod


@pytest.fixture
def store(tmp_path):
    return _load_storage(tmp_path)


def test_add_host_encrypts_password(store):
    rec = store.add_host("1.2.3.4", "root", password="hunter2")
    assert rec["host"] == "1.2.3.4"
    assert rec["id"] == "1-2-3-4"
    # First host added becomes the default.
    assert rec["is_default"] is True
    # Password is stored encrypted, not in plaintext.
    assert rec["password"] != "hunter2"
    assert store.decrypt_password(rec) == "hunter2"


def test_add_host_replaces_duplicate(store):
    store.add_host("h1", "root", password="a")
    store.add_host("h1", "admin", password="b")
    hosts = [h for h in store.list_hosts() if h["host"] == "h1"]
    assert len(hosts) == 1
    assert hosts[0]["username"] == "admin"
    assert store.decrypt_password(hosts[0]) == "b"


def test_get_host_by_id_and_host(store):
    store.add_host("box.example.com", "root", password="p")
    assert store.get_host("box.example.com") is not None
    assert store.get_host("box-example-com") is not None
    assert store.get_host("nope") is None


def test_default_host_selection(store):
    store.add_host("first", "root", password="p1")
    store.add_host("second", "root", password="p2")
    assert store.get_default_host()["host"] == "first"
    store.set_default_host("second")
    assert store.get_default_host()["host"] == "second"


def test_update_host_reencrypts_password(store):
    store.add_host("h", "root", password="old")
    store.update_host("h", password="new", status="online")
    host = store.get_host("h")
    assert host["status"] == "online"
    assert store.decrypt_password(host) == "new"


def test_seed_default_host_idempotent(store):
    store.seed_default_host("rootpw")
    assert len(store.list_hosts()) == 1
    store.seed_default_host("other")  # no-op once seeded
    assert len(store.list_hosts()) == 1
    assert store.decrypt_password(store.get_default_host()) == "rootpw"


def test_service_port_round_trip(store):
    assert store.get_service_port("web", "h1") is None
    store.save_service_port("web", "h1", 8080)
    assert store.get_service_port("web", "h1") == 8080
    # Overwrites rather than duplicating.
    store.save_service_port("web", "h1", 9090)
    assert store.get_service_port("web", "h1") == 9090
    matches = [s for s in store._load()["services"] if s["service"] == "web"]
    assert len(matches) == 1
