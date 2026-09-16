from src.llms.llm import get_llm_by_type
from src.prompts.recommendation_model import Recommendation, SimpleRecommendation, StructuredRecommendation
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from src.config.agents import LLMType
from src.utils.metrics import recall_at_k
from src.eval.llm_eval import resolve_model_location
from src.agents.gemini_react_wrapper import GeminiReactWrapper
import json
import os
import asyncio
from langgraph.prebuilt import create_react_agent
from src.tools import (
    crawl_tool,
    get_web_search_tool,
    get_structured_retriever_tool,
    python_repl_tool,
)
import logging
logger = logging.getLogger(__name__)

def get_system_prompt_by_name(name, agent_type):
    path = os.path.join(os.path.dirname(__file__), "system_prompt", f"{agent_type}_{name}.md")
    with open(path, "r") as f:
        system_prompt = f.read()
    return system_prompt

def get_tool_prompt_by_name(name):
    path = os.path.join(os.path.dirname(__file__), "system_prompt", "tools", f"{name}.md")
    with open(path, "r") as f:
        tool_prompt = f.read()
    return tool_prompt

async def invoke_with_semaphore(json_input, tools, location, llm_name, llm_type, system_prompt, _system_prompt, available_tools, semaphore):
    async with semaphore:
        try:
            if "retriever" in available_tools:
                structured_resources = {
                    "history_actions_informations": json_input["history_actions_informations"],
                    "candidates_informations": json_input["candidates_informations"],
                }
                structured_retriever_tool_history = get_structured_retriever_tool(structured_resources, "history", name="history_retriever_tool")
                structured_retriever_tool_candidate = get_structured_retriever_tool(structured_resources, "candidate", name="candidate_retriever_tool")
                if structured_retriever_tool_history:
                    tools.insert(0, structured_retriever_tool_history)
                if structured_retriever_tool_candidate:
                    tools.insert(0, structured_retriever_tool_candidate)
                tool_prompt = get_tool_prompt_by_name("retriever")
                _system_prompt = _system_prompt.replace("[AVAILABLE TOOLS]", "[AVAILABLE TOOLS]\n" + tool_prompt)

            _system_prompt = _system_prompt.replace("[AVAILABLE TOOLS]", "")

            if system_prompt == 'simple':
                response_format = Recommendation
            elif system_prompt == 'basic':
                response_format = SimpleRecommendation
            elif "detailed" in system_prompt:
                response_format = StructuredRecommendation
            else:
                raise ValueError(f"System prompt {system_prompt} not found")

            if "gemini" not in llm_name:
                react_agent = create_react_agent(
                    name=f"react_{llm_name}",
                    model=get_llm_by_type((llm_type, location)),
                    tools=tools,
                    prompt=_system_prompt,
                    response_format=response_format,
                    #debug=True,
                )
            else:
                react_agent = create_react_agent(
                    name=f"react_{llm_name}",
                    model=get_llm_by_type((llm_type, location)),
                    tools=tools,
                    prompt=_system_prompt,
                    #debug=True,
                )
                react_agent = GeminiReactWrapper(react_agent, response_format)

            user_prompt = json_input["prompt"]
            agent_input = {
                "messages": [
                    HumanMessage(content=user_prompt)
                ]
            }
            response = await react_agent.ainvoke(agent_input)
            logger.info("Task done")
            return response
        except Exception as error:
            logger.error(
                "ReAct invocation failed: %s: %s",
                type(error).__name__,
                error,
                exc_info=True,
            )
            return None

async def react_eval(llm_type: LLMType, llm_name: str, data_path: str, available_tools: list, system_prompt: str, max_workers: int):
    semaphore = asyncio.Semaphore(max_workers)

    # Get llm
    location = resolve_model_location(llm_type, llm_name)
    _system_prompt = get_system_prompt_by_name(system_prompt, 'react')

    # Get the input data
    with open(data_path, "r") as f:
        lines = f.readlines()
    json_inputs = [json.loads(line) for line in lines]

    # Evaluate the llm using the input data
    tasks = []
    for json_input in json_inputs:
        tools = []
        sample_system_prompt = _system_prompt
        for tool in available_tools:
            if tool == "web_search":
                tools.append(get_web_search_tool(3))
                tool_prompt = get_tool_prompt_by_name(tool)
                sample_system_prompt = sample_system_prompt.replace("[AVAILABLE TOOLS]", "[AVAILABLE TOOLS]\n" + tool_prompt)
            elif tool == "crawl":
                tools.append(crawl_tool)
                tool_prompt = get_tool_prompt_by_name(tool)
                sample_system_prompt = sample_system_prompt.replace("[AVAILABLE TOOLS]", "[AVAILABLE TOOLS]\n" + tool_prompt)
            elif tool == "python_repl":
                tools.append(python_repl_tool)
                tool_prompt = get_tool_prompt_by_name(tool)
                sample_system_prompt = sample_system_prompt.replace("[AVAILABLE TOOLS]", "[AVAILABLE TOOLS]\n" + tool_prompt)

        tasks.append(invoke_with_semaphore(json_input, tools, location, llm_name, llm_type, system_prompt, sample_system_prompt, available_tools, semaphore))

    responses = await asyncio.gather(*tasks)

    results = []
    for i, response in enumerate(responses):
        try:
            if isinstance(response, dict):
                all_messages = response['messages']
                response = response['structured_response']
            response_content = response.model_dump_json(indent=4, exclude_none=True)
            response_dict = json.loads(response_content)
            # Remove the HumanMessages and the last message
            all_messages = all_messages[:-1]
            react_messages = []
            for msg in all_messages:
                if isinstance(msg, AIMessage):
                    react_messages.append(msg.tool_calls)
                elif isinstance(msg, ToolMessage):
                    react_messages.append(msg.content)

            results.append({"sample_id": json_inputs[i]["sample_id"], "response": response_dict, "react_messages": react_messages, "answer_indices": json_inputs[i]["answer_indices"]})
        except Exception:
            logger.error("ReAct response parsing failed")
            results.append({"sample_id": json_inputs[i]["sample_id"], "response": None, "react_messages": None, "answer_indices": json_inputs[i]["answer_indices"]})
            continue

    # Process the results and get the final score of this model
    recall_at_1_score = []
    recall_at_3_score = []
    recall_at_5_score = []
    invalid_count = 0
    for result in results:
        if result["response"] is None:
            recall_at_1_score.append(0)
            recall_at_3_score.append(0)
            recall_at_5_score.append(0)
            invalid_count += 1
            result["recall_at_1"] = 0
            result["recall_at_3"] = 0
            result["recall_at_5"] = 0
            continue
        predict_rank = []
        for i in range(1, len(result["response"]["products"]) + 1):
            for product in result["response"]["products"]:
                if product["rank"] == i:
                    predict_rank.append(product["index"])
                    break
            else:
                logger.warning("Model response contains a rank gap")
        score_at_1 = recall_at_k(predict_rank, result["answer_indices"], 1)
        score_at_3 = recall_at_k(predict_rank, result["answer_indices"], 3)
        score_at_5 = recall_at_k(predict_rank, result["answer_indices"], 5)
        result["recall_at_1"] = score_at_1
        result["recall_at_3"] = score_at_3
        result["recall_at_5"] = score_at_5
        recall_at_1_score.append(score_at_1)
        recall_at_3_score.append(score_at_3)
        recall_at_5_score.append(score_at_5)
    final_score_all = {
        "recall_at_1": sum(recall_at_1_score) / len(recall_at_1_score),
        "recall_at_3": sum(recall_at_3_score) / len(recall_at_3_score),
        "recall_at_5": sum(recall_at_5_score) / len(recall_at_5_score),
    }
    valid_count = len(results) - invalid_count
    final_score_valid = ({
        "recall_at_1": sum(recall_at_1_score) / valid_count,
        "recall_at_3": sum(recall_at_3_score) / valid_count,
        "recall_at_5": sum(recall_at_5_score) / valid_count,
    } if valid_count else None)

    return final_score_all, final_score_valid, results, invalid_count
