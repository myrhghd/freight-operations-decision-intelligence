from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "data" / "processed" / "logistics.duckdb"
SERVICE_NAME = "freight-visibility-ai-assistant"
