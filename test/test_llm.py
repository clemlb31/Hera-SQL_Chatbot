from src.llm import parse_llm_response, load_system_prompt, load_intent_prompt


def test_parse_confirm_sql():
    raw = '{"type": "confirm_sql", "message": "Je vais compter les anomalies.", "sql": "SELECT COUNT(*) FROM generic_anomaly"}'
    result = parse_llm_response(raw)
    assert result["type"] == "confirm_sql"
    assert result["sql"] == "SELECT COUNT(*) FROM generic_anomaly"
    assert "compter" in result["message"]


def test_parse_clarify():
    raw = '{"type": "clarify", "message": "Pouvez-vous préciser la période ?"}'
    result = parse_llm_response(raw)
    assert result["type"] == "clarify"
    assert result["sql"] is None


def test_parse_with_markdown_fences():
    raw = '```json\n{"type": "confirm_sql", "message": "test", "sql": "SELECT 1"}\n```'
    result = parse_llm_response(raw)
    assert result["type"] == "confirm_sql"
    assert result["sql"] == "SELECT 1"


def test_parse_malformed_json():
    raw = "This is not JSON at all"
    result = parse_llm_response(raw)
    assert result["type"] == "error"


def test_parse_json_embedded_in_text():
    raw = 'Here is my response: {"type": "clarify", "message": "What period?"} hope this helps'
    result = parse_llm_response(raw)
    assert result["type"] == "clarify"


def test_parse_missing_fields():
    raw = '{"type": "confirm_sql"}'
    result = parse_llm_response(raw)
    assert result["message"] == ""
    assert result["sql"] is None


def test_parse_reasoning_field():
    """Chain-of-Thought reasoning field should be preserved in parsed output."""
    raw = '{"type": "confirm_sql", "reasoning": "Table generic_anomaly, COUNT(*), pas de filtre.", "message": "Je vais compter.", "sql": "SELECT COUNT(*) FROM generic_anomaly"}'
    result = parse_llm_response(raw)
    assert result["type"] == "confirm_sql"
    assert result["reasoning"] == "Table generic_anomaly, COUNT(*), pas de filtre."
    assert result["sql"] is not None


def test_parse_reasoning_absent():
    """When reasoning field is absent, it should not appear in output."""
    raw = '{"type": "confirm_sql", "message": "test", "sql": "SELECT 1"}'
    result = parse_llm_response(raw)
    assert "reasoning" not in result


def test_system_prompt_loads():
    prompt = load_system_prompt()
    assert "generic_anomaly" in prompt
    assert "configuration" in prompt
    assert "JSON" in prompt
    assert "confirm_sql" in prompt


def test_system_prompt_has_cot_instructions():
    """System prompt should contain Chain-of-Thought instructions."""
    prompt = load_system_prompt()
    assert "reasoning" in prompt.lower()
    assert "Chain-of-Thought" in prompt or "raisonnement" in prompt.lower()


def test_system_prompt_has_sample_rows():
    """System prompt should contain sample data rows."""
    prompt = load_system_prompt()
    assert "ANO00026656D" in prompt
    assert "EXEMPLES DE DONNÉES" in prompt


def test_system_prompt_has_anti_hallucination():
    """System prompt should contain anti-hallucination constraints."""
    prompt = load_system_prompt()
    assert "anti-hallucination" in prompt.lower() or "N'invente JAMAIS" in prompt


def test_system_prompt_has_exact_values():
    """System prompt should list exact column values."""
    prompt = load_system_prompt()
    assert "VALEURS EXACTES" in prompt
    assert '"tiers"' in prompt
    assert '"Q"' in prompt


def test_load_intent_prompt_explain():
    """Explain intent prompt should load with examples."""
    prompt = load_intent_prompt("explain")
    assert prompt is not None
    assert "COMPRENDRE" in prompt
    assert "reasoning" in prompt


def test_load_intent_prompt_compare():
    """Compare intent prompt should load with examples."""
    prompt = load_intent_prompt("compare")
    assert prompt is not None
    assert "COMPARER" in prompt
    assert "GROUP BY" in prompt


def test_load_intent_prompt_nonexistent():
    """Unknown intent should return None."""
    prompt = load_intent_prompt("nonexistent_intent")
    assert prompt is None
