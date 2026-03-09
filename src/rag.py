import sqlite3


# Business synonyms: maps common French/English terms to actual column values
# Format: alias -> (column_name, exact_value)
BUSINESS_SYNONYMS: dict[str, list[tuple[str, str]]] = {
    # frequency_typ aliases
    "mensuel": [("frequency_typ", "M")],
    "mensuelle": [("frequency_typ", "M")],
    "mensuelles": [("frequency_typ", "M")],
    "monthly": [("frequency_typ", "M")],
    "trimestriel": [("frequency_typ", "Q")],
    "trimestrielle": [("frequency_typ", "Q")],
    "trimestrielles": [("frequency_typ", "Q")],
    "quarterly": [("frequency_typ", "Q")],
    # hotfix_flg aliases
    "hotfix": [("hotfix_flg", "1")],
    "correction court terme": [("hotfix_flg", "1")],
    "short term": [("hotfix_flg", "1")],
    # business_object_typ aliases
    "client": [("business_object_typ", "tiers")],
    "clients": [("business_object_typ", "tiers")],
    "contrepartie": [("business_object_typ", "tiers")],
    "contreparties": [("business_object_typ", "tiers")],
    "third party": [("business_object_typ", "tiers")],
    "produit": [("business_object_typ", "titres")],
    "produits": [("business_object_typ", "titres")],
    "instrument": [("business_object_typ", "titres")],
    "instruments": [("business_object_typ", "titres")],
    "securities": [("business_object_typ", "titres")],
    "amount": [("business_object_typ", "montant")],
    "amounts": [("business_object_typ", "montant")],
    "montants": [("business_object_typ", "montant")],
    # source_event_typ aliases
    "résolue": [("source_event_typ", "SOLVED")],
    "résolues": [("source_event_typ", "SOLVED")],
    "resolved": [("source_event_typ", "SOLVED")],
    "solved": [("source_event_typ", "SOLVED")],
    "corrigée": [("source_event_typ", "SOLVED")],
    "corrigées": [("source_event_typ", "SOLVED")],
}


class ValueIndex:
    """Index of distinct column values for RAG-augmented LLM context."""

    # Columns to index from generic_anomaly
    ANOMALY_COLUMNS = [
        "business_object_typ",
        "control_id",
        "typology_id",
        "source_event_typ",
        "frequency_typ",
        "priority_typ",
        "correction_mode_typ",
    ]

    # Columns to index from configuration
    CONFIG_COLUMNS = [
        "typology_fr_lbl",
        "typology_en_lbl",
    ]

    def __init__(self, conn: sqlite3.Connection):
        self._values: dict[str, list[str]] = {}
        self._reverse: dict[str, list[tuple[str, str]]] = {}
        self._build_index(conn)

    def _build_index(self, conn: sqlite3.Connection):
        for col in self.ANOMALY_COLUMNS:
            rows = conn.execute(
                f"SELECT DISTINCT {col} FROM generic_anomaly WHERE {col} IS NOT NULL AND {col} != ''"
            ).fetchall()
            values = [r[0] for r in rows if r[0]]
            self._values[col] = values

        for col in self.CONFIG_COLUMNS:
            rows = conn.execute(
                f"SELECT DISTINCT {col} FROM configuration WHERE {col} IS NOT NULL AND {col} != ''"
            ).fetchall()
            values = [r[0] for r in rows if r[0]]
            self._values[col] = values

        # Build reverse index: normalized token -> [(column, exact_value)]
        for col, values in self._values.items():
            for val in values:
                key = str(val).lower().strip()
                if key not in self._reverse:
                    self._reverse[key] = []
                self._reverse[key].append((col, str(val)))

    def _resolve_synonyms(self, tokens: list[str]) -> dict[str, set[str]]:
        """Resolve business synonyms from user tokens. Returns matches dict."""
        matches: dict[str, set[str]] = {}

        # Check single tokens
        for token in tokens:
            if token in BUSINESS_SYNONYMS:
                for col, val in BUSINESS_SYNONYMS[token]:
                    matches.setdefault(col, set()).add(val)

        # Check bigrams (e.g. "court terme", "third party")
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]} {tokens[i+1]}"
            if bigram in BUSINESS_SYNONYMS:
                for col, val in BUSINESS_SYNONYMS[bigram]:
                    matches.setdefault(col, set()).add(val)

        return matches

    def find_relevant_values(self, user_query: str) -> str | None:
        """Find column values relevant to the user's query.

        Returns a context string to inject into the LLM prompt, or None if no matches.
        """
        query_lower = user_query.lower()
        tokens = query_lower.split()

        # Start with synonym matches (high priority)
        matches = self._resolve_synonyms(tokens)
        match_count = sum(len(v) for v in matches.values())

        # Then do token-based matching on the reverse index
        for token in tokens:
            if len(token) < 3:
                continue
            for known_val, entries in self._reverse.items():
                if token in known_val or known_val in token:
                    for col, exact_val in entries:
                        if col not in matches:
                            matches[col] = set()
                        if exact_val not in matches[col]:
                            matches[col].add(exact_val)
                            match_count += 1
                            if match_count >= 20:
                                break
                if match_count >= 20:
                    break
            if match_count >= 20:
                break

        if not matches:
            return None

        parts = []
        for col, vals in matches.items():
            vals_str = ", ".join(f'"{v}"' for v in sorted(vals)[:10])
            parts.append(f"- {col} : {vals_str}")

        return "## VALEURS PERTINENTES DÉTECTÉES\nUtilise ces valeurs exactes dans tes requêtes SQL :\n" + "\n".join(parts)
