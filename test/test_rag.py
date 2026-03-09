import sqlite3
import pytest
from src.rag import ValueIndex, BUSINESS_SYNONYMS


@pytest.fixture(scope="module")
def index():
    """Build a ValueIndex from a minimal in-memory database."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE generic_anomaly (
            business_object_typ TEXT,
            control_id TEXT,
            typology_id TEXT,
            source_event_typ TEXT,
            frequency_typ TEXT,
            priority_typ TEXT,
            correction_mode_typ TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE configuration (
            typology_fr_lbl TEXT,
            typology_en_lbl TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO generic_anomaly VALUES (?,?,?,?,?,?,?)",
        [
            ("tiers", "Falcon", "Falcon-naf_nace", "CREATED", "Q", "HIGH", "AUTO"),
            ("contrat", "Falcon", "Falcon-siret", "DISAPPEARED", "M", "LOW", "MANUAL"),
            ("titres", "Eagle", "Eagle-isin", "CREATED", "Q", None, None),
        ],
    )
    conn.executemany(
        "INSERT INTO configuration VALUES (?,?)",
        [
            ("Cohérence NAF/NACE temporelle", "NAF/NACE temporal consistency"),
            ("Validation SIRET", "SIRET validation"),
        ],
    )
    conn.commit()
    idx = ValueIndex(conn)
    conn.close()
    return idx


def test_index_contains_expected_columns(index):
    assert "business_object_typ" in index._values
    assert "control_id" in index._values
    assert "typology_fr_lbl" in index._values
    assert "typology_en_lbl" in index._values


def test_index_values_populated(index):
    assert set(index._values["business_object_typ"]) == {"tiers", "contrat", "titres"}
    assert set(index._values["control_id"]) == {"Falcon", "Eagle"}
    assert set(index._values["frequency_typ"]) == {"Q", "M"}


def test_find_relevant_values_match(index):
    result = index.find_relevant_values("anomalies tiers détectées par Falcon")
    assert result is not None
    assert "tiers" in result
    assert "Falcon" in result
    assert "VALEURS PERTINENTES" in result


def test_find_relevant_values_no_match(index):
    result = index.find_relevant_values("bonjour salut bienvenue")
    assert result is None


def test_find_relevant_values_short_tokens_ignored(index):
    """Tokens shorter than 3 chars should be skipped."""
    result = index.find_relevant_values("a b Q M")
    assert result is None


def test_find_relevant_values_max_matches(index):
    """Should cap at 20 matches maximum."""
    result = index.find_relevant_values("Falcon tiers contrat titres Eagle CREATED DISAPPEARED")
    if result:
        # Count quoted values in the result
        count = result.count('"')
        assert count <= 40  # 20 values * 2 quotes each


def test_reverse_index_built(index):
    assert "falcon" in index._reverse
    assert "tiers" in index._reverse
    entries = index._reverse["falcon"]
    columns = [col for col, _ in entries]
    assert "control_id" in columns


def test_synonyms_mensuel_resolves(index):
    """'mensuel' should resolve to frequency_typ = 'M' via synonyms."""
    result = index.find_relevant_values("anomalies mensuel")
    assert result is not None
    assert '"M"' in result


def test_synonyms_trimestriel_resolves(index):
    """'trimestrielle' should resolve to frequency_typ = 'Q' via synonyms."""
    result = index.find_relevant_values("fréquence trimestrielle")
    assert result is not None
    assert '"Q"' in result


def test_synonyms_client_resolves(index):
    """'client' should resolve to business_object_typ = 'tiers' via synonyms."""
    result = index.find_relevant_values("anomalies client")
    assert result is not None
    assert '"tiers"' in result


def test_synonyms_dict_has_expected_keys():
    """BUSINESS_SYNONYMS should contain key aliases."""
    assert "mensuel" in BUSINESS_SYNONYMS
    assert "quarterly" in BUSINESS_SYNONYMS
    assert "client" in BUSINESS_SYNONYMS
    assert "hotfix" in BUSINESS_SYNONYMS
    assert "resolved" in BUSINESS_SYNONYMS


def test_synonyms_bigram_resolution(index):
    """Bigram synonyms like 'third party' should resolve."""
    result = index.find_relevant_values("third party anomalies")
    assert result is not None
    assert '"tiers"' in result
