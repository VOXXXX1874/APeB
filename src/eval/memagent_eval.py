from src.llms.llm import get_llm_by_type
from src.prompts.recommendation_model import SimpleRecommendation
from src.config.agents import LLMType
from src.utils.metrics import recall_at_k
from src.eval.llm_eval import resolve_model_location
import json
import os
import re
import asyncio
from typing import List
from pydantic import BaseModel, Field
from src.utils.format_utils import *

import logging
logger = logging.getLogger(__name__)

def get_interactions_candidates_descriptions_in_prompt(prompt: str, title_key_map: dict, structured_resources: dict) -> tuple[List[str], List[str]]:
    # First process history
    history_interactions = re.findall(r"<history>(.*?)</history>", prompt, re.DOTALL)[0]
    history_interactions = re.findall(r"\d+\.\s.*?(?=\n\d+\.|$)", history_interactions, flags=re.S)
    # Filter out empty strings
    history_interactions = [interaction.strip() for interaction in history_interactions if interaction.strip()]
    history_title_key_map = title_key_map["history_title_key_map"]
    # Find the title of each interaction through "Product name: (.*); Price:"
    history_interactions_descriptions = []
    for interaction in history_interactions:
        product_name = None
        video_title = None
        if "Product name" in interaction:
            product_name = re.search(r"Product name: (.*); Price:", interaction, re.DOTALL).group(1).strip()
        elif "Product introducted in this video" in interaction:
            product_name = re.search(r"Product introducted in this video: (.*); Price:", interaction, re.DOTALL).group(1).strip()
        elif "Video title" in interaction:
            video_title = re.search(r"Video title:(.*)$", interaction, re.DOTALL).group(1).strip()
        else:
            continue
        if product_name:
            history_interaction_key = history_title_key_map[product_name]
        elif video_title:
            history_interaction_key = history_title_key_map[video_title]
        history_interactions_descriptions.append(structured_resources["history_actions_informations"][history_interaction_key])

    # Then process candidates
    candidates = re.findall(r"<candidates>(.*?)</candidates>", prompt, re.DOTALL)[0]
    candidates = re.findall(r"\d+\.\s.*?(?=\n\d+\.|$)", candidates, flags=re.S)
    # Filter out empty strings
    candidates = [candidate.strip() for candidate in candidates if candidate.strip()]
    candidate_title_key_map = title_key_map["candidate_title_key_map"]
    # Find the title of each candidate through "Product name: (.*); Price:"
    candidates_descriptions = []
    for candidate in candidates:
        product_name = re.search(r"Product name: (.*); Price:", candidate).group(1)
        candidate_interaction_key = candidate_title_key_map[product_name]
        candidates_descriptions.append(structured_resources["candidates_informations"][candidate_interaction_key])

    return history_interactions_descriptions, candidates_descriptions

def organize_structured_resources(structured_resources: dict) -> dict:
    # First process history
    history_interactions_information = structured_resources["history_actions_informations"]
    # Construct a map from title to key
    history_title_key_map = {}
    for interaction_id in history_interactions_information.keys():
        history_interaction_content = history_interactions_information[interaction_id]
        if "p" in interaction_id:
            if "<<<Product name>>>" in history_interaction_content:
                history_detailed_information_content_dict = parse_product_text_new(history_interaction_content)
            else:
                history_detailed_information_content_dict = parse_product_text(history_interaction_content)
            product_name = history_detailed_information_content_dict["product_name"]
            history_title_key_map[product_name] = interaction_id
        elif "v" in interaction_id:
            if "<<<Video title>>>" in history_interaction_content:
                history_detailed_information_content_dict = parse_video_text_new(history_interaction_content)
            else:
                history_detailed_information_content_dict = parse_video_text(history_interaction_content)
            video_title = history_detailed_information_content_dict["video_title"]
            product_action = history_detailed_information_content_dict["product_introducted_in_this_video"]
            if video_title != "None":
                history_title_key_map[video_title] = interaction_id
            if product_action != "None":
                history_title_key_map[product_action] = interaction_id

    # Then process the candidates
    candidate_title_key_map = {}
    candidate_information = structured_resources["candidates_informations"]
    for candidate_id in candidate_information.keys():
        candidate_content = candidate_information[candidate_id]
        if "<<<Product name>>>" in candidate_content:
            candidate_detailed_information_content_dict = parse_candidate_product_text_new(candidate_content)
        else:
            candidate_detailed_information_content_dict = parse_candidate_product_text(candidate_content)
        product_name = candidate_detailed_information_content_dict["product_name"]
        candidate_title_key_map[product_name] = candidate_id

    return {
        "history_title_key_map": history_title_key_map,
        "candidate_title_key_map": candidate_title_key_map,
    }


class Memory(BaseModel):
    reasoning: str = Field(
        ..., description="The reasoning process about how to modify the memory"
    )
    memory: str = Field(
        ..., description="The memory that is used to store the important information from the previous retrieved chunk"
    )

class MemAgent:
    def __init__(self, memory_llm, answer_llm, memory_system_prompt, answer_system_prompt, section_size, structured_resources):
        self.memory_llm = memory_llm
        self.answer_llm = answer_llm
        self.memory_system_prompt = memory_system_prompt
        self.answer_system_prompt = answer_system_prompt
        self.section_size = section_size
        self.structured_resources = structured_resources
        self.title_key_map = organize_structured_resources(self.structured_resources)

    async def ainvoke(self, input):
        # Get the history interactions and candidates descriptions from the prompt
        history_interactions_descriptions, candidates_descriptions = get_interactions_candidates_descriptions_in_prompt(input, self.title_key_map, self.structured_resources)
        memory = ""
        section = ""
        for i in range(0, len(history_interactions_descriptions), self.section_size):
            # Construct the section from the history interactions
            section = f"A section of {self.section_size} history interactions:\n"
            section += "\n".join(history_interactions_descriptions[i:i+self.section_size])
            full_input = f"<recommendation>{input}</recommendation><memory>{memory}</memory><section>{section}</section>"
            memory_input = [
                {"role": "system", "content": self.memory_system_prompt},
                {"role": "user", "content": full_input},
            ]
            memory_response = await self.memory_llm.ainvoke(memory_input)

            memory = memory_response.memory

        for i in range(0, len(candidates_descriptions), self.section_size):
            # Construct the section from the candidates
            section = f"A section of {self.section_size} candidates:\n"
            section += "\n".join(candidates_descriptions[i:i+self.section_size])
            full_input = f"<recommendation>{input}</recommendation><memory>{memory}</memory><section>{section}</section>"
            memory_input = [
                {"role": "system", "content": self.memory_system_prompt},
                {"role": "user", "content": full_input},
            ]
            memory_response = await self.memory_llm.ainvoke(memory_input)

            memory = memory_response.memory

        final_input = f"<recommendation>{input}</recommendation><memory>{memory}</memory>"
        answer_input = [
            {"role": "system", "content": self.answer_system_prompt},
            {"role": "user", "content": final_input},
        ]
        answer_response = await self.answer_llm.ainvoke(answer_input)

        return answer_response

def get_system_prompt_by_name(name, agent_type):
    path = os.path.join(os.path.dirname(__file__), "system_prompt", f"{agent_type}_{name}.md")
    with open(path, "r") as f:
        system_prompt = f.read()
    return system_prompt

async def invoke_with_semaphore(json_input, location, llm_name, llm_type, memory_system_prompt, answer_system_prompt, section_size, semaphore):
    async with semaphore:
        try:
            structured_resources = {
                "history_actions_informations": json_input["history_actions_informations"],
                "candidates_informations": json_input["candidates_informations"],
            }

            memory_response_format = Memory
            answer_response_format = SimpleRecommendation

            memory_llm = get_llm_by_type((llm_type, location)).with_structured_output(
                memory_response_format,
                method="json_mode",
            )
            answer_llm = get_llm_by_type((llm_type, location)).with_structured_output(
                answer_response_format,
                method="json_mode",
            )

            user_prompt = json_input["prompt"]

            memagent = MemAgent(memory_llm, answer_llm, memory_system_prompt, answer_system_prompt, section_size, structured_resources)

            response = await memagent.ainvoke(input = user_prompt)
            logger.info("Task done")
            return response
        except Exception as error:
            logger.error(
                "MemAgent invocation failed: %s: %s",
                type(error).__name__,
                error,
                exc_info=True,
            )
            return None

async def memagent_eval(llm_type: LLMType, llm_name: str, data_path: str, section_size: int, max_workers: int):
    semaphore = asyncio.Semaphore(max_workers)

    # Get llm
    location = resolve_model_location(llm_type, llm_name)
    memory_system_prompt = get_system_prompt_by_name('memory', 'memagent')
    answer_system_prompt = get_system_prompt_by_name('answer', 'memagent')

    # Get the input data
    with open(data_path, "r") as f:
        lines = f.readlines()
    json_inputs = [json.loads(line) for line in lines]

    # Evaluate the llm using the input data
    tasks = []
    for json_input in json_inputs:
        tasks.append(invoke_with_semaphore(json_input, location, llm_name, llm_type, memory_system_prompt, answer_system_prompt, section_size, semaphore))

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
            logger.error("MemAgent response parsing failed")
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
