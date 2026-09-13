from __future__ import annotations

import os
import runpy
from pathlib import Path

import pytest

from app.core.config import _load_environment
from app.core import config


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


LLM_VARIABLES = (
    "LOCAL_LLM_ENABLED", "OLLAMA_HOST", "OLLAMA_MODEL", "OLLAMA_KEEP_ALIVE",
    "OLLAMA_REQUEST_TIMEOUT_SECONDS",
)


@pytest.fixture
def isolated_llm_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in LLM_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)


def test_llm_defaults(isolated_llm_environment: None) -> None:
    settings = runpy.run_path(config.__file__)
    assert {name: settings[name] for name in LLM_VARIABLES} == {
        "LOCAL_LLM_ENABLED": False,
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": "qwen2.5:1.5b",
        "OLLAMA_KEEP_ALIVE": "2m",
        "OLLAMA_REQUEST_TIMEOUT_SECONDS": 120.0,
    }


@pytest.mark.parametrize("value, expected", [
    ("true", True), ("TRUE", True), ("1", True), ("yes", True), (" On ", True),
    ("false", False), ("FALSE", False), ("0", False), ("no", False), (" Off ", False),
])
def test_llm_boolean_parsing(value, expected, isolated_llm_environment, monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_ENABLED", value)
    assert runpy.run_path(config.__file__)["LOCAL_LLM_ENABLED"] is expected


@pytest.mark.parametrize("value", ["", "enabled", "2"])
def test_llm_invalid_boolean_rejected(value, isolated_llm_environment, monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_ENABLED", value)
    with pytest.raises(ValueError):
        runpy.run_path(config.__file__)


def test_llm_overrides(isolated_llm_environment, monkeypatch):
    overrides = {
        "LOCAL_LLM_ENABLED": "yes", "OLLAMA_HOST": "http://localhost:11435",
        "OLLAMA_MODEL": "test-model", "OLLAMA_KEEP_ALIVE": "3m",
        "OLLAMA_REQUEST_TIMEOUT_SECONDS": "90.5",
    }
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)
    settings = runpy.run_path(config.__file__)
    assert settings["LOCAL_LLM_ENABLED"] is True
    assert settings["OLLAMA_REQUEST_TIMEOUT_SECONDS"] == 90.5
    for name in ("OLLAMA_HOST", "OLLAMA_MODEL", "OLLAMA_KEEP_ALIVE"):
        assert settings[name] == overrides[name]


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "bad"])
def test_llm_invalid_timeout_rejected(value, isolated_llm_environment, monkeypatch):
    monkeypatch.setenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError):
        runpy.run_path(config.__file__)


def test_llm_process_environment_overrides_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LOCAL_LLM_ENABLED=true\nOLLAMA_MODEL=dotenv-model\n")
    monkeypatch.setenv("LOCAL_LLM_ENABLED", "false")
    monkeypatch.setenv("OLLAMA_MODEL", "process-model")
    _load_environment(env_file)
    assert config._env_bool("LOCAL_LLM_ENABLED") is False
    assert os.environ["OLLAMA_MODEL"] == "process-model"
