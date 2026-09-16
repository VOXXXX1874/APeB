"""Public dataset schema, validation, and release conversion helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


SAMPLE_SCHEMA_VERSION = "apeb.eval.v1"
MANIFEST_SCHEMA_VERSION = "apeb.dataset-manifest.v1"
DATASET_LICENSE = "CC-BY-NC-ND-4.0"
_SAMPLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class DataValidationError(ValueError):
    """A validation error whose message never includes dataset contents."""


class ResourceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    history: dict[str, str] = Field(default_factory=dict)
    candidates: dict[str, str]

    @field_validator("history", "candidates")
    @classmethod
    def validate_resource_map(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key.strip() for key in value):
            raise ValueError("resource identifiers must be non-empty")
        if any(not isinstance(text, str) for text in value.values()):
            raise ValueError("resource values must be strings")
        return value

    @field_validator("candidates")
    @classmethod
    def require_candidates(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("at least one candidate resource is required")
        return value


class EvalSample(BaseModel):
    """One public APeB evaluation sample."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["apeb.eval.v1"] = SAMPLE_SCHEMA_VERSION
    sample_id: str
    task: Literal["predict_order"] = "predict_order"
    prompt: str
    resources: ResourceBundle
    answer_indices: list[int]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sample_id")
    @classmethod
    def validate_sample_id(cls, value: str) -> str:
        if not _SAMPLE_ID_RE.fullmatch(value):
            raise ValueError(
                "sample_id must contain only letters, digits, '.', '_', or '-'"
            )
        return value

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must be non-empty")
        return value

    @field_validator("answer_indices")
    @classmethod
    def validate_answers(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("answer_indices must contain at least one index")
        if any(index < 0 for index in value):
            raise ValueError("answer indices must be non-negative")
        if len(value) != len(set(value)):
            raise ValueError("answer indices must be unique")
        return value


class DatasetManifest(BaseModel):
    """Release metadata required next to every public dataset shard."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["apeb.dataset-manifest.v1"] = MANIFEST_SCHEMA_VERSION
    dataset_name: str
    dataset_version: str
    license: Literal["CC-BY-NC-ND-4.0"]
    privacy_reviewed: bool
    representation: Literal["combined", "split"]
    source_url: str | None = None
    notes: str | None = None

    @field_validator("dataset_name", "dataset_version", "license")
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must be non-empty")
        return value.strip()


@dataclass(frozen=True)
class LoadedDataset:
    samples: list[EvalSample]
    manifest: DatasetManifest
    data_path: Path
    details_path: Path | None
    manifest_path: Path


def _safe_validation_message(
    kind: str, path: Path, line_number: int | None, error: ValidationError
) -> str:
    locations = []
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in item.get("loc", ())) or "record"
        locations.append(f"{location}: {item['msg']}")
    where = f"{path}"
    if line_number is not None:
        where += f":{line_number}"
    return f"invalid {kind} at {where} ({'; '.join(locations)})"


def _read_json_file(path: Path, kind: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as error:
        raise DataValidationError(f"missing {kind}: {path}") from error
    except json.JSONDecodeError as error:
        raise DataValidationError(
            f"invalid JSON in {kind} at {path}:{error.lineno}"
        ) from error
    if not isinstance(value, dict):
        raise DataValidationError(f"{kind} must contain a JSON object: {path}")
    return value


def _read_jsonl(path: Path, kind: str) -> list[tuple[int, dict[str, Any]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise DataValidationError(
                        f"invalid JSON in {kind} at {path}:{line_number}"
                    ) from error
                if not isinstance(record, dict):
                    raise DataValidationError(
                        f"{kind} record must be an object at {path}:{line_number}"
                    )
                records.append((line_number, record))
    except FileNotFoundError as error:
        raise DataValidationError(f"missing {kind}: {path}") from error
    if not records:
        raise DataValidationError(f"{kind} contains no records: {path}")
    return records


def _resolve_paths(
    data: str | Path,
    details: str | Path | None,
    manifest: str | Path | None,
) -> tuple[Path, Path | None, Path]:
    data_path = Path(data)
    if data_path.is_dir():
        root = data_path
        manifest_path = Path(manifest) if manifest else root / "dataset_manifest.json"
        if details:
            raise DataValidationError("--details cannot be used when DATA is a directory")
        if (root / "samples.jsonl").exists():
            return root / "samples.jsonl", None, manifest_path
        return root / "prompts.jsonl", root / "details.jsonl", manifest_path

    manifest_path = (
        Path(manifest) if manifest else data_path.parent / "dataset_manifest.json"
    )
    return data_path, Path(details) if details else None, manifest_path


def load_dataset(
    data: str | Path,
    *,
    details: str | Path | None = None,
    manifest: str | Path | None = None,
) -> LoadedDataset:
    """Load and strictly validate combined or split public data."""

    data_path, details_path, manifest_path = _resolve_paths(data, details, manifest)
    manifest_raw = _read_json_file(manifest_path, "dataset manifest")
    try:
        parsed_manifest = DatasetManifest.model_validate(manifest_raw)
    except ValidationError as error:
        raise DataValidationError(
            _safe_validation_message("dataset manifest", manifest_path, None, error)
        ) from error

    if parsed_manifest.representation == "combined" and details_path is not None:
        raise DataValidationError("combined manifest cannot be loaded with details data")
    if parsed_manifest.representation == "split" and details_path is None:
        raise DataValidationError("split manifest requires details.jsonl")

    raw_samples: list[tuple[int, dict[str, Any]]]
    if details_path is None:
        raw_samples = _read_jsonl(data_path, "samples")
    else:
        prompt_records = _read_jsonl(data_path, "prompts")
        detail_records = _read_jsonl(details_path, "details")
        details_by_id: dict[str, dict[str, Any]] = {}
        for line_number, record in detail_records:
            allowed = {"schema_version", "sample_id", "resources"}
            if set(record) != allowed:
                raise DataValidationError(
                    f"invalid details fields at {details_path}:{line_number}"
                )
            if record.get("schema_version") != SAMPLE_SCHEMA_VERSION:
                raise DataValidationError(
                    f"invalid details schema_version at {details_path}:{line_number}"
                )
            sample_id = record.get("sample_id")
            if not isinstance(sample_id, str):
                raise DataValidationError(
                    f"details sample_id must be a string at {details_path}:{line_number}"
                )
            if sample_id in details_by_id:
                raise DataValidationError(f"duplicate details sample_id: {sample_id}")
            details_by_id[sample_id] = record

        raw_samples = []
        for line_number, prompt_record in prompt_records:
            sample_id = prompt_record.get("sample_id")
            detail_record = details_by_id.pop(sample_id, None)
            if detail_record is None:
                raise DataValidationError(f"missing details for sample_id: {sample_id}")
            merged = dict(prompt_record)
            merged["resources"] = detail_record["resources"]
            raw_samples.append((line_number, merged))
        if details_by_id:
            raise DataValidationError(
                f"details contain {len(details_by_id)} sample_id(s) without prompts"
            )

    samples: list[EvalSample] = []
    seen: set[str] = set()
    for line_number, record in raw_samples:
        try:
            sample = EvalSample.model_validate(record)
        except ValidationError as error:
            raise DataValidationError(
                _safe_validation_message("sample", data_path, line_number, error)
            ) from error
        if sample.sample_id in seen:
            raise DataValidationError(f"duplicate sample_id: {sample.sample_id}")
        seen.add(sample.sample_id)
        samples.append(sample)

    return LoadedDataset(
        samples=samples,
        manifest=parsed_manifest,
        data_path=data_path,
        details_path=details_path,
        manifest_path=manifest_path,
    )


def _write_jsonl_exclusive(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def _expected_outputs(
    destination: Path, representation: Literal["combined", "split"]
) -> list[Path]:
    expected = [destination / "dataset_manifest.json"]
    expected += (
        [destination / "samples.jsonl"]
        if representation == "combined"
        else [destination / "prompts.jsonl", destination / "details.jsonl"]
    )
    return expected


def _require_absent(
    destination: Path, representation: Literal["combined", "split"], action: str
) -> None:
    existing = [
        path for path in _expected_outputs(destination, representation) if path.exists()
    ]
    if existing:
        raise DataValidationError(
            f"refusing to overwrite {action}: "
            + ", ".join(str(path) for path in existing)
        )


def _write_dataset(
    destination: Path,
    samples: list[EvalSample],
    manifest: DatasetManifest,
    representation: Literal["combined", "split"],
) -> tuple[Path, Path | None]:
    manifest_path = destination / "dataset_manifest.json"
    with manifest_path.open("x", encoding="utf-8") as handle:
        json.dump(manifest.model_dump(mode="json"), handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    if representation == "combined":
        data_path = destination / "samples.jsonl"
        details_path = None
        _write_jsonl_exclusive(
            data_path, (sample.model_dump(mode="json") for sample in samples)
        )
        return data_path, details_path

    data_path = destination / "prompts.jsonl"
    details_path = destination / "details.jsonl"
    prompt_records = []
    detail_records = []
    for sample in samples:
        record = sample.model_dump(mode="json")
        resources = record.pop("resources")
        prompt_records.append(record)
        detail_records.append(
            {
                "schema_version": SAMPLE_SCHEMA_VERSION,
                "sample_id": sample.sample_id,
                "resources": resources,
            }
        )
    _write_jsonl_exclusive(data_path, prompt_records)
    _write_jsonl_exclusive(details_path, detail_records)
    return data_path, details_path


RELEASE_PROMPT_SUFFIX = "_prompt.json"
RELEASE_DETAIL_SUFFIX = "_detailed_information.json"


def _index_release_files(root: Path, family: str, suffix: str) -> dict[str, Path]:
    """Map bucket name to file path for one family of release package files."""

    indexed: dict[str, Path] = {}
    for path in sorted(root.glob(f"{family}/*/*{suffix}")):
        indexed[path.name[: -len(suffix)]] = path
    return indexed


def _record_sort_key(record_id: str) -> tuple[int, str]:
    return (int(record_id), "") if record_id.isdigit() else (1 << 62, record_id)


def convert_release_dataset(
    release_root: str | Path,
    output_dir: str | Path,
    *,
    representation: Literal["combined", "split"] = "combined",
    buckets: Iterable[str] | None = None,
    limit: int | None = None,
    dataset_name: str = "apeb-release",
    dataset_version: str = "1.0.0",
) -> LoadedDataset:
    """Convert a downloaded APeB release package into ``apeb.eval.v1`` data."""

    root = Path(release_root)
    if not root.is_dir():
        raise DataValidationError(f"release package directory does not exist: {root}")

    prompt_files = _index_release_files(root, "simple_prompt", RELEASE_PROMPT_SUFFIX)
    if not prompt_files:
        raise DataValidationError(
            "no release prompt files found under "
            f"{root}/simple_prompt/*/*{RELEASE_PROMPT_SUFFIX}"
        )
    detail_files = _index_release_files(
        root, "history_details", RELEASE_DETAIL_SUFFIX
    )

    selected = sorted(prompt_files) if buckets is None else sorted(set(buckets))
    unknown = [bucket for bucket in selected if bucket not in prompt_files]
    if unknown:
        raise DataValidationError("unknown bucket(s): " + ", ".join(unknown))
    missing_details = [bucket for bucket in selected if bucket not in detail_files]
    if missing_details:
        raise DataValidationError(
            "missing release detail file for bucket(s): "
            + ", ".join(missing_details)
            + f"; download history_details/*/*{RELEASE_DETAIL_SUFFIX} as well"
        )
    if limit is not None and limit < 1:
        raise DataValidationError("limit must be positive")

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    _require_absent(destination, representation, "conversion output")

    converted: list[EvalSample] = []
    for bucket in selected:
        prompt_records = _read_json_file(prompt_files[bucket], "release prompt file")
        detail_records = _read_json_file(detail_files[bucket], "release detail file")
        for record_id in sorted(prompt_records, key=_record_sort_key):
            if limit is not None and len(converted) >= limit:
                break
            prompt_record = prompt_records[record_id]
            detail_record = detail_records.get(record_id)
            if not isinstance(prompt_record, dict):
                raise DataValidationError(
                    f"release record {record_id} must be a JSON object in bucket {bucket}"
                )
            if not isinstance(detail_record, dict):
                raise DataValidationError(
                    f"release record {record_id} is missing from the detail file "
                    f"of bucket {bucket}"
                )
            raw_sample = {
                "schema_version": SAMPLE_SCHEMA_VERSION,
                "sample_id": f"sample_{len(converted) + 1:06d}",
                "task": "predict_order",
                "prompt": prompt_record.get("prompt"),
                "resources": {
                    "history": detail_record.get("history_actions_informations", {}),
                    "candidates": detail_record.get("candidates_informations", {}),
                },
                "answer_indices": prompt_record.get("answer"),
                "metadata": {
                    "release_bucket": bucket,
                    "release_record_id": str(record_id),
                },
            }
            try:
                converted.append(EvalSample.model_validate(raw_sample))
            except ValidationError as error:
                raise DataValidationError(
                    _safe_validation_message(
                        "release sample", prompt_files[bucket], None, error
                    )
                ) from error
        if limit is not None and len(converted) >= limit:
            break

    if not converted:
        raise DataValidationError("no samples were converted")

    manifest = DatasetManifest(
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        license=DATASET_LICENSE,
        privacy_reviewed=True,
        representation=representation,
        notes="Converted from the published APeB release package.",
    )
    data_path, details_path = _write_dataset(
        destination, converted, manifest, representation
    )
    return LoadedDataset(
        samples=converted,
        manifest=manifest,
        data_path=data_path,
        details_path=details_path,
        manifest_path=destination / "dataset_manifest.json",
    )
