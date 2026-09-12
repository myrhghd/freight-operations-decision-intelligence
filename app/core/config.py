import math
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "data" / "processed" / "logistics.duckdb"
SERVICE_NAME = "freight-visibility-ai-assistant"


def _load_environment(env_path: Path | None = None) -> None:
    """Load .env into the process environment. Safe to call with a missing file.

    override=False keeps existing environment variables ahead of .env values.
    """
    load_dotenv(env_path or PROJECT_ROOT / ".env", override=False)


_load_environment()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _env_positive_float(name: str, default: float) -> float:
    value = float(os.getenv(name, str(default)))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


LOCAL_LLM_ENABLED = _env_bool("LOCAL_LLM_ENABLED")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "2m")
# Allow cold model loading and CPU inference. This is an internal transport
# timeout, independent of Streamlit's HTTP timeout, not an end to end deadline.
OLLAMA_REQUEST_TIMEOUT_SECONDS = _env_positive_float("OLLAMA_REQUEST_TIMEOUT_SECONDS", 60.0)
