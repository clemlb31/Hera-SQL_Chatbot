import pandas as pd
from src.routes.export import generate_pdf


def test_pdf_generates_valid_buffer():
    df = pd.DataFrame({"anomaly_kuid": ["ANO001", "ANO002"], "count": [10, 20]})
    buffer = generate_pdf("Combien d'anomalies ?", "SELECT anomaly_kuid, count FROM test", df, "Il y a 2 résultats.")
    content = buffer.read()
    assert len(content) > 0
    assert content[:5] == b"%PDF-"


def test_pdf_without_question():
    df = pd.DataFrame({"a": [1]})
    buffer = generate_pdf(None, "SELECT 1", df, None)
    content = buffer.read()
    assert content[:5] == b"%PDF-"


def test_pdf_empty_dataframe():
    df = pd.DataFrame()
    buffer = generate_pdf("test", "SELECT 1 WHERE 0", df, None)
    content = buffer.read()
    assert content[:5] == b"%PDF-"


def test_pdf_large_dataframe_truncated():
    """PDF should handle DataFrames > 100 rows (truncates to 100)."""
    df = pd.DataFrame({"id": range(200), "val": range(200)})
    buffer = generate_pdf(None, "SELECT id, val FROM big", df, None)
    content = buffer.read()
    assert len(content) > 0
