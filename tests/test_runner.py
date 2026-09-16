from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

from src.data import EvalSample
from src.eval import runner


def _sample() -> EvalSample:
    return EvalSample.model_validate(
        {
            "schema_version": "apeb.eval.v1",
            "sample_id": "sample_001",
            "task": "predict_order",
            "prompt": "<history>history</history>\n<query>query</query>\n"
            "<candidates>\n1. candidate\n</candidates>",
            "resources": {
                "history": {"history_p_001": "history detail"},
                "candidates": {"candidate_p_001": "candidate detail"},
            },
            "answer_indices": [1],
            "metadata": {},
        }
    )


@pytest.mark.parametrize(
    "tools,network,code,message",
    [
        (("web_search",), False, False, "allow-network-tools"),
        (("crawl",), False, False, "allow-network-tools"),
        (("python_repl",), False, False, "allow-code-execution"),
    ],
)
def test_sensitive_tools_require_explicit_gates(
    tools: tuple[str, ...], network: bool, code: bool, message: str
) -> None:
    options = runner.EvaluationOptions(
        framework="react",
        model="BASIC_MODEL/default",
        tools=tools,
        allow_network_tools=network,
        allow_code_execution=code,
    )
    with pytest.raises(runner.EvaluationConfigurationError, match=message):
        runner.validate_options(options)


def test_local_retriever_is_safe_default() -> None:
    options = runner.EvaluationOptions(
        framework="react", model="BASIC_MODEL/default"
    )
    runner.validate_options(options)
    assert options.tools == ("retriever",)


@pytest.mark.parametrize("framework", runner.FRAMEWORKS)
def test_all_framework_adapters_accept_fake_provider(
    framework: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: dict = {}

    async def fake_dispatch(options, data_path):
        observed["record"] = json.loads(data_path.read_text(encoding="utf-8"))
        return (
            {},
            {},
            [
                {
                    "sample_id": "sample_001",
                    "response": {"products": [{"rank": 1, "index": 1}]},
                    "react_messages": ["private trace"],
                }
            ],
            0,
        )

    monkeypatch.setattr(runner, "_dispatch", fake_dispatch)
    options = runner.EvaluationOptions(
        framework=framework,
        model="BASIC_MODEL/default",
        tools=("retriever",),
    )
    summary, results, artifacts = asyncio.run(
        runner.evaluate_samples([_sample()], options, work_dir=tmp_path)
    )

    record = observed["record"]
    assert record["sample_id"] == "sample_001"
    assert record["prompt"] == _sample().prompt
    assert set(record) == {
        "sample_id",
        "prompt",
        "history_actions_informations",
        "candidates_informations",
        "answer_indices",
    }
    assert results[0]["predicted_indices"] == [1]
    assert "response" not in results[0]
    assert summary["valid_count"] == 1
    assert artifacts[0]["trace"] == ["private trace"]


@pytest.mark.parametrize(
    "framework,module_name,function_name",
    [
        ("raw", "src.eval.llm_eval", "llm_eval"),
        ("react", "src.eval.react_eval", "react_eval"),
        ("asareact", "src.eval.asareact_eval", "asareact_eval"),
        ("deerflow", "src.eval.deerflow_eval", "deerflow_eval"),
        ("vqra", "src.eval.vqra_eval", "vqra_eval"),
        ("memagent", "src.eval.memagent_eval", "memagent_eval"),
    ],
)
def test_dispatch_is_lazy_and_routes_each_method(
    framework: str,
    module_name: str,
    function_name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    called = []

    async def fake_method(*args):
        called.append(args)
        return {}, {}, [], 0

    fake_module = types.ModuleType(module_name)
    setattr(fake_module, function_name, fake_method)
    monkeypatch.setitem(sys.modules, module_name, fake_module)
    data_path = tmp_path / "samples.jsonl"
    data_path.write_text("{}\n", encoding="utf-8")
    options = runner.EvaluationOptions(
        framework=framework,
        model="BASIC_MODEL/default",
        tools=("retriever",),
    )
    asyncio.run(runner._dispatch(options, data_path))
    assert len(called) == 1
