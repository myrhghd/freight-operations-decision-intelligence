"""Explicit local benchmark; never imported by application startup."""

import argparse
import json
from contextlib import ExitStack
from functools import wraps
from pathlib import Path
from statistics import median
from time import perf_counter, sleep
from unittest.mock import patch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cold", action="store_true", help="Unload the configured Ollama model first")
    parser.add_argument("--requests", type=int, default=7)
    parser.add_argument("--timeout", type=float, default=180, help="Process-only diagnostic timeout")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.requests < 7 or args.timeout <= 0:
        parser.error("Use at least seven requests and a positive timeout")

    import ollama
    from chromadb.api.models.Collection import Collection
    from sentence_transformers import SentenceTransformer
    from app.core import config
    from app.rag import retriever
    from app.schemas.local_llm import SOPGenerationResult
    from app.services import assistant_service as assistant

    config.LOCAL_LLM_ENABLED = True
    config.OLLAMA_REQUEST_TIMEOUT_SECONDS = args.timeout
    client = ollama.Client(host=config.OLLAMA_HOST, timeout=args.timeout)
    if args.cold:
        client.generate(model=config.OLLAMA_MODEL, keep_alive=0)
        deadline = perf_counter() + 30
        while any(m.model == config.OLLAMA_MODEL for m in client.ps().models):
            if perf_counter() >= deadline:
                raise RuntimeError("Ollama model did not unload within 30 seconds")
            sleep(0.25)

    metrics = (
        "embedding_init", "query_embedding", "chroma_access", "chroma_query",
        "extractive", "llm_client_init", "llm_request", "validation", "rendering",
    )
    current = {}
    records = []

    def timed(name, function):
        @wraps(function)
        def wrapper(*positional, **keywords):
            started = perf_counter()
            try:
                result = function(*positional, **keywords)
                if name == "llm_request":
                    for field in ("load_duration", "prompt_eval_duration", "eval_duration", "total_duration"):
                        value = getattr(result, field, None)
                        current["ollama_" + field + "_s"] = value / 1e9 if value is not None else None
                    current["prompt_tokens"] = result.prompt_eval_count
                    current["output_tokens"] = result.eval_count
                return result
            finally:
                current[name + "_s"] += perf_counter() - started
                current[name + "_calls"] += 1
        return wrapper

    with ExitStack() as stack:
        for owner, attribute, name in (
            (SentenceTransformer, "__init__", "embedding_init"),
            (SentenceTransformer, "encode", "query_embedding"),
            (retriever, "get_collection", "chroma_access"),
            (Collection, "query", "chroma_query"),
            (assistant, "extractive_answer_from_chunks", "extractive"),
            (ollama.Client, "__init__", "llm_client_init"),
            (ollama.Client, "chat", "llm_request"),
            (assistant, "_render_sop_selection", "rendering"),
        ):
            stack.enter_context(patch.object(owner, attribute, timed(name, getattr(owner, attribute))))
        for attribute in ("model_validate_json", "model_validate"):
            stack.enter_context(patch.object(SOPGenerationResult, attribute,
                staticmethod(timed("validation", getattr(SOPGenerationResult, attribute)))))

        for index in range(args.requests):
            current = {name + suffix: 0 for name in metrics for suffix in ("_s", "_calls")}
            current["request"] = index + 1
            current["phase"] = "cold" if index == 0 and args.cold else "second" if index == 1 else "warm"
            started = perf_counter()
            response = assistant.build_chat_response("What is the customer notification policy?")
            current["total_s"] = perf_counter() - started
            assert set(response) == {"question", "route", "answer", "data", "sources"}
            assert response["route"] == "sop_search"
            current["enhanced"] = current["rendering_calls"] == 1
            current["other_s"] = current["total_s"] - sum(current[name + "_s"] for name in metrics)
            records.append(current)
            print(json.dumps(current), flush=True)

    warm = records[2:]
    summary = {key: {"min": min(row[key] for row in warm),
                     "median": median(row[key] for row in warm),
                     "max": max(row[key] for row in warm)}
               for key in ("total_s",) + tuple(name + "_s" for name in metrics)}
    report = {"model": config.OLLAMA_MODEL, "keep_alive": config.OLLAMA_KEEP_ALIVE,
              "timeout": args.timeout, "cold_unload": args.cold, "records": records,
              "warm_summary": summary}
    print(json.dumps({"warm_summary": summary}), flush=True)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
