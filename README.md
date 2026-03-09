# Prisme — Anomaly Insights

**Prisme** est un chatbot NL2SQL (Natural Language to SQL) augmenté par RAG, conçu pour explorer et analyser des anomalies de qualité de données. L'utilisateur pose une question en langage naturel, Prisme génère la requête SQL correspondante, l'exécute sur une base SQLite en mémoire (~167 000 anomalies) et restitue les résultats sous forme de tableaux, graphiques et exports.

---

## Guide d'utilisation

### Installation

**Prérequis :** Python 3.12+, un fournisseur LLM (Ollama local ou clé API Mistral).

```bash
# 1. Cloner le projet
git clone <repo-url> && cd Prisme

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer l'environnement
cp .env.example .env
# Éditer .env : choisir LLM_PROVIDER (ollama ou mistral) et renseigner la clé API si besoin

# 4. (Si Ollama) S'assurer que le modèle est téléchargé
ollama pull qwen3.5:latest

# 5. Lancer le serveur
uvicorn src.main:app --reload --port 8000
```

Ouvrir **http://localhost:8000** dans un navigateur.

### Poser une question

1. Taper une question en français ou en anglais dans la zone de saisie en bas de l'écran.
   - Exemples : *"Combien d'anomalies par type d'objet métier ?"*, *"Top 10 des typologies les plus fréquentes"*
   - Des suggestions de questions sont affichées sur l'écran d'accueil pour démarrer rapidement.
2. Prisme répond avec une **explication** de ce qu'il a compris et la **requête SQL** qu'il propose.
3. Trois options s'offrent à vous :
   - **Exécuter** — lance la requête et affiche les résultats.
   - **Modifier** — demander à Prisme d'ajuster la requête (ex : *"Ajoute un filtre sur 2024"*).
   - **Annuler** — abandonner la requête.

Si la question est ambiguë, Prisme demandera une clarification avant de proposer du SQL.

> **Routing intelligent** — Prisme classifie automatiquement votre question en 4 intentions :
> - **sql_query** — question sur les données → pipeline NL2SQL
> - **explain** — *"Pourquoi cette anomalie ?"* → explication métier enrichie
> - **compare** — *"Compare tiers vs contrat"* → requête comparative
> - **off_topic** — question hors périmètre → refus poli avec recentrage

### Dashboard

Cliquer sur le bouton grille (en haut à droite) pour ouvrir/fermer le panneau dashboard. Il affiche :
- **3 KPIs** — nombre total d'anomalies, hotfix actifs, typologies
- **Top 5 objets métier** — barres horizontales avec compteurs
- **Top 5 typologies** — barres horizontales avec compteurs

Le dashboard se charge une seule fois et reste en cache côté client.

### Lire les résultats

- Les résultats s'affichent dans un **tableau** scrollable sous le message.
- Si le résultat contient 2 colonnes (label + valeur numérique), un **graphique** est généré automatiquement. Cliquer sur *"Afficher le graphique"* pour le voir.
- Le nombre total de lignes est indiqué (ex : *"167 000 total, 50 affichés"*).

### Exporter les résultats

Après une exécution, trois boutons d'export apparaissent :
- **CSV** — fichier texte compatible Excel (encodage UTF-8 BOM).
- **Excel** — fichier .xlsx natif.
- **PDF** — rapport formaté incluant la question, le SQL, le tableau de résultats et le résumé.

### Changer de modèle LLM

Le sélecteur en bas à gauche de la zone de saisie permet de basculer entre :
- **Qwen 3.5 (local)** — via Ollama, fonctionne hors ligne.
- **Mistral Small / Large** — via l'API Mistral, nécessite une clé API.

Le changement est immédiat, pas besoin de redémarrer.

### Gérer les conversations

- **Historique** — cliquer sur le bouton ☰ en haut à gauche pour ouvrir la sidebar avec toutes les conversations passées.
- **Reprendre** — cliquer sur une conversation pour la recharger avec tout son historique.
- **Supprimer** — survoler une conversation et cliquer sur ✕.
- **Nouvelle conversation** — bouton *"+ Nouvelle conversation"* en haut à droite.

### Autocomplétion

En tapant dans la zone de saisie, un menu déroulant peut apparaître avec des suggestions de noms de tables, colonnes ou valeurs connues. Utiliser les flèches ↑↓ pour naviguer, Enter ou Tab pour sélectionner.

### Bloc de réflexion

Quand Prisme utilise un modèle avec thinking (Qwen), un bloc dépliable *"Réflexion"* apparaît au-dessus de la réponse. Il montre le raisonnement interne du LLM — utile pour comprendre comment la requête a été construite.

### Évaluation

Pour mesurer la qualité du NL2SQL sur un jeu de 20 questions prédéfinies :

```bash
python -m eval.run_eval                    # Évaluer avec le modèle par défaut
python -m eval.run_eval --model mistral-small-latest  # Évaluer un modèle spécifique
python -m eval.run_eval --all-models --output results.json  # Comparer tous les modèles
```

### Tests

```bash
pytest test/ -v
```

91 tests couvrant la base de données, le parsing LLM, le RAG (synonymes, index inversé), le cache, les conversations, le logger, les suggestions, l'export PDF, le router d'intention, le dashboard, les prompts (CoT, intent overlays) et les routes API.

---

## Architecture

```
interface/          Frontend (HTML/CSS/JS vanilla)
src/
├── main.py         FastAPI app, lifespan, routes
├── routes/         Endpoints API (chat, stream, query, export, suggestions, conversations, dashboard)
├── database.py     SQLite in-memory, chargement CSV, validation SQL
├── llm.py          Abstraction multi-LLM (Mistral API, Ollama local)
├── rag.py          ValueIndex — injection de contexte RAG
├── cache.py        Cache LRU avec TTL
├── logger.py       Event logger SQLite
├── conversation_store.py   Persistance des conversations
├── router.py       Classifieur d'intention (sql_query, explain, compare, off_topic)
├── models.py       Modèles Pydantic
└── config.py       Configuration centralisée
prompts/
├── system.txt      System prompt avec schéma de données
├── explain.txt     Prompt overlay pour les explications métier
└── compare.txt     Prompt overlay pour les comparaisons
eval/               Framework d'évaluation NL2SQL
data/               Dumps CSV (non trackés)
```

## Configuration

| Variable | Description | Défaut |
|----------|-------------|--------|
| `LLM_PROVIDER` | `mistral` ou `ollama` | `ollama` |
| `MISTRAL_API_KEY` | Clé API Mistral | — |
| `MISTRAL_MODEL` | Modèle Mistral | `mistral-small-latest` |
| `OLLAMA_MODEL` | Modèle Ollama local | `qwen3.5:latest` |

---

## Fonctionnalités

### Routing par intention

- **Classifieur automatique** — Avant tout appel au LLM, la question est classifiée en 4 intentions : `sql_query`, `explain`, `compare`, `off_topic`.
- **Prompts spécialisés** — Chaque intention injecte un prompt overlay adapté (SQL, explication métier, comparaison) pour améliorer la qualité des réponses.
- **Compliance / filtre off-topic** — Les questions hors périmètre (prompt injection, sujets non liés aux anomalies) sont bloquées sans appeler le LLM. Prisme refuse poliment et recentre l'utilisateur.

### Dashboard KPIs

- **Panneau rétractable** — Bouton grille en haut à droite, le panneau s'affiche/se cache sous le header.
- **3 KPIs** — Nombre total d'anomalies, hotfix actifs, nombre de typologies.
- **Top 5 objets métier** — Barres horizontales proportionnelles avec compteurs.
- **Top 5 typologies** — Barres horizontales avec libellés français.
- **Chargement lazy** — Les données ne sont récupérées qu'au premier clic et mises en cache.

### Chat NL2SQL

- **Langage naturel → SQL** — L'utilisateur pose une question, le LLM génère un `SELECT` SQLite validé. Les requêtes destructrices (INSERT, UPDATE, DELETE, DROP) sont bloquées.
- **Flux conversationnel** — Le LLM répond soit par une clarification (question ambiguë), soit par une proposition SQL avec explication. L'utilisateur confirme, modifie ou annule avant exécution.
- **Historique de conversation** — Chaque échange est persisté en SQLite. Le contexte conversationnel est injecté dans le prompt pour des réponses cohérentes.
- **Bilingue** — Répond en français ou en anglais selon la langue de l'utilisateur.

### Prompt Engineering avancé

- **Chain-of-Thought (CoT)** — Le system prompt impose un raisonnement structuré en 5 étapes avant la génération SQL : identification des tables, sélection des colonnes, conditions de jointure, filtres WHERE, agrégations. Le champ `reasoning` dans la réponse JSON capture ce raisonnement.
- **Sample rows** — Le prompt inclut 3 lignes d'exemple par table pour que le LLM comprenne les formats réels des données (dates, codes, JSON).
- **Contraintes anti-hallucination** — Règles explicites interdisant au LLM d'inventer des tables ou colonnes, obligeant les alias qualifiés dans les JOINs, et recommandant LIKE en cas de doute sur une valeur.
- **Few-shot examples avec CoT** — Les exemples du system prompt incluent un champ `reasoning` montrant le raisonnement attendu pour chaque type de requête.
- **Prompts spécialisés enrichis** — Les overlays explain et compare contiennent des exemples détaillés (FR/EN) avec raisonnement, règles spécifiques et structure de réponse attendue.

### Streaming temps réel

- **Server-Sent Events (SSE)** — Les tokens du LLM sont streamés en temps réel dans l'interface. L'utilisateur voit la réponse se construire progressivement.
- **Blocs de réflexion** — Les tokens de "thinking" (`<think>...</think>`) sont capturés et affichés dans un bloc dépliable "Réflexion" dans l'UI.

### RAG — Injection de contexte

- **ValueIndex** — Un index inversé pré-calculé des valeurs distinctes des colonnes clés (business_object_typ, control_id, typology_id, frequency_typ, priority_typ, etc.).
- **Matching par tokens** — Les mots de la question utilisateur sont comparés à l'index. Les valeurs pertinentes sont injectées dans le system prompt pour que le LLM génère du SQL avec les bonnes valeurs exactes.
- **Synonymes métier** — Dictionnaire d'alias qui traduit le langage courant vers les valeurs exactes de la base : "client" → `tiers`, "mensuel" → `M`, "trimestriel" → `Q`, "resolved" → `SOLVED`, etc. Supporte les bigrams ("third party", "court terme").
- **Valeurs exactes dans le prompt** — Le system prompt inclut la liste exhaustive des valeurs possibles pour chaque colonne clé, empêchant le LLM de deviner.

### Multi-modèles LLM

- **Mistral API** — Support de `mistral-small-latest` et `mistral-large-latest` via l'API Mistral.
- **Ollama local** — Support de Qwen 3.5 (et tout modèle Ollama compatible) en inférence locale.
- **Switch à la volée** — L'utilisateur peut changer de modèle directement depuis le sélecteur dans l'interface, sans redémarrer le serveur.

### Sécurité SQL

- **Whitelist SELECT** — Seules les requêtes `SELECT` sont autorisées. Toute autre instruction est rejetée.
- **Validation EXPLAIN** — Chaque requête passe par `EXPLAIN QUERY PLAN` pour détecter les erreurs de syntaxe avant exécution.
- **Détection de requêtes coûteuses** — Alertes automatiques pour `SELECT *` sans LIMIT, CROSS JOIN, ou jointures implicites sans WHERE. L'utilisateur peut forcer l'exécution.

### Self-healing SQL

- **Correction automatique** — Si une requête échoue à l'exécution, le LLM reçoit le message d'erreur **avec le schéma complet** et tente de corriger le SQL (jusqu'à 2 tentatives).
- **Gestion des résultats vides** — Si une requête retourne 0 lignes, le LLM réanalyse les filtres et propose une requête corrigée avec des filtres plus souples (LIKE au lieu de =, valeurs approchées).
- **Traçabilité** — Les corrections appliquées (erreurs SQL et filtres relâchés) sont affichées à l'utilisateur.

### Cache de requêtes

- **LRU + TTL** — Les résultats sont mis en cache en mémoire (clé = hash SHA256 du SQL normalisé). TTL de 5 minutes, max 100 entrées. Évite les appels DB redondants.

### Résultats et visualisation

- **Tableau de résultats** — Affichage en tableau HTML scrollable avec headers sticky, troncature des cellules longues, et indication du nombre total de lignes.
- **Graphiques automatiques** — Détection automatique des résultats à 2 colonnes (label + valeur numérique). Génération de bar charts (ou line charts pour les dates) via Chart.js.
- **Toggle graphique** — Bouton pour afficher/masquer le graphique.

### Export multi-format

- **CSV** — Export UTF-8 avec BOM pour compatibilité Excel.
- **Excel** — Export XLSX via openpyxl.
- **PDF** — Rapport formaté avec ReportLab : titre, question originale, requête SQL, tableau de résultats et résumé du LLM. Jusqu'à 50 000 lignes.

### Autocomplétion

- **Suggestions en temps réel** — Dropdown de suggestions pendant la saisie (tables, colonnes, valeurs distinctes).
- **Debounce 300ms** — Limite les appels API pendant la frappe.
- **Navigation clavier** — Flèches haut/bas, Enter/Tab pour sélectionner, Escape pour fermer.

### Gestion des conversations

- **Sidebar historique** — Liste des conversations passées avec titre (extrait du premier message), date, et bouton de suppression.
- **Reprise de conversation** — Clic pour recharger l'historique complet et continuer l'échange.
- **Nouvelle conversation** — Reset de l'état et retour à l'écran d'accueil.

### Logging

- **Event logger** — Tous les événements significatifs (appels LLM, exécutions SQL, erreurs) sont loggés en SQLite avec latence, modèle, conversation ID et métadonnées.
- **Endpoint `/api/logs`** — Consultation des 50 derniers événements.

### Évaluation NL2SQL

- **Dataset de 20 questions** — Couvre les principaux patterns SQL : COUNT, GROUP BY, JOIN, filtres dates, TOP N, DISTINCT, recherche JSON, etc.
- **Script d'évaluation** — Vérifie le type de réponse, le matching regex du SQL généré, et la validité d'exécution.
- **Multi-modèle** — Peut évaluer et comparer différents modèles LLM.
- **Export JSON** — Résultats détaillés par question avec métriques de latence et taux de succès.

### Interface

- **Light / Dark mode** — Thème clair et sombre suivant automatiquement la préférence système (`prefers-color-scheme`). Un bouton toggle dans le header permet de forcer le thème. Le choix est persisté en `localStorage`.
- **Design Natixis** — Palette construite autour du violet Natixis (#5C1A7E) avec des couleurs adaptées pour chaque mode (contrastes WCAG).
- **Responsive** — Adapté desktop et mobile, sidebar repliable.
- **Coloration syntaxique SQL** — Keywords, fonctions, strings et nombres colorés, adaptés au thème actif.
- **Copier le SQL** — Bouton de copie dans le presse-papier.
- **Auto-resize textarea** — Le champ de saisie grandit automatiquement (max 150px).

---

## API Endpoints

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/api/chat` | Chat standard |
| POST | `/api/chat/stream` | Chat streaming SSE |
| POST | `/api/execute` | Exécuter le SQL en attente |
| GET | `/api/export` | Export CSV/XLSX/PDF |
| GET | `/api/conversations` | Lister les conversations |
| GET | `/api/conversations/{id}` | Détail d'une conversation |
| DELETE | `/api/conversations/{id}` | Supprimer une conversation |
| GET | `/api/suggestions` | Autocomplétion |
| GET | `/api/dashboard` | KPIs du dashboard |
| GET | `/api/schema` | Schéma de la base |
| GET | `/api/logs` | Logs récents |

## Données

- **generic_anomaly** — ~167 000 anomalies de qualité (tiers, contrats, montants, titres, trades, positions...)
- **configuration** — 264 typologies avec libellés FR/EN, contrôles fonctionnels, flags de visibilité
- **Jointure** — `generic_anomaly.typology_id → configuration.typology_id`
