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
