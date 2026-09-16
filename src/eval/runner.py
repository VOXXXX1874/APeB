"""Unified, privacy-aware adapters for the released evaluation methods."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from src.data import EvalSample
from src.utils.metrics import evaluate_ranking


logger = logging.getLogger(__name__)

FRAMEWORKS = ("raw", "react", "asareact", "deerflow", "vqra", "memagent")
TOOLS = ("retriever", "web_search", "crawl", "python_repl")
NETWORK_TOOLS = frozenset({"web_search", "crawl"})


class EvaluationConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class EvaluationOptions:
    framework: str
    model: str
    tools: tuple[str, ...] = ("retriever",)
    allow_network_tools: bool = False
    allow_code_execution: bool = False
    system_prompt: str = "basic"
    tools_system_prompt: str = "tools"
    max_workers: int = 10
    majority_voting: int = 1
    section_size: int = 5
    researcher_model: str | None = None


def validate_options(options: EvaluationOptions) -> None:
    if options.framework not in FRAMEWORKS:
        raise EvaluationConfigurationError(
            f"unsupported framework '{options.framework}'"
        )
    unknown = sorted(set(options.tools) - set(TOOLS))
    if unknown:
        raise EvaluationConfigurationError(f"unsupported tool(s): {', '.join(unknown)}")
    if set(options.tools) & NETWORK_TOOLS and not options.allow_network_tools:
        raise EvaluationConfigurationError(
            "web_search and crawl require --allow-network-tools"
        )
    if "python_repl" in options.tools and not options.allow_code_execution:
        raise EvaluationConfigurationError(
            "python_repl requires --allow-code-execution"
        )
    supported_tools = {
        "raw": {"retriever"},
        "react": set(TOOLS),
        "asareact": {"retriever"},
        "deerflow": {"retriever", "web_search", "crawl", "python_repl"},
        "vqra": {"retriever"},
        "memagent": {"retriever"},
    }
    unsupported_for_framework = sorted(set(options.tools) - supported_tools[options.framework])
    if unsupported_for_framework:
        raise EvaluationConfigurationError(
            f"{options.framework} does not support tool(s): "
            + ", ".join(unsupported_for_framework)
        )
    if options.researcher_model and options.framework != "deerflow":
        raise EvaluationConfigurationError("--researcher-model is only valid for deerflow")
    if options.max_workers < 1:
        raise EvaluationConfigurationError("max_workers must be positive")
    if options.majority_voting < 1:
        raise EvaluationConfigurationError("majority_voting must be positive")
    if options.section_size < 1:
        raise EvaluationConfigurationError("section_size must be positive")
    model_type_from_location(options.model)
    if options.researcher_model:
        model_type_from_location(options.researcher_model)


def model_type_from_location(location: str) -> str:
    try:
        group, name = location.split("/", maxsplit=1)
    except ValueError as error:
        raise EvaluationConfigurationError(
            "model must use GROUP/NAME, for example BASIC_MODEL/default"
        ) from error
    if not name:
        raise EvaluationConfigurationError("model name cannot be empty")
    if group == "BASIC_MODEL":
        return "basic"
    if group == "REASONING_MODEL":
        return "reasoning"
    raise EvaluationConfigurationError(
        "model group must be BASIC_MODEL or REASONING_MODEL"
    )


def _write_task_records(path: Path, samples: Sequence[EvalSample]) -> None:
    """Write the internal record shape the method implementations consume."""

    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        for sample in samples:
            record = {
                "sample_id": sample.sample_id,
                "prompt": sample.prompt,
                "history_actions_informations": sample.resources.history,
                "candidates_informations": sample.resources.candidates,
                "answer_indices": sample.answer_indices,
            }
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


async def _dispatch(
    options: EvaluationOptions, data_path: Path
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], int]:
    llm_type = model_type_from_location(options.model)
    common = (llm_type, options.model, str(data_path))

    if options.framework == "raw":
        from src.eval.llm_eval import llm_eval

        return await llm_eval(
            *common,
            options.system_prompt,
            options.max_workers,
            options.majority_voting,
        )
    if options.framework == "react":
        from src.eval.react_eval import react_eval

        return await react_eval(
            *common,
            list(options.tools),
            options.system_prompt,
            options.max_workers,
        )
    if options.framework == "asareact":
        from src.eval.asareact_eval import asareact_eval

        return await asareact_eval(
            *common,
            options.system_prompt,
            options.tools_system_prompt,
            options.max_workers,
        )
    if options.framework == "deerflow":
        from src.eval.deerflow_eval import deerflow_eval

        return await deerflow_eval(
            llm_type,
            options.model,
            options.researcher_model,
            str(data_path),
            list(options.tools),
            options.max_workers,
        )
    if options.framework == "vqra":
        from src.eval.vqra_eval import vqra_eval

        return await vqra_eval(
            *common,
            options.system_prompt,
            str(data_path),
            options.max_workers,
        )
    if options.framework == "memagent":
        from src.eval.memagent_eval import memagent_eval

        return await memagent_eval(
            *common,
            options.section_size,
            options.max_workers,
        )
    raise AssertionError("framework validation and dispatch are out of sync")


def _extract_ranking(response: Any) -> list[int] | None:
    if not isinstance(response, dict) or not isinstance(response.get("products"), list):
        return None
    products = response["products"]
    ranked: list[tuple[int, int]] = []
    for product in products:
        if not isinstance(product, dict):
            return None
        rank = product.get("rank")
        index = product.get("index")
        if not isinstance(rank, int) or not isinstance(index, int) or rank < 1:
            return None
        ranked.append((rank, index))
    ranks = [rank for rank, _ in ranked]
    indices = [index for _, index in ranked]
    if len(ranks) != len(set(ranks)) or len(indices) != len(set(indices)):
        return None
    return [index for _, index in sorted(ranked)]


async def evaluate_samples(
    samples: Sequence[EvalSample], options: EvaluationOptions, *, work_dir: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Run one framework and return a summary, safe results, and opt-in artifacts."""

    validate_options(options)
    work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix=".apeb-eval-", dir=work_dir) as temp_dir:
        records_path = Path(temp_dir) / "samples.jsonl"
        _write_task_records(records_path, samples)
        try:
            _, _, raw_results, _ = await _dispatch(options, records_path)
        except Exception as error:
            logger.error(
                "Framework execution failed without recording request content: %s: %s",
                type(error).__name__,
                error,
                exc_info=True,
            )
            raise EvaluationConfigurationError(
                "framework execution failed; check provider availability and local configuration"
            ) from error
    elapsed = time.perf_counter() - started

    raw_by_id = {str(item.get("sample_id")): item for item in raw_results}
    safe_results: list[dict[str, Any]] = []
    private_artifacts: list[dict[str, Any]] = []
    for sample in samples:
        raw = raw_by_id.get(sample.sample_id, {})
        ranking = _extract_ranking(raw.get("response"))
        status = "ok" if ranking is not None else "invalid_response"
        metrics = evaluate_ranking(ranking or [], sample.answer_indices)
        result = {
            "schema_version": "apeb.result.v1",
            "sample_id": sample.sample_id,
            "framework": options.framework,
            "status": status,
            "predicted_indices": ranking,
            "answer_indices": sample.answer_indices,
            "metrics": metrics,
        }
        safe_results.append(result)
        artifact: dict[str, Any] = {
            "sample_id": sample.sample_id,
            "response": raw.get("response"),
        }
        if "react_messages" in raw:
            artifact["trace"] = raw.get("react_messages")
        private_artifacts.append(artifact)
        logger.info(
            "sample_id=%s framework=%s status=%s",
            sample.sample_id,
            options.framework,
            status,
        )

    valid = [result for result in safe_results if result["status"] == "ok"]
    summary = {
        "schema_version": "apeb.summary.v1",
        "framework": options.framework,
        "model": options.model,
        "sample_count": len(safe_results),
        "valid_count": len(valid),
        "invalid_count": len(safe_results) - len(valid),
        "metrics_all": _mean_metrics(safe_results),
        "metrics_valid": _mean_metrics(valid) if valid else None,
        "elapsed_seconds": round(elapsed, 6),
        "privacy": {
            "network_tools_enabled": bool(set(options.tools) & NETWORK_TOOLS),
            "code_execution_enabled": "python_repl" in options.tools,
        },
    }
    return summary, safe_results, private_artifacts


def _mean_metrics(results: Sequence[dict[str, Any]]) -> dict[str, float] | None:
    if not results:
        return None
    keys = ("recall_at_1", "recall_at_3", "recall_at_5")
    return {
        key: sum(float(result["metrics"][key]) for result in results) / len(results)
        for key in keys
    }


def summarize_result_files(paths: Sequence[Path]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for supplied in paths:
        path = supplied / "results.jsonl" if supplied.is_dir() else supplied
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as error:
                        raise EvaluationConfigurationError(
                            f"invalid result JSON at {path}:{line_number}"
                        ) from error
                    if record.get("schema_version") != "apeb.result.v1":
                        raise EvaluationConfigurationError(
                            f"unsupported result schema at {path}:{line_number}"
                        )
                    results.append(record)
        except FileNotFoundError as error:
            raise EvaluationConfigurationError(f"missing results file: {path}") from error
    if not results:
        raise EvaluationConfigurationError("no result records found")
    valid = [result for result in results if result.get("status") == "ok"]
    frameworks = sorted({str(result.get("framework")) for result in results})
    return {
        "schema_version": "apeb.summary.v1",
        "frameworks": frameworks,
        "sample_count": len(results),
        "valid_count": len(valid),
        "invalid_count": len(results) - len(valid),
        "metrics_all": _mean_metrics(results),
        "metrics_valid": _mean_metrics(valid) if valid else None,
    }


def run_evaluation(
    samples: Sequence[EvalSample], options: EvaluationOptions, *, work_dir: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    return asyncio.run(evaluate_samples(samples, options, work_dir=work_dir))
