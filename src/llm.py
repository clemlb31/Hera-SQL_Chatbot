import re
import json
import ollama
from abc import ABC, abstractmethod
from mistralai import Mistral
from src.config import (
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    OLLAMA_MODEL,
    PROMPTS_DIR,
)

# Model ID -> (provider_type, actual_model_id)
MODEL_REGISTRY = {
    "mistral-small-latest": ("mistral", "mistral-small-latest"),
    "mistral-large-latest": ("mistral", "mistral-large-latest"),
    "qwen3.5:9b": ("ollama", "qwen3.5:9b"),
}


def load_system_prompt() -> str:
    """Load the system prompt from prompts/system.txt."""
    path = PROMPTS_DIR / "system.txt"
    return path.read_text(encoding="utf-8")


def load_intent_prompt(intent: str) -> str | None:
    """Load an optional intent-specific prompt overlay (explain, compare)."""
    path = PROMPTS_DIR / f"{intent}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def extract_thinking(raw_text: str) -> tuple[str | None, str]:
    """Extract <think>...</think> block from response. Returns (thinking, rest)."""
    match = re.search(r"<think>(.*?)</think>", raw_text, re.DOTALL)
    if match:
        thinking = match.group(1).strip()
        rest = raw_text[:match.start()] + raw_text[match.end():]
        return thinking, rest.strip()
    return None, raw_text


def parse_llm_response(raw_text: str) -> dict:
    """Parse the LLM's JSON response, handling edge cases."""
    # Extract thinking block first
    thinking, text = extract_thinking(raw_text)
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start:end])
            except json.JSONDecodeError:
                return {"type": "error", "message": raw_text, "sql": None}
        else:
            return {"type": "error", "message": raw_text, "sql": None}

    if "type" not in parsed:
        parsed["type"] = "error"
    if "message" not in parsed:
        parsed["message"] = ""
    if "sql" not in parsed:
        parsed["sql"] = None
    # Extract reasoning (Chain-of-Thought) if present
    if "reasoning" in parsed:
        parsed["reasoning"] = parsed["reasoning"]
    if thinking:
        parsed["thinking"] = thinking

    return parsed


# --- LLM Providers ---

class LLMProvider(ABC):
    @abstractmethod
    def chat(self, system_prompt: str, messages: list[dict]) -> str:
        pass

    def chat_stream(self, system_prompt: str, messages: list[dict]):
        """Yield token dicts as they arrive. Override for streaming support."""
        # Default fallback: yield full response as one chunk
        result = self.chat(system_prompt, messages)
        yield {"thinking": "", "content": result}


class MistralProvider(LLMProvider):
    def __init__(self, model: str = MISTRAL_MODEL):
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.model = model

    def chat(self, system_prompt: str, messages: list[dict]) -> str:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        response = self.client.chat.complete(
            model=self.model,
            messages=full_messages,
            temperature=0.1,
        )
        return response.choices[0].message.content

    def chat_stream(self, system_prompt: str, messages: list[dict]):
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        stream = self.client.chat.stream(
            model=self.model,
            messages=full_messages,
            temperature=0.1,
        )
        for event in stream:
            delta = event.data.choices[0].delta
            yield {"thinking": "", "content": delta.content or ""}


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model

    def chat(self, system_prompt: str, messages: list[dict]) -> str:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        response = ollama.chat(
            model=self.model,
            messages=full_messages,
            think=True,
            options={"temperature": 0.1},
        )
        # Combine thinking + content if thinking is available
        parts = []
        if response.message.thinking:
            parts.append(f"<think>{response.message.thinking}</think>")
        if response.message.content:
            parts.append(response.message.content)
        return "\n".join(parts)

    def chat_stream(self, system_prompt: str, messages: list[dict]):
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        stream = ollama.chat(
            model=self.model,
            messages=full_messages,
            stream=True,
            think=True,
            options={"temperature": 0.1},
        )
        for chunk in stream:
            yield {
                "thinking": getattr(chunk.message, "thinking", None) or "",
                "content": chunk.message.content or "",
            }


def get_provider(model_id: str | None = None) -> LLMProvider:
    """Return a provider for the given model ID."""
    if model_id and model_id in MODEL_REGISTRY:
        provider_type, actual_model = MODEL_REGISTRY[model_id]
        if provider_type == "ollama":
            return OllamaProvider(model=actual_model)
        return MistralProvider(model=actual_model)
    # Default: Ollama (Qwen)
    return OllamaProvider()


# --- Cached system prompt ---

_system_prompt: str | None = None


def _get_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = load_system_prompt()
    return _system_prompt


def generate_response(messages: list[dict], model_id: str | None = None, context: str | None = None, intent: str | None = None) -> dict:
    """Send conversation to LLM and return parsed structured response."""
    provider = get_provider(model_id)
    system_prompt = _get_system_prompt()
    # Append intent-specific instructions
    if intent:
        intent_prompt = load_intent_prompt(intent)
        if intent_prompt:
            system_prompt = system_prompt + "\n\n" + intent_prompt
    if context:
        system_prompt = system_prompt + "\n\n" + context
    raw = provider.chat(system_prompt, messages)
    return parse_llm_response(raw)


def fix_sql(original_sql: str, error_message: str, model_id: str | None = None) -> dict:
    """Ask the LLM to fix a failed SQL query. Returns parsed response with corrected SQL."""
    provider = get_provider(model_id)
    system_prompt = _get_system_prompt()

    prompt = (
        f"La requête SQL suivante a échoué. Corrige-la en respectant le schéma.\n\n"
        f"## Requête originale\n```sql\n{original_sql}\n```\n\n"
        f"## Erreur\n{error_message}\n\n"
        f"## Rappel du schéma\n"
        f"- Tables: generic_anomaly (anomaly_kuid, title_txt, description_txt, business_object_typ, "
        f"source_application_iua_cod, control_id, typology_id, detection_time, asof_dat, frequency_typ, "
        f"priority_typ, object_identification_fields, error_fields, hotfix_flg, hotfix_expiration_asof_dat, "
        f"source_event_typ, other_fields, correction_mode_typ)\n"
        f"- Tables: configuration (typology_id, control_id, typology_cod, typology_fr_lbl, typology_en_lbl, "
        f"remediation_flg, is_deleted_flg, is_visible_flg, functional_control_id, pre_analysis_flg)\n"
        f"- JOIN: generic_anomaly.typology_id = configuration.typology_id\n\n"
        f"Analyse l'erreur, identifie la cause (colonne inexistante, syntaxe, valeur incorrecte), "
        f"et retourne le JSON corrigé."
    )

    messages = [{"role": "user", "content": prompt}]
    raw = provider.chat(system_prompt, messages)
    return parse_llm_response(raw)


def fix_empty_results(original_sql: str, user_question: str, model_id: str | None = None) -> dict:
    """Ask the LLM to reconsider a query that returned 0 results."""
    provider = get_provider(model_id)
    system_prompt = _get_system_prompt()

    prompt = (
        f"La requête SQL suivante a retourné 0 résultats. Les filtres sont peut-être trop restrictifs "
        f"ou les valeurs utilisées ne correspondent pas aux données réelles.\n\n"
        f"## Question originale\n{user_question}\n\n"
        f"## Requête (0 résultats)\n```sql\n{original_sql}\n```\n\n"
        f"Analyse les filtres et propose une requête corrigée avec des filtres plus souples "
        f"(LIKE au lieu de =, valeurs approchées, suppression de filtres trop restrictifs). "
        f"Explique dans 'message' ce que tu as changé."
    )

    messages = [{"role": "user", "content": prompt}]
    raw = provider.chat(system_prompt, messages)
    return parse_llm_response(raw)


def explain_results(sql: str, results: dict, model_id: str | None = None) -> str:
    """Ask the LLM to summarize query results in natural language."""
    provider = get_provider(model_id)

    prompt = (
        f"Résume brièvement les résultats de cette requête SQL. "
        f"Sois concis et mets en avant les chiffres clés.\n\n"
        f"Requête: {sql}\n"
        f"Nombre total de résultats: {results['total_count']}\n"
        f"Colonnes: {results['columns']}\n"
        f"Premières lignes: {json.dumps(results['rows'][:5], default=str)}"
    )

    messages = [{"role": "user", "content": prompt}]
    raw = provider.chat("Tu es un assistant d'analyse de données. Réponds de manière concise.", messages)
    return raw
