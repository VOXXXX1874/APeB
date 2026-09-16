from src.llms.llm import get_llm_by_type
from src.prompts.recommendation_model import Recommendation, SimpleRecommendation, DetailedGroundedRecommendation, StructuredRecommendation
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from src.config.agents import LLMType
from src.utils.metrics import recall_at_k
from src.eval.llm_eval import resolve_model_location
from src.agents.handcraft_asareact_wrapper import HandcraftASAReactWrapper
import json
import os
import asyncio
from src.tools import (
    get_structured_retriever_tool,
)
import logging
logger = logging.getLogger(__name__)

def get_system_prompt_by_name(name, agent_type):
    path = os.path.join(os.path.dirname(__file__), "system_prompt", f"{agent_type}_{name}.md")
    with open(path, "r") as f:
        system_prompt = f.read()
    return system_prompt

async def invoke_with_semaphore(json_input,
                                tools,
                                location,
                                llm_name,
                                llm_type,
                                system_prompt,
                                tools_prompt,
                                answer_prompt,
                                roles_system_prompt,
                                semaphore):
    async with semaphore:
        try:
            structured_resources = {
                "history_actions_informations": json_input["history_actions_informations"],
                "candidates_informations": json_input["candidates_informations"],
            }
            history_retriever_tool = get_structured_retriever_tool(structured_resources, "history", name="history_retriever_tool")
            candidate_retriever_tool = get_structured_retriever_tool(structured_resources, "candidate", name="candidate_retriever_tool")
            if history_retriever_tool:
                tools.append(history_retriever_tool)
            if candidate_retriever_tool:
                tools.append(candidate_retriever_tool)

            if 'simple' in system_prompt:
                response_format = Recommendation
            elif 'basic' in system_prompt:
                response_format = SimpleRecommendation
            elif "detailed" in system_prompt:
                response_format = StructuredRecommendation
            else:
                raise ValueError(f"System prompt {system_prompt} not found")
            asareact_agent = HandcraftASAReactWrapper(model=get_llm_by_type((llm_type, location)),
                                                answer_prompt = answer_prompt,
                                                tools_prompt = tools_prompt,
                                                roles_system_prompt = roles_system_prompt,
                                                tools = tools,
                                                pydantic_model = response_format)

            user_prompt = json_input["prompt"]
            response = await asareact_agent.ainvoke(user_prompt)
            logger.info("Task done")
            return response
        except Exception as error:
            logger.error(
                "ASA-ReAct invocation failed: %s: %s",
                type(error).__name__,
                error,
                exc_info=True,
            )
            return None

async def asareact_eval(llm_type: LLMType, llm_name: str, data_path: str, system_prompt: str, tools_system_prompt: str, max_workers: int):
    semaphore = asyncio.Semaphore(max_workers)

    # Get llm
    location = resolve_model_location(llm_type, llm_name)
    answer_prompt = get_system_prompt_by_name(system_prompt, 'asareact')
    tools_prompt = get_system_prompt_by_name(tools_system_prompt, 'asareact')
    roles_system_prompt = get_system_prompt_by_name('roles', 'asareact')

    # Get the input data
    with open(data_path, "r") as f:
        lines = f.readlines()
    json_inputs = [json.loads(line) for line in lines]

    # Evaluate the llm using the input data
    tasks = []
    for json_input in json_inputs:
        tools = []

        tasks.append(invoke_with_semaphore(json_input,
                                           tools, location,
                                           llm_name,
                                           llm_type,
                                           system_prompt,
                                           tools_prompt,
                                           answer_prompt,
                                           roles_system_prompt,
                                           semaphore))

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
            all_messages = all_messages[2:-2]
            react_messages = []
            for msg in all_messages:
                if isinstance(msg, AIMessage):
                    react_messages.append(msg.content)
                elif isinstance(msg, HumanMessage):
                    react_messages.append(msg.content)

            results.append({"sample_id": json_inputs[i]["sample_id"], "response": response_dict, "react_messages": react_messages, "answer_indices": json_inputs[i]["answer_indices"]})
        except Exception:
            logger.error("ASA-ReAct response parsing failed")
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
