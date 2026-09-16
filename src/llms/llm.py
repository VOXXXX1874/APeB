# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
import logging
from typing import Any, Dict, Tuple

from langchain_openai import ChatOpenAI, AzureChatOpenAI
from src.llms.deepseekr1wrapper import DeepSeekR1Wrapper

from src.config import load_yaml_config
from src.config.agents import LLMType

logger = logging.getLogger(__name__)

def _get_config_file_path() -> str:
    """Return the explicitly selected local model configuration."""
    path = os.getenv("APEB_MODEL_CONFIG")
    if not path:
        raise ValueError("APEB_MODEL_CONFIG is not set")
    return path


def _get_llm_type_config_keys() -> dict[str, str]:
    """Get mapping of LLM types to their configuration keys."""
    return {
        "reasoning": "REASONING_MODEL",
        "basic": "BASIC_MODEL",
        "vision": "VISION_MODEL",
    }


def _create_llm_use_conf(
    llm_type: LLMType, conf: Dict[str, Any]
) -> ChatOpenAI | DeepSeekR1Wrapper:
    """Create LLM instance using configuration."""
    llm_type_config_keys = _get_llm_type_config_keys()
    config_key = llm_type_config_keys.get(llm_type)

    if not config_key:
        raise ValueError(f"Unknown LLM type: {llm_type}")

    llm_conf = conf.get(config_key, {})
    if not isinstance(llm_conf, dict):
        raise ValueError(f"Invalid LLM configuration for {llm_type}: {llm_conf}")

    if not llm_conf:
        raise ValueError(f"No configuration found for LLM type: {llm_type}")

    if llm_conf.get("azure_endpoint"):
        model = AzureChatOpenAI(**llm_conf)
        if config_key == "REASONING_MODEL" and llm_conf.get("model") == "DeepSeek-R1":
            return DeepSeekR1Wrapper(model)
        return model

    return ChatOpenAI(**llm_conf)



def get_llm_by_type(
    llm_type_location: Tuple[LLMType, str]
) -> ChatOpenAI | DeepSeekR1Wrapper:
    """
    Get LLM instance by type. Returns cached instance if available.
    """
    llm_type, location = llm_type_location
    if not location:
        raise ValueError("a deterministic GROUP/NAME model location is required")
    llm_conf = load_yaml_config(_get_config_file_path())
    try:
        model_type, name = location.split("/", maxsplit=1)
        expected_type = _get_llm_type_config_keys()[llm_type]
        if model_type != expected_type:
            raise ValueError(
                f"model location {location} does not match llm type {llm_type}"
            )
        conf = {model_type: llm_conf[model_type][name]}
    except (KeyError, ValueError) as error:
        raise ValueError(f"model location not found in configuration: {location}") from error
    logger.info("Loading configured model: %s", location)
    llm = _create_llm_use_conf(llm_type, conf)
    logger.info("Successfully loaded LLM")
    return llm
