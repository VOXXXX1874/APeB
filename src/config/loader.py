# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
import re
from typing import Any, Dict

import yaml


_ENV_REFERENCE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_ENV_ONLY_KEY_PARTS = (
    "api_key",
    "token",
    "secret",
    "password",
    "endpoint",
    "base_url",
)


def replace_env_vars(value: str) -> str:
    """Resolve an exact ``${NAME}`` reference without exposing its value."""
    if not isinstance(value, str):
        return value
    match = _ENV_REFERENCE.fullmatch(value)
    if match:
        env_var = match.group(1)
        if env_var not in os.environ:
            raise ValueError(f"required environment variable is not set: {env_var}")
        return os.environ[env_var]
    return value


def process_dict(config: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively process dictionary to replace environment variables."""
    if not config:
        return {}
    result = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = process_dict(value)
        elif isinstance(value, str):
            normalized_key = str(key).lower()
            if any(part in normalized_key for part in _ENV_ONLY_KEY_PARTS):
                if not _ENV_REFERENCE.fullmatch(value):
                    raise ValueError(
                        f"configuration field '{key}' must use an exact ${{ENV_NAME}} reference"
                    )
            result[key] = replace_env_vars(value)
        else:
            result[key] = value
    return result


_config_cache: Dict[str, Dict[str, Any]] = {}


def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """Load a YAML object and resolve explicit environment references."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"configuration file does not exist: {file_path}")

    # 检查缓存中是否已存在配置
    if file_path in _config_cache:
        return _config_cache[file_path]

    # 如果缓存中不存在，则加载并处理配置
    with open(file_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError("configuration root must be a mapping")
    processed_config = process_dict(config)

    # 将处理后的配置存入缓存
    _config_cache[file_path] = processed_config
    return processed_config
