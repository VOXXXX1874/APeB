from src.config.agents import LLMType
from src.utils.metrics import recall_at_k
import json
import asyncio
import os
from src.workflow import run_agent_workflow_async
from src.eval.llm_eval import resolve_model_location
import logging
logger = logging.getLogger(__name__)

async def deerflow_eval(llm_type: LLMType, llm_name: str, researcher: str, data_path: str, available_tools: list, max_workers: int):
    semaphore = asyncio.Semaphore(max_workers)

    # Get llm
    location = resolve_model_location(llm_type, llm_name)
    if researcher:
        researcher_type = (
            "basic" if researcher.startswith("BASIC_MODEL/") else "reasoning"
        )
        researcher_location = resolve_model_location(researcher_type, researcher)
    else:
        researcher_type = llm_type
        researcher_location = location
    logger.info("Researcher model configured")

    async def process_single_uid(json_input, agent_llm_map, semaphore):
        async with semaphore:
            run_kwargs = {
                "max_plan_iterations": 1,
                "max_step_num": 3,
                "enable_background_investigation": False,
                "agent_llm_map": agent_llm_map,
                "system_prompt_path": os.path.abspath(os.path.join(os.path.dirname(__file__), "system_prompt", f"deerflow"))
            }
            logger.info("Processing sample_id=%s", json_input["sample_id"])
            try:
                predict_order_res = await run_agent_workflow_async(
                    inputs={
                        "prompt": json_input["prompt"],
                        "history_actions_informations": json_input[
                            "history_actions_informations"
                        ],
                        "candidates_informations": json_input["candidates_informations"],
                    },
                    task="predict_order",
                    available_tools=available_tools,
                    **run_kwargs
                )
                if predict_order_res.get("final_report") == None:
                    raise ValueError(f"The report is empty.")
                return predict_order_res.get("final_report")
            except Exception as error:
                logger.error(
                    "sample_id=%s framework=deerflow status=failed: %s: %s",
                    json_input["sample_id"],
                    type(error).__name__,
                    error,
                    exc_info=True,
                )
                return None


    # Get the input data
    with open(data_path, "r") as f:
        lines = f.readlines()
    json_inputs = [json.loads(line) for line in lines]

    # Evaluate the llm using the input data
    tasks = []
    for json_input in json_inputs:
        agent_llm_map = {
            "coordinator": (researcher_type, researcher_location),
            "planner": (llm_type, location),
            "researcher": (researcher_type, researcher_location),
            "coder": (researcher_type, researcher_location),
            "reporter": (llm_type, location),
        }
        tasks.append(process_single_uid(json_input, agent_llm_map, semaphore))

    responses = await asyncio.gather(*tasks)

    results = []
    for i, response in enumerate(responses):
        if response:
            results.append({"sample_id": json_inputs[i]["sample_id"], "response": response, "answer_indices": json_inputs[i]["answer_indices"]})
        else:
            results.append({"sample_id": json_inputs[i]["sample_id"], "response": None, "answer_indices": json_inputs[i]["answer_indices"]})


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
