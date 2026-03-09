import pytest
from src.database import init_database


@pytest.fixture(scope="session")
def db():
    """Load real data into an in-memory SQLite database once for all tests."""
    conn = init_database()
    yield conn
    conn.close()
