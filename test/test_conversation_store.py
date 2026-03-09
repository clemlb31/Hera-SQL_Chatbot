import pytest
from src.conversation_store import ConversationStore


@pytest.fixture
def store(tmp_path):
    s = ConversationStore(db_path=str(tmp_path / "test.db"))
    yield s
    s.close()


def test_create_and_contains(store):
    store.create("conv-1")
    assert "conv-1" in store
    assert "conv-999" not in store


def test_add_and_get_history(store):
    store.create("conv-1")
    store.add_message("conv-1", "user", "Bonjour")
    store.add_message("conv-1", "assistant", "Salut!")
    history = store.get_history("conv-1")
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "Bonjour"}
    assert history[1] == {"role": "assistant", "content": "Salut!"}


def test_get_full_conversation(store):
    store.create("conv-1")
    store.add_message("conv-1", "user", "test")
    conv = store.get("conv-1")
    assert conv is not None
    assert conv["model"] is None
    assert conv["pending_sql"] is None
    assert len(conv["history"]) == 1


def test_get_nonexistent(store):
    assert store.get("nope") is None


def test_set_and_get_model(store):
    store.create("conv-1")
    store.set_model("conv-1", "mistral-small-latest")
    assert store.get_model("conv-1") == "mistral-small-latest"


def test_set_and_get_pending_sql(store):
    store.create("conv-1")
    store.set_pending_sql("conv-1", "SELECT COUNT(*) FROM generic_anomaly")
    assert store.get_pending_sql("conv-1") == "SELECT COUNT(*) FROM generic_anomaly"
    store.set_pending_sql("conv-1", None)
    assert store.get_pending_sql("conv-1") is None


def test_set_and_get_last_results(store):
    store.create("conv-1")
    results = {"columns": ["a"], "rows": [[1]], "total_count": 1}
    store.set_last_results("conv-1", results)
    assert store.get_last_results("conv-1") == results
    store.set_last_results("conv-1", None)
    assert store.get_last_results("conv-1") is None


def test_list_all(store):
    store.create("conv-1")
    store.add_message("conv-1", "user", "Premier message")
    store.create("conv-2")
    store.add_message("conv-2", "user", "Deuxieme message")
    items = store.list_all()
    assert len(items) == 2
    assert items[0]["first_message"] is not None


def test_delete(store):
    store.create("conv-1")
    store.add_message("conv-1", "user", "test")
    store.delete("conv-1")
    assert "conv-1" not in store
    assert store.get_history("conv-1") == []
