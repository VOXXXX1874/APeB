# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from langgraph.prebuilt import create_react_agent

from src.prompts import apply_prompt_template
from src.llms.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP


# Create agents using configured LLM types
def create_agent(agent_name: str, agent_type: str, tools: list, prompt_template: str, llm_map: dict):
    """Factory function to create agents with consistent configuration."""
    return create_react_agent(
        name=agent_name,
        model=get_llm_by_type(llm_map[agent_type]),
        tools=tools,
        prompt=lambda state, config: apply_prompt_template(prompt_template, state, config),
        #debug=True,
    )
