import pytest
from src.logger import EventLogger


@pytest.fixture
def logger(tmp_path):
    lg = EventLogger(db_path=str(tmp_path / "test_logs.db"))
    yield lg
    lg.close()


def test_log_and_retrieve(logger):
    logger.log("sql_execute", conversation_id="c1", sql="SELECT 1", latency_ms=42)
    logs = logger.get_recent(10)
    assert len(logs) == 1
    assert logs[0]["event_type"] == "sql_execute"
    assert logs[0]["conversation_id"] == "c1"
    assert logs[0]["latency_ms"] == 42
    assert logs[0]["sql_query"] == "SELECT 1"


def test_log_with_metadata(logger):
    logger.log("chat_response", metadata={"tokens": 150})
    logs = logger.get_recent()
    assert '"tokens": 150' in logs[0]["metadata"]


def test_log_error(logger):
    logger.log("sql_error", error="no such table: foo", sql="SELECT * FROM foo")
    logs = logger.get_recent()
    assert logs[0]["error"] == "no such table: foo"


def test_recent_order(logger):
    logger.log("event_1")
    logger.log("event_2")
    logger.log("event_3")
    logs = logger.get_recent(2)
    assert len(logs) == 2
    assert logs[0]["event_type"] == "event_3"  # Most recent first
    assert logs[1]["event_type"] == "event_2"


def test_empty_logs(logger):
    assert logger.get_recent() == []
