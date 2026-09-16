# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT
import logging

from src.graph import build_graph
from src.config.agents import AGENT_LLM_MAP
from typing import Any

def enable_debug_logging():
    """Enable debug level logging for more detailed execution information."""
    logging.getLogger("src").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

# Create the graph
graph = build_graph()


def build_structured_resources(inputs: dict[str, Any]) -> dict[str, Any]:
    """Construct the DeerFlow resource bundle from one compatibility record."""

    resources = {
        "history_actions_informations": inputs["history_actions_informations"],
        "candidates_informations": inputs["candidates_informations"],
    }
    return resources

async def run_agent_workflow_async(
    inputs: dict,
    debug: bool = False,
    max_plan_iterations: int = 1,
    max_step_num: int = 3,
    enable_background_investigation: bool = True,
    task: str = "original",
    agent_llm_map: dict[str, str] = None,
    system_prompt_path: str = None,
    available_tools: list[str] | None = None,
):
    """Run the agent workflow asynchronously with the given user input.

    Args:
        user_input: The user's query or request
        debug: If True, enables debug level logging
        max_plan_iterations: Maximum number of plan iterations
        max_step_num: Maximum number of steps in a plan
        enable_background_investigation: If True, performs web search before planning to enhance context

    Returns:
        The final state after the workflow completes
    """
    if not inputs:
        raise ValueError("Input could not be empty")

    if debug:
        enable_debug_logging()

    initial_state = {
        # Runtime Variables
        "messages": [{"role": "user", "content": inputs["prompt"]}],
        "auto_accepted_plan": True,
        "enable_background_investigation": enable_background_investigation,
    }
    structured_resources = build_structured_resources(inputs)
    config = {
        "configurable": {
            "thread_id": "default",
            "max_plan_iterations": max_plan_iterations,
            "max_step_num": max_step_num,
            "task": task,
            "agent_llm_map": agent_llm_map if agent_llm_map else AGENT_LLM_MAP,
            "structured_resources": structured_resources,
            "available_tools": available_tools or ["retriever"],
            "enable_deep_thinking": True,
            "system_prompt_path": system_prompt_path
        },
        "recursion_limit": 100,
    }
    plan = None
    final_report = None
    observations = []
    try:
        async for s in graph.astream(
            input=initial_state, config=config, stream_mode="values"
        ):

                if isinstance(s, dict):
                    # Get final report
                    if "final_report" in s:
                        final_report = s["final_report"]
                    if "current_plan" in s and type(s["current_plan"]) != str:
                        plan = s["current_plan"].model_dump_json(indent=4)
                    if "observations" in s:
                        observations = s["observations"]
    except Exception:
        logger.error("Agent workflow failed; the sample is marked invalid")

    logger.info("Async workflow completed successfully")

    res = {
        "plan": plan,
        "final_report": final_report,
        "observations": observations,
    }

    return res

if __name__ == "__main__":
    print(graph.get_graph(xray=True).draw_mermaid())
