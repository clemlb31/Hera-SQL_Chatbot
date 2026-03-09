import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROMPTS_DIR = BASE_DIR / "prompts"

# LLM Provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # "mistral" or "ollama"

# Mistral
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

# Ollama
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

# Database
MAX_ROWS_DISPLAY = 50
MAX_ROWS_EXPORT = 50000

# SQL Safety
FORBIDDEN_SQL_KEYWORDS = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "EXEC", "TRUNCATE"]
