from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.config import _load_environment


def test_load_environment_reads_values_from_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EXAMPLE_GRAPH_TEST_VAR", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("EXAMPLE_GRAPH_TEST_VAR=from_dotenv\n")

    _load_environment(env_file)

    assert os.environ["EXAMPLE_GRAPH_TEST_VAR"] == "from_dotenv"


def test_load_environment_keeps_existing_variable_over_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EXAMPLE_GRAPH_TEST_VAR", "from_process_environment")
    env_file = tmp_path / ".env"
    env_file.write_text("EXAMPLE_GRAPH_TEST_VAR=from_dotenv\n")

    _load_environment(env_file)

    assert os.environ["EXAMPLE_GRAPH_TEST_VAR"] == "from_process_environment"


def test_load_environment_missing_file_does_not_raise(tmp_path: Path) -> None:
    missing_env_file = tmp_path / "does_not_exist.env"

    _load_environment(missing_env_file)
