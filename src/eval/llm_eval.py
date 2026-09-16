from src.llms.llm import get_llm_by_type
from src.prompts.recommendation_model import Recommendation, SimpleRecommendation, DetailedGroundedRecommendation, StructuredRecommendation
from src.config.agents import LLMType
from src.utils.metrics import recall_at_k
import json
import os
import asyncio
from collections import defaultdict

import logging
logger = logging.getLogger(__name__)

def resolve_model_location(llm_type: LLMType, llm_name: str) -> str:
    """Return the GROUP/NAME location to look up in the local model config."""
    expected = "BASIC_MODEL" if llm_type == "basic" else "REASONING_MODEL"
    if not llm_name.startswith(expected + "/") or len(llm_name) == len(expected) + 1:
        raise ValueError(
            f"Model must be given as {expected}/NAME from the model config, "
            f"for example {expected}/default"
        )
    return llm_name

def get_system_prompt_by_name(name, agent_type):
    path = os.path.join(os.path.dirname(__file__), "system_prompt", f"{agent_type}_{name}.md")
    with open(path, "r") as f:
        system_prompt = f.read()
    return system_prompt


async def llm_eval(llm_type: LLMType, llm_name: str, data_path: str, system_prompt: str, max_workers: int, majority_voting: int = 1):
    semaphore = asyncio.Semaphore(max_workers)

    async def invoke_with_semaphore(llm, prompt):
        async with semaphore:
            try:
                response = await llm.ainvoke(prompt)
                logger.info("Task done")
                return response
            except Exception as error:
                logger.error(
                    "Model invocation failed: %s: %s",
                    type(error).__name__,
                    error,
                    exc_info=True,
                )
                return None

    # Get llm
    location = resolve_model_location(llm_type, llm_name)

    # Get system prompt
    _system_prompt = get_system_prompt_by_name(system_prompt, 'llm')

    # Get the input data
    with open(data_path, "r") as f:
        lines = f.readlines()
    json_inputs = [json.loads(line) for line in lines]

    # Evaluate the llm using the input data
    tasks = []
    for json_input in json_inputs:
        user_prompt = json_input["prompt"]
        input_prompt = [
            {"role": "system", "content": _system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        for _ in range(majority_voting):
            if 'simple' in system_prompt:
                response_format = Recommendation
            elif 'basic' in system_prompt:
                response_format = SimpleRecommendation
            elif "detailed" in system_prompt:
                response_format = StructuredRecommendation
            else:
                raise ValueError(f"System prompt {system_prompt} not found")
            llm = get_llm_by_type((llm_type, location)).with_structured_output(
                response_format,
                method="json_mode",
            )
            tasks.append(invoke_with_semaphore(llm, input_prompt))

    responses = await asyncio.gather(*tasks)

    results = []
    response_idx = 0
    for i, json_input in enumerate(json_inputs):
        group_responses = responses[response_idx:response_idx + majority_voting]
        response_idx += majority_voting

        if majority_voting > 1:
            valid_responses = []
            for r in group_responses:
                if r is not None:
                    try:
                        response_content = r.model_dump_json(indent=4, exclude_none=True)
                        valid_responses.append(json.loads(response_content))
                    except Exception:
                        logger.warning("A majority-voting response was invalid")

            if not valid_responses:
                results.append({"sample_id": json_inputs[i]["sample_id"], "response": None, "answer_indices": json_inputs[i]["answer_indices"]})
                continue

            all_product_indices = set()
            max_num_products = 0
            for r_dict in valid_responses:
                products = r_dict.get("products", [])
                if products:
                    max_num_products = max(max_num_products, len(products))
                    for p in products:
                        all_product_indices.add(p['index'])

            if not all_product_indices:
                results.append({"sample_id": json_inputs[i]["sample_id"], "response": None, "answer_indices": json_inputs[i]["answer_indices"]})
                continue

            product_avg_ranks = defaultdict(float)
            for p_idx in all_product_indices:
                ranks = []
                for r_dict in valid_responses:
                    products_in_resp = {p['index']: p['rank'] for p in r_dict.get("products", [])}
                    if p_idx in products_in_resp:
                        ranks.append(products_in_resp[p_idx])
                    else:
                        ranks.append(max_num_products + 1)
                product_avg_ranks[p_idx] = sum(ranks) / len(ranks)

            sorted_products = sorted(product_avg_ranks.items(), key=lambda item: item[1])

            voted_response = {"products": [{"rank": rank + 1, "index": p_idx} for rank, (p_idx, _) in enumerate(sorted_products)]}
            results.append({"sample_id": json_inputs[i]["sample_id"], "response": voted_response, "answer_indices": json_inputs[i]["answer_indices"]})
        else:
            response = group_responses[0]
            if response:
                try:
                    response_content = response.model_dump_json(indent=4, exclude_none=True)
                    response_dict = json.loads(response_content)
                    results.append({"sample_id": json_inputs[i]["sample_id"], "response": response_dict, "answer_indices": json_inputs[i]["answer_indices"]})
                except Exception:
                    logger.error("Model response parsing failed")
                    results.append({"sample_id": json_inputs[i]["sample_id"], "response": None, "answer_indices": json_inputs[i]["answer_indices"]})
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
