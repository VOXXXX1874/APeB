from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data import (
    DataValidationError,
    EvalSample,
    convert_release_dataset,
    load_dataset,
)


def _sample(sample_id: str = "sample_001") -> dict:
    return {
        "schema_version": "apeb.eval.v1",
        "sample_id": sample_id,
        "task": "predict_order",
        "prompt": "<history>\n1. Product name: A; Price: 1 USD\n</history>\n"
        "<query>portable item</query>\n"
        "<candidates>\n1. Product name: B; Price: 2 USD\n</candidates>",
        "resources": {
            "history": {"history_p_001": "Product name:\nA"},
            "candidates": {"candidate_p_001": "Product name:\nB"},
        },
        "answer_indices": [1],
        "metadata": {},
    }


def _manifest(representation: str) -> dict:
    return {
        "schema_version": "apeb.dataset-manifest.v1",
        "dataset_name": "synthetic-test",
        "dataset_version": "1.0",
        "license": "CC-BY-NC-ND-4.0",
        "privacy_reviewed": True,
        "representation": representation,
    }


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(value) + "\n" for value in values), encoding="utf-8"
    )


def test_combined_and_split_are_equivalent(tmp_path: Path) -> None:
    combined = tmp_path / "combined"
    split = tmp_path / "split"
    combined.mkdir()
    split.mkdir()
    sample = _sample()

    _write_json(combined / "dataset_manifest.json", _manifest("combined"))
    _write_jsonl(combined / "samples.jsonl", [sample])

    _write_json(split / "dataset_manifest.json", _manifest("split"))
    prompt = dict(sample)
    resources = prompt.pop("resources")
    _write_jsonl(split / "prompts.jsonl", [prompt])
    _write_jsonl(
        split / "details.jsonl",
        [
            {
                "schema_version": "apeb.eval.v1",
                "sample_id": sample["sample_id"],
                "resources": resources,
            }
        ],
    )

    combined_loaded = load_dataset(combined)
    split_loaded = load_dataset(split)
    assert combined_loaded.samples == split_loaded.samples


def test_unknown_sample_fields_are_rejected() -> None:
    value = _sample()
    value["unexpected_field"] = "marker"
    with pytest.raises(ValueError):
        EvalSample.model_validate(value)


def test_duplicate_sample_ids_are_rejected(tmp_path: Path) -> None:
    _write_json(tmp_path / "dataset_manifest.json", _manifest("combined"))
    _write_jsonl(tmp_path / "samples.jsonl", [_sample(), _sample()])
    with pytest.raises(DataValidationError, match="duplicate sample_id"):
        load_dataset(tmp_path)


def _write_release_package(root: Path) -> None:
    prompts = root / "simple_prompt" / "enselected_encrypted_open"
    details = root / "history_details" / "enselected_240_encrypted_open"
    prompts.mkdir(parents=True)
    details.mkdir(parents=True)
    records = {
        "0000000000000000001": {
            "prompt": "<history>\n1. Action type: view; Product name: A\n</history>\n"
            "<query>portable item</query>\n"
            "<candidates>\n1. Product name: B\n2. Product name: C\n</candidates>",
            "answer": [2],
        },
        "0000000000000000002": {
            "prompt": "<history>\n1. Action type: order; Product name: D\n</history>\n"
            "<query>another item</query>\n"
            "<candidates>\n1. Product name: E\n</candidates>",
            "answer": [1],
        },
    }
    _write_json(prompts / "1016_1020_prompt.json", records)
    _write_json(
        details / "1016_1020_detailed_information.json",
        {
            record_id: {
                "history_actions_informations": {"history_p_001": "detail history"},
                "candidates_informations": {"candidate_p_001": "detail candidate"},
            }
            for record_id in records
        },
    )
    # The structured variant must not be picked up as the detail source.
    _write_json(
        details / "1016_1020_detailed_information_dict.json",
        {record_id: {"unused": True} for record_id in records},
    )


def test_release_conversion_builds_eval_samples(tmp_path: Path) -> None:
    package = tmp_path / "release"
    _write_release_package(package)
    output = tmp_path / "converted"

    converted = convert_release_dataset(package, output)

    assert [sample.sample_id for sample in converted.samples] == [
        "sample_000001",
        "sample_000002",
    ]
    assert converted.samples[0].answer_indices == [2]
    assert converted.samples[0].metadata == {
        "release_bucket": "1016_1020",
        "release_record_id": "0000000000000000001",
    }
    assert converted.samples[0].resources.candidates == {
        "candidate_p_001": "detail candidate"
    }
    assert converted.manifest.privacy_reviewed is True
    assert load_dataset(output).samples == converted.samples


def test_release_conversion_applies_limit(tmp_path: Path) -> None:
    package = tmp_path / "release"
    _write_release_package(package)

    converted = convert_release_dataset(package, tmp_path / "limited", limit=1)

    assert [sample.sample_id for sample in converted.samples] == ["sample_000001"]


def test_release_conversion_requires_detail_files(tmp_path: Path) -> None:
    package = tmp_path / "release"
    prompts = package / "simple_prompt" / "enselected_encrypted_open"
    prompts.mkdir(parents=True)
    _write_json(
        prompts / "1016_1020_prompt.json",
        {"0000000000000000001": {"prompt": "prompt", "answer": [1]}},
    )

    with pytest.raises(DataValidationError, match="missing release detail file"):
        convert_release_dataset(package, tmp_path / "converted")

