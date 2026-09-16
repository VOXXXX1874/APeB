"""Command-line interface for the public APeB evaluation release."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from src.data import (
    DataValidationError,
    convert_release_dataset,
    load_dataset,
)


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _add_dataset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "data",
        help="Dataset directory, combined samples.jsonl, or split prompts.jsonl",
    )
    parser.add_argument("--details", help="details.jsonl for split data")
    parser.add_argument("--manifest", help="dataset_manifest.json path")
    parser.add_argument(
        "--allow-unreviewed-data",
        action="store_true",
        help="Allow a manifest with privacy_reviewed=false",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apeb",
        description="Agent Personalization Benchmark evaluation tools",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-data", help="Validate public data")
    _add_dataset_arguments(validate)
    validate.set_defaults(handler=_cmd_validate)

    convert = subparsers.add_parser(
        "convert-release",
        help="Convert a downloaded release package into apeb.eval.v1 data",
    )
    convert.add_argument(
        "release_dir", help="Directory of the downloaded APeB release package"
    )
    convert.add_argument("--output-dir", type=Path, required=True)
    convert.add_argument(
        "--representation", choices=("combined", "split"), default="combined"
    )
    convert.add_argument(
        "--buckets", nargs="+", help="Convert only these bucket directories"
    )
    convert.add_argument(
        "--limit", type=int, help="Stop after this many converted samples"
    )
    convert.add_argument("--dataset-name", default="apeb-release")
    convert.add_argument("--dataset-version", default="1.0.0")
    convert.set_defaults(handler=_cmd_convert_release)

    evaluate = subparsers.add_parser("evaluate", help="Run one evaluation method")
    _add_dataset_arguments(evaluate)
    evaluate.add_argument(
        "--framework",
        required=True,
        choices=("raw", "react", "asareact", "deerflow", "vqra", "memagent"),
    )
    evaluate.add_argument(
        "--model",
        required=True,
        help="Model location from the config, for example BASIC_MODEL/default",
    )
    evaluate.add_argument(
        "--model-config",
        type=Path,
        help="Local YAML model config (or set APEB_MODEL_CONFIG)",
    )
    evaluate.add_argument("--researcher-model")
    evaluate.add_argument("--output-dir", type=Path, required=True)
    evaluate.add_argument(
        "--tools",
        nargs="+",
        default=["retriever"],
        choices=(
            "retriever",
            "web_search",
            "crawl",
            "python_repl",
        ),
    )
    evaluate.add_argument("--allow-network-tools", action="store_true")
    evaluate.add_argument("--allow-code-execution", action="store_true")
    evaluate.add_argument("--system-prompt", default="basic")
    evaluate.add_argument("--tools-system-prompt", default="tools")
    evaluate.add_argument("--max-workers", type=int, default=10)
    evaluate.add_argument("--majority-voting", type=int, default=1)
    evaluate.add_argument("--section-size", type=int, default=5)
    evaluate.add_argument(
        "--save-responses",
        action="store_true",
        help="Write full model responses to a separate sensitive artifact",
    )
    evaluate.add_argument(
        "--save-traces",
        action="store_true",
        help="Write agent traces to a separate sensitive artifact",
    )
    evaluate.add_argument("--log-level", choices=("WARNING", "INFO"), default="INFO")
    evaluate.set_defaults(handler=_cmd_evaluate)

    summarize = subparsers.add_parser(
        "summarize", help="Aggregate one or more results.jsonl files"
    )
    summarize.add_argument("paths", nargs="+", type=Path)
    summarize.add_argument("--output", type=Path)
    summarize.set_defaults(handler=_cmd_summarize)
    return parser


def _load_checked_dataset(args: argparse.Namespace):
    dataset = load_dataset(args.data, details=args.details, manifest=args.manifest)
    if not dataset.manifest.privacy_reviewed and not args.allow_unreviewed_data:
        raise DataValidationError(
            "dataset privacy_reviewed=false; review it or pass --allow-unreviewed-data"
        )
    return dataset


def _cmd_validate(args: argparse.Namespace) -> int:
    dataset = _load_checked_dataset(args)
    print(
        _json_dump(
            {
                "status": "valid",
                "sample_count": len(dataset.samples),
                "representation": dataset.manifest.representation,
                "privacy_reviewed": dataset.manifest.privacy_reviewed,
                "license": dataset.manifest.license,
            }
        )
    )
    return 0


def _cmd_convert_release(args: argparse.Namespace) -> int:
    dataset = convert_release_dataset(
        args.release_dir,
        args.output_dir,
        representation=args.representation,
        buckets=args.buckets,
        limit=args.limit,
        dataset_name=args.dataset_name,
        dataset_version=args.dataset_version,
    )
    print(
        _json_dump(
            {
                "status": "converted",
                "sample_count": len(dataset.samples),
                "output_dir": str(Path(args.output_dir)),
                "representation": dataset.manifest.representation,
                "privacy_reviewed": dataset.manifest.privacy_reviewed,
            }
        )
    )
    return 0


def _write_json_exclusive(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _write_jsonl_exclusive(path: Path, values: Sequence[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def _cmd_evaluate(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    for noisy_logger in ("httpx", "openai", "langchain", "langgraph"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
    dataset = _load_checked_dataset(args)

    model_config = args.model_config or (
        Path(os.environ["APEB_MODEL_CONFIG"]) if os.getenv("APEB_MODEL_CONFIG") else None
    )
    if model_config is None:
        raise DataValidationError(
            "provide --model-config or set APEB_MODEL_CONFIG"
        )
    if not model_config.is_file():
        raise DataValidationError(f"model config does not exist: {model_config}")
    os.environ["APEB_MODEL_CONFIG"] = str(model_config.resolve())

    from src.eval.runner import EvaluationOptions, run_evaluation

    options = EvaluationOptions(
        framework=args.framework,
        model=args.model,
        tools=tuple(dict.fromkeys(args.tools)),
        allow_network_tools=args.allow_network_tools,
        allow_code_execution=args.allow_code_execution,
        system_prompt=args.system_prompt,
        tools_system_prompt=args.tools_system_prompt,
        max_workers=args.max_workers,
        majority_voting=args.majority_voting,
        section_size=args.section_size,
        researcher_model=args.researcher_model,
    )

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    targets = [output_dir / "summary.json", output_dir / "results.jsonl"]
    if args.save_responses:
        targets.append(output_dir / "responses.jsonl")
    if args.save_traces:
        targets.append(output_dir / "traces.jsonl")
    existing = [path for path in targets if path.exists()]
    if existing:
        raise DataValidationError(
            "refusing to overwrite output: " + ", ".join(str(path) for path in existing)
        )

    summary, results, artifacts = run_evaluation(
        dataset.samples, options, work_dir=output_dir
    )
    _write_json_exclusive(output_dir / "summary.json", summary)
    _write_jsonl_exclusive(output_dir / "results.jsonl", results)
    if args.save_responses:
        _write_jsonl_exclusive(
            output_dir / "responses.jsonl",
            [
                {"sample_id": item["sample_id"], "response": item.get("response")}
                for item in artifacts
            ],
        )
    if args.save_traces:
        _write_jsonl_exclusive(
            output_dir / "traces.jsonl",
            [
                {"sample_id": item["sample_id"], "trace": item.get("trace")}
                for item in artifacts
                if "trace" in item
            ],
        )
    print(_json_dump(summary))
    return 0


def _cmd_summarize(args: argparse.Namespace) -> int:
    from src.eval.runner import summarize_result_files

    summary = summarize_result_files(args.paths)
    if args.output:
        _write_json_exclusive(args.output, summary)
    print(_json_dump(summary))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (DataValidationError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
