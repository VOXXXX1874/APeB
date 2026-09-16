# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
import dataclasses
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from langgraph.prebuilt.chat_agent_executor import AgentState
from src.config.configuration import Configuration


def get_prompt_template(prompt_name: str) -> str:
    """
    Load and return a prompt template using Jinja2.

    Args:
        prompt_name: Name of the prompt template file (without .md extension)

    Returns:
        The template string with proper variable substitution syntax
    """
    try:
        env = Environment(
        loader=FileSystemLoader(os.path.dirname(__file__)),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )
        template = env.get_template(f"{prompt_name}.md")
        return template.render()
    except Exception as e:
        raise ValueError(f"Error loading template {prompt_name}: {e}")


def apply_prompt_template(
    prompt_name: str, state: AgentState, configurable: Configuration = None
) -> list:
    """
    Apply template variables to a prompt template and return formatted messages.

    Args:
        prompt_name: Name of the prompt template to use
        state: Current agent state containing variables to substitute

    Returns:
        List of messages with the system prompt as the first message
    """
    # Convert state to dict for template rendering
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **state,
    }
    if isinstance(configurable, Configuration):
        task = configurable.task
        system_prompt_path = configurable.system_prompt_path
        state_vars.update(dataclasses.asdict(configurable))
    elif isinstance(configurable, dict):
        task = configurable['configurable']["task"]
        system_prompt_path = configurable['configurable']["system_prompt_path"]
    else:
        task = "original"

    try:
        if system_prompt_path:
            env = Environment(
                loader=FileSystemLoader(system_prompt_path),
                autoescape=select_autoescape(),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            template = env.get_template(f"{prompt_name}.md")
        else:
            env = Environment(
                loader=FileSystemLoader(os.path.dirname(__file__)),
                autoescape=select_autoescape(),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            template = env.get_template(f"tasks/{task}/{prompt_name}.md")
        system_prompt = template.render(**state_vars)
        return [{"role": "system", "content": system_prompt}] + state["messages"]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")
