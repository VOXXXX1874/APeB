from src.llms.llm import get_llm_by_type
from src.prompts.recommendation_model import SimpleRecommendation, Recommendation, StructuredRecommendation
from src.config.agents import LLMType
from src.utils.metrics import recall_at_k
from src.eval.llm_eval import resolve_model_location
import json
import os
import re
import asyncio
from typing import List
from pydantic import BaseModel, Field

class History_Record(BaseModel):
    matched_indices: List[int] = Field(..., description="The list of indices of the history records that are relevant to the current intent.")
    rationale: str = Field(..., description="The rationale about why the record is relevant to the current intent.")

class VQRA_Rewrite(BaseModel):
    case_summary: str = Field(
        ..., description="A concise detective-style summary."
    )
    user_inferred_intent: str = Field(
        ..., description="A clear, concrete restatement of what the user is actually trying to buy now, phrased at a level suitable for product selection."
    )
    relevant_history_detected: bool = Field(
        ..., description="Whether at least one history title clearly provides evidence toward the current intent."
    )
    relevant_history_records: List[History_Record] = Field(
        ..., description="A list of history records index and rationale about why the record is relevant to the current intent."
    )
    refined_query_terms: List[str] = Field(
        ..., description="A list of refined query terms that can reflect the user's true intent and preference."
    )
    best_primary_query: str = Field(
        ..., description="The most suitable query that can reflect the user's true intent and preference."
    )
    confidence_score: float = Field(
        ..., description="The confidence score of the best primary query, ranging from 0 to 1."
    )

import logging
logger = logging.getLogger(__name__)

class VQRAgent:
    def __init__(self, rewrite_llm, recommend_llm, rewrite_system_prompt, recommend_system_prompt):
        self.rewrite_llm = rewrite_llm
        self.recommend_llm = recommend_llm
        self.rewrite_system_prompt = rewrite_system_prompt
        self.recommend_system_prompt = recommend_system_prompt

    async def ainvoke(self, input, rewrite_input):
        # Remove the <candidates> ... </candidates> from the input during rewrite
        init_input = re.sub(r"<candidates>.*?</candidates>", "", rewrite_input, flags=re.DOTALL)
        rewrite_q_input = [
            {"role": "system", "content": self.rewrite_system_prompt},
            {"role": "user", "content": init_input},
        ]
        rewrite_response = await self.rewrite_llm.ainvoke(rewrite_q_input)
        rewrite_query = rewrite_response.best_primary_query

        # Substitute the <query> ... </query> of input with rewrite_query
        final_input = re.sub(r"<query>.*?</query>", f"<query>{rewrite_query}</query>", input, flags=re.DOTALL)

        recommend_input = [
            {"role": "system", "content": self.recommend_system_prompt},
            {"role": "user", "content": final_input},
        ]
        recommend_response = await self.recommend_llm.ainvoke(recommend_input)

        return recommend_response

def get_system_prompt_by_name(name, agent_type):
    path = os.path.join(os.path.dirname(__file__), "system_prompt", f"{agent_type}_{name}.md")
    with open(path, "r") as f:
        system_prompt = f.read()
    return system_prompt

async def invoke_with_semaphore(json_input, location, llm_name, llm_type, rewrite_system_prompt, recommend_system_prompt, system_prompt, semaphore):
    async with semaphore:
        try:
            rewrite_response_format = VQRA_Rewrite
            if 'simple' in system_prompt:
                recommend_response_format = Recommendation
            elif 'basic' in system_prompt:
                recommend_response_format = SimpleRecommendation
            elif "detailed" in system_prompt:
                recommend_response_format = StructuredRecommendation
            else:
                raise ValueError(f"System prompt {system_prompt} not found")

            rewrite_llm = get_llm_by_type((llm_type, location)).with_structured_output(
                rewrite_response_format,
                method="json_mode",
            )
            recommend_llm = get_llm_by_type((llm_type, location)).with_structured_output(
                recommend_response_format,
                method="json_mode",
            )

            user_prompt = json_input["prompt"]
            rewrite_prompt = json_input["rewrite_prompt"]

            vqragent = VQRAgent(rewrite_llm, recommend_llm, rewrite_system_prompt, recommend_system_prompt)

            response = await vqragent.ainvoke(input = user_prompt, rewrite_input = rewrite_prompt)
            logger.info("Task done")
            return response
        except Exception as error:
            logger.error(
                "VQRA invocation failed: %s: %s",
                type(error).__name__,
                error,
                exc_info=True,
            )
            return None

async def vqra_eval(llm_type: LLMType, llm_name: str, data_path: str, system_prompt: str, rewrite_data:str, max_workers: int):
    semaphore = asyncio.Semaphore(max_workers)

    # Get llm
    location = resolve_model_location(llm_type, llm_name)
    rewrite_system_prompt = get_system_prompt_by_name('rewrite', 'vqra')
    recommend_system_prompt = get_system_prompt_by_name(system_prompt, 'vqra')

    # Get the input data
    with open(data_path, "r") as f:
        lines = f.readlines()
    json_inputs = [json.loads(line) for line in lines]

    # Get the data for rewrite
    with open(rewrite_data, "r") as f:
        lines = f.readlines()
    json_rewrites = [json.loads(line) for line in lines]

    for json_input in json_inputs:
        # Find the rewrite data for this sample
        for json_rewrite in json_rewrites:
            if json_rewrite["sample_id"] == json_input["sample_id"]:
                json_input["sample_id"] = json_rewrite["sample_id"]
                json_input["rewrite_prompt"] = json_rewrite["prompt"]

    # Evaluate the llm using the input data
    tasks = []
    for json_input in json_inputs:
        tasks.append(invoke_with_semaphore(
            json_input,
            location,
            llm_name,
            llm_type,
            rewrite_system_prompt,
            recommend_system_prompt,
            system_prompt,
            semaphore))

    responses = await asyncio.gather(*tasks)

    results = []
    for i, response in enumerate(responses):
        try:
            if isinstance(response, dict):
                response = response['structured_response']
            response_content = response.model_dump_json(indent=4, exclude_none=True)
            response_dict = json.loads(response_content)
            results.append({"sample_id": json_inputs[i]["sample_id"], "response": response_dict, "answer_indices": json_inputs[i]["answer_indices"]})
        except Exception:
            logger.error("VQRA response parsing failed")
            results.append({"sample_id": json_inputs[i]["sample_id"], "response": None, "answer_indices": json_inputs[i]["answer_indices"]})
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
