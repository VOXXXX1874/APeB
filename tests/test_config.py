from pathlib import Path

import pytest

from src.config.loader import load_yaml_config


def test_sensitive_config_fields_require_environment_reference(tmp_path: Path) -> None:
    field = "api_" + "key"
    value = "literal-" + "credential-marker"
    path = tmp_path / "models.yaml"
    path.write_text(f"BASIC_MODEL:\n  default:\n    {field}: {value}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must use an exact") as error:
        load_yaml_config(str(path))
    assert value not in str(error.value)


def test_environment_reference_is_resolved(monkeypatch, tmp_path: Path) -> None:
    variable = "APEB_TEST_CREDENTIAL"
    marker = "runtime-value-marker"
    monkeypatch.setenv(variable, marker)
    path = tmp_path / "models.yaml"
    path.write_text(
        "BASIC_MODEL:\n  default:\n    api_key: ${APEB_TEST_CREDENTIAL}\n",
        encoding="utf-8",
    )
    loaded = load_yaml_config(str(path))
    assert loaded["BASIC_MODEL"]["default"]["api_key"] == marker
