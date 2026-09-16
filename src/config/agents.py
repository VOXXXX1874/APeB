# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from typing import Literal, Tuple

# Define available LLM types
LLMType = Literal["basic", "reasoning", "vision"]

# Define agent-LLM mapping
AGENT_LLM_MAP: dict[str, Tuple[LLMType, str]] = {
    "coordinator": ("basic", None),
    "planner": ("reasoning", None),
    "researcher": ("basic", None),
    "coder": ("basic", None),
    "reporter": ("reasoning", None),
    "podcast_script_writer": ("basic", None),
    "ppt_composer": ("basic", None),
    "prose_writer": ("basic", None),
    "prompt_enhancer": ("basic", None),
}
