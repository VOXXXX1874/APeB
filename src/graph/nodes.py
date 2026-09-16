# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import json
import logging
import os
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.types import Command, interrupt

from src.agents import create_agent
from src.tools.search import LoggedTavilySearch
from src.tools import (
    crawl_tool,
    get_web_search_tool,
    get_structured_retriever_tool,
    python_repl_tool,
)

from src.config.configuration import Configuration
from src.llms.llm import get_llm_by_type
from src.prompts.planner_model import Plan
from src.prompts.features_model import Report
from src.prompts.recommendation_model import Recommendation
from src.prompts.template import apply_prompt_template
from src.utils.json_utils import repair_json_output
from src.utils.prepare_prompts import prepare_grouped_actions

from .types import State
from ..config import SELECTED_SEARCH_ENGINE, SearchEngine

logger = logging.getLogger(__name__)


@tool
def handoff_to_planner(
    research_topic: Annotated[str, "The topic of the research task to be handed off."],
    locale: Annotated[str, "The user's detected language locale (e.g., en-US, zh-CN)."],
    common_features: Annotated[list[str], "Common features of products related to current query."]
):
    """Handoff to planner agent to do plan."""
    # This tool is not returning anything: we're just using it
    # as a way for LLM to signal that it needs to hand off to planner agent
    return


def background_investigation_node(state: State, config: RunnableConfig):
    logger.info("background investigation node is running.")
    configurable = Configuration.from_runnable_config(config)
    query = state.get("research_topic")
    background_investigation_results = None
    if SELECTED_SEARCH_ENGINE == SearchEngine.TAVILY.value:
        searched_content = LoggedTavilySearch(
            max_results=configurable.max_search_results
        ).invoke(query)
        if isinstance(searched_content, list):
            background_investigation_results = [
                f"## {elem['title']}\n\n{elem['content']}" for elem in searched_content
            ]
            return {
                "background_investigation_results": "\n\n".join(
                    background_investigation_results
                )
            }
        else:
            logger.error("Web search returned a malformed response")
    else:
        background_investigation_results = get_web_search_tool(
            configurable.max_search_results
        ).invoke(query)
    return {
        "background_investigation_results": json.dumps(
            background_investigation_results, ensure_ascii=False
        )
    }


async def planner_node(
    state: State, config: RunnableConfig
) -> Command[Literal["human_feedback", "reporter"]]:
    """Planner node that generate the full plan."""
    logger.info("Planner generating full plan")
    configurable = Configuration.from_runnable_config(config)
    plan_iterations = state["plan_iterations"] if state.get("plan_iterations", 0) else 0
    messages = apply_prompt_template("planner", state, configurable)

    if state.get("enable_background_investigation") and state.get(
        "background_investigation_results"
    ):
        messages += [
            {
                "role": "user",
                "content": (
                    "background investigation results of user query:\n"
                    + state["background_investigation_results"]
                    + "\n"
                ),
            }
        ]

    llm = get_llm_by_type(configurable.agent_llm_map["planner"]).with_structured_output(
        Plan,
        method="json_mode",
    )

    # if the plan iterations is greater than the max plan iterations, return the reporter node
    if plan_iterations >= configurable.max_plan_iterations:
        return Command(goto="reporter")

    full_response = ""
    logger.debug("Planner prompt prepared")
    response = await llm.ainvoke(messages)
    full_response = response.model_dump_json(indent=4, exclude_none=True)
    logger.debug("Planner response received")

    try:
        curr_plan = json.loads(repair_json_output(full_response))
    except json.JSONDecodeError:
        logger.warning("Planner response is not a valid JSON")
        if plan_iterations > 0:
            return Command(goto="reporter")
        else:
            return Command(goto="__end__")
    if curr_plan.get("has_enough_context"):
        logger.info("Planner response has enough context.")
        new_plan = Plan.model_validate(curr_plan)
        return Command(
            update={
                "current_plan": new_plan,
            },
            goto="reporter",
        )
    return Command(
        update={
            "current_plan": full_response,
        },
        goto="human_feedback",
    )


def human_feedback_node(
    state,
) -> Command[Literal["planner", "research_team", "reporter", "__end__"]]:
    current_plan = state.get("current_plan", "")
    # check if the plan is auto accepted
    auto_accepted_plan = state.get("auto_accepted_plan", False)
    if not auto_accepted_plan:
        feedback = interrupt("Please Review the Plan.")

        # if the feedback is not accepted, return the planner node
        if feedback and str(feedback).upper().startswith("[EDIT_PLAN]"):
            return Command(
                update={
                    "messages": [
                        HumanMessage(content=feedback, name="feedback"),
                    ],
                },
                goto="planner",
            )
        elif feedback and str(feedback).upper().startswith("[ACCEPTED]"):
            logger.info("Plan is accepted by user.")
        else:
            raise TypeError(f"Interrupt value of {feedback} is not supported.")

    # if the plan is accepted, run the following node
    plan_iterations = state["plan_iterations"] if state.get("plan_iterations", 0) else 0
    goto = "research_team"
    try:
        current_plan = repair_json_output(current_plan)
        # increment the plan iterations
        plan_iterations += 1
        # parse the plan
        new_plan = json.loads(current_plan)
        if new_plan["has_enough_context"]:
            goto = "reporter"
    except json.JSONDecodeError:
        logger.warning("Planner response is not a valid JSON")
        if plan_iterations > 1:  # the plan_iterations is increased before this check
            return Command(goto="reporter")
        else:
            return Command(goto="__end__")

    return Command(
        update={
            "current_plan": Plan.model_validate(new_plan),
            "plan_iterations": plan_iterations,
            "locale": new_plan["locale"],
        },
        goto=goto,
    )


async def coordinator_node(
    state: State, config: RunnableConfig
) -> Command[Literal["planner", "background_investigator", "__end__"]]:
    """Coordinator node that communicate with customers."""
    logger.info("Coordinator talking.")
    configurable = Configuration.from_runnable_config(config)
    messages = apply_prompt_template("coordinator", state, configurable)
    llm = get_llm_by_type(configurable.agent_llm_map["coordinator"]).bind_tools([handoff_to_planner])
    response = await llm.ainvoke(messages)
    logger.debug("Coordinator response received")

    goto = "__end__"
    locale = state.get("locale", "en-US")  # Default locale if not specified
    research_topic = state.get("research_topic", "")
    common_features = ""

    if len(response.tool_calls) > 0:
        goto = "planner"
        if state.get("enable_background_investigation"):
            # if the search_before_planning is True, add the web search tool to the planner agent
            goto = "background_investigator"
        try:
            for tool_call in response.tool_calls:
                if tool_call.get("name", "") != "handoff_to_planner":
                    continue
                locale = tool_call.get("args", {}).get("locale")
                research_topic = tool_call.get("args", {}).get("research_topic")
                common_features = tool_call.get("args", {}).get("common_features")
                break
        except Exception:
            logger.error("Coordinator tool-call parsing failed")
    else:
        logger.warning(
            "Coordinator response contains no tool calls. Terminating workflow execution."
        )

    return Command(
        update={
            "locale": locale,
            "research_topic": research_topic,
            "common_features": common_features,
        },
        goto=goto,
    )


async def reporter_node(state: State, config: RunnableConfig):
    """Reporter node that write a final report."""
    logger.info("Reporter write final report")
    configurable = Configuration.from_runnable_config(config)
    current_plan = state.get("current_plan")
    all_observations = ""
    observations = state.get("observations", [])
    for i, observation in enumerate(observations):
        all_observations += f"Observation {i+1}:\n{observation}\n\n"
    all_observations += f"Please avoid repeating or focusing on those common features in your report, because they cannot bring useful information: {state.get('common_features', '')}"
    input_ = {
        "messages": [
            HumanMessage(
                "#Input\n\n" + state.get("messages")[0].content
                + f"\n\n# Research Requirements\n\n## Task\n\n{current_plan.title}\n\n## Description\n\n{current_plan.thought}"
                + f"\n\n# Observations from Researcher\n\n{all_observations}",
                name="user"
            ),
        ],
        "locale": state.get("locale", "en-US"),
    }
    invoke_messages = apply_prompt_template("reporter", input_, configurable)

    logger.debug("Reporter prompt prepared")
    if configurable.agent_llm_map["reporter"][0] != "reasoning":
        logger.info("Warning: Only reasoning model is capable of writing report.")

    llm = get_llm_by_type(configurable.agent_llm_map["reporter"])
    if configurable.task != "predict_order":
        llm = llm.with_structured_output(
            Report,
            method="json_mode",
        )
    else:
        llm = llm.with_structured_output(
            Recommendation,
            method="json_mode",
        )
    response = await llm.ainvoke(invoke_messages)
    response_content = response.model_dump_json(indent=4, exclude_none=True)
    # Convert the response to a dictionary
    response_dict = json.loads(response_content)
    logger.debug("Reporter response parsed")

    return {"final_report": response_dict}


def research_team_node(state: State):
    """Research team node that collaborates on tasks."""
    logger.info("Research team is collaborating on tasks.")
    pass


async def _execute_agent_step(
    state: State, agent, agent_name: str, config: RunnableConfig
) -> Command[Literal["research_team"]]:
    """Helper function to execute a step using the specified agent."""
    current_plan = state.get("current_plan")
    observations = state.get("observations", [])
    configurable = Configuration.from_runnable_config(config)
    # Find the first unexecuted step
    current_step = None
    completed_steps = []
    for step in current_plan.steps:
        if not step.execution_res:
            current_step = step
            break
        else:
            completed_steps.append(step)

    if not current_step:
        logger.warning("No unexecuted step found")
        return Command(goto="research_team")

    logger.info("Executing research step with agent=%s", agent_name)
    # Prepare the input for the agent with grouped actions
    actions_group = prepare_grouped_actions(state.get("messages")[0].content, configurable.task, current_step.actions_index_list, current_step.candidates_index_list)
    agent_input = {
        "messages": [
            HumanMessage(
                content=f"# Current Task\n\n## Title\n\n{current_step.title}\n\n## Description\n\n{current_step.description}\n\n## Locale\n\n{state.get('locale', 'en-US')}\n\n## Products Group\n\n{actions_group}\n\n## Common Features\n\n{state.get('common_features')}"
            )
        ]
    }

    # Invoke the agent
    default_recursion_limit = 25
    try:
        env_value_str = os.getenv("AGENT_RECURSION_LIMIT", str(default_recursion_limit))
        parsed_limit = int(env_value_str)

        if parsed_limit > 0:
            recursion_limit = parsed_limit
            logger.info(f"Recursion limit set to: {recursion_limit}")
        else:
            logger.warning(
                f"AGENT_RECURSION_LIMIT value '{env_value_str}' (parsed as {parsed_limit}) is not positive. "
                f"Using default value {default_recursion_limit}."
            )
            recursion_limit = default_recursion_limit
    except ValueError:
        raw_env_value = os.getenv("AGENT_RECURSION_LIMIT")
        logger.warning(
            f"Invalid AGENT_RECURSION_LIMIT value: '{raw_env_value}'. "
            f"Using default value {default_recursion_limit}."
        )
        recursion_limit = default_recursion_limit

    logger.debug("Research agent prompt prepared")
    result = await agent.ainvoke(
        input=agent_input, config={"recursion_limit": recursion_limit, "configurable": {"task": configurable.task, "system_prompt_path": configurable.system_prompt_path}}
    )

    # Process the result
    response_content = result["messages"][-1].content
    logger.debug("Research agent response received")

    # Update the step with the execution result
    current_step.execution_res = response_content
    logger.info("Research step completed by agent=%s", agent_name)

    return Command(
        update={
            "observations": observations + [response_content],
        },
        goto="research_team",
    )


async def _setup_and_execute_agent_step(
    state: State,
    config: RunnableConfig,
    agent_type: str,
    default_tools: list,
) -> Command[Literal["research_team"]]:
    """Create an agent with only the explicitly approved local tool list."""
    configurable = Configuration.from_runnable_config(config)
    agent = create_agent(
        agent_type,
        agent_type,
        default_tools,
        agent_type,
        configurable.agent_llm_map,
    )
    return await _execute_agent_step(state, agent, agent_type, config)


async def researcher_node(
    state: State, config: RunnableConfig
) -> Command[Literal["research_team"]]:
    """Researcher node that do research"""
    logger.info("Researcher node is researching.")
    configurable = Configuration.from_runnable_config(config)
    enabled = set(configurable.available_tools)
    tools = []
    if "web_search" in enabled:
        tools.append(get_web_search_tool(configurable.max_search_results))
    if "crawl" in enabled:
        tools.append(crawl_tool)
    if "python_repl" in enabled:
        tools.append(python_repl_tool)
    if configurable.task == "predict_order" and "retriever" in enabled:
        structured_retriever_tool_history = get_structured_retriever_tool(configurable.structured_resources, "history", name="history_retriever_tool")
        structured_retriever_tool_candidate = get_structured_retriever_tool(configurable.structured_resources, "candidate", name="candidate_retriever_tool")
        if structured_retriever_tool_candidate:
            tools.insert(0, structured_retriever_tool_candidate)
        if structured_retriever_tool_history:
            tools.insert(0, structured_retriever_tool_history)


    logger.info("Researcher tool count: %d", len(tools))
    return await _setup_and_execute_agent_step(
        state,
        config,
        "researcher",
        tools,
    )
