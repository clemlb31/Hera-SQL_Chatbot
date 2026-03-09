"""
Intent router — classifies user questions into intents before dispatching to the LLM.

Intents:
  - sql_query:  Data question → NL2SQL pipeline (default)
  - explain:    "Why does this anomaly exist?" → RAG with config labels
  - compare:    "Compare X vs Y" → generate comparative SQL
  - off_topic:  Unrelated to anomalies → politely refuse
"""

import re

# Patterns indicating an explanation request
_EXPLAIN_PATTERNS = re.compile(
    r"\b(pourquoi|expliqu|explain|why|signifie|meaning|comprendre|understand|"
    r"c['']est quoi|what is|what does|que veut dire|à quoi correspond)\b",
    re.IGNORECASE,
)

# Patterns indicating a comparison request
_COMPARE_PATTERNS = re.compile(
    r"\b(compar|versus|vs\.?|différence|difference|évolution|evolution|"
    r"par rapport|trend|tendance)\b",
    re.IGNORECASE,
)

# Patterns that suggest off-topic / prompt injection
_OFF_TOPIC_PATTERNS = re.compile(
    r"\b(ignore|oublie|forget|pretend|fais comme si|"
    r"raconte|joke|blague|poème|poem|recipe|recette|"
    r"translate|traduis|résume ce texte|summarize this text)\b",
    re.IGNORECASE,
)

# Topics that ARE on-topic (anomalies, data quality, SQL)
_ON_TOPIC_PATTERNS = re.compile(
    r"\b(anomali|typolog|control|falcon|eagle|hotfix|tiers|contrat|montant|"
    r"titres|asset|trade|position|business.?object|frequency|priority|"
    r"correction|kuid|sql|requête|query|données|data|nombre|count|"
    r"combien|filtr|group|top|stat|moyenne|average|max|min|total)\b",
    re.IGNORECASE,
)


def classify_intent(user_message: str) -> str:
    """Classify the user's message into an intent.

    Returns one of: "sql_query", "explain", "compare", "off_topic"
    """
    text = user_message.strip()

    # Check off-topic first (prompt injection / unrelated)
    if _OFF_TOPIC_PATTERNS.search(text) and not _ON_TOPIC_PATTERNS.search(text):
        return "off_topic"

    # Explanation intent
    if _EXPLAIN_PATTERNS.search(text) and _ON_TOPIC_PATTERNS.search(text):
        return "explain"

    # Comparison intent
    if _COMPARE_PATTERNS.search(text):
        return "compare"

    # Default: SQL query
    return "sql_query"


# Response templates for off-topic
OFF_TOPIC_RESPONSE = {
    "type": "clarify",
    "message": (
        "Je suis Prisme, un assistant spécialisé dans l'analyse des anomalies de qualité de données. "
        "Je ne peux répondre qu'aux questions portant sur les anomalies, les typologies, "
        "les contrôles et les statistiques associées. "
        "Pouvez-vous reformuler votre question dans ce périmètre ?"
    ),
    "sql": None,
}
