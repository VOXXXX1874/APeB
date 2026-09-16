from typing import Any, Optional, Type, Union
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from src.prompts.filter_model import SAReAct_ToolCall
# If you use Pydantic v2, `BaseModel` import path may differ; usually:
from pydantic import BaseModel

import logging
logger = logging.getLogger(__name__)

A_PREFIX = '''======================================================================
User History, Query, and the Candidates
======================================================================
'''

class HandcraftASAReactWrapper:
    """
    Wraps a raw LangChain react agent to:
      - get the final output from the agent
      - optionally parse JSON into a Pydantic model
    Usage:
      react_agent = create_react_agent(
            name=f"react_{llm_name}",
            model=get_llm_by_type(llm_type, index),
            tools=tools,
            prompt=system_prompt,
            #debug=True,
        )
      react_agent = ReactWrapper(react_agent).with_structured_output(Plan)
      res = react_agent.invoke(messages)        # returns Plan instance
    """

    def __init__(self,
                 model: Any,
                 answer_prompt: str,
                 tools_prompt: str,
                 roles_system_prompt: str,
                 tools: list,
                 pydantic_model: Optional[Type[BaseModel]] = None,
                 max_iterations: int = 5):
        self.model = model
        self.pydantic_model = pydantic_model
        self.answer_prompt = answer_prompt
        self.tools_prompt = tools_prompt
        self.roles_system_prompt = roles_system_prompt
        self.tools = tools
        self.max_iterations = max_iterations

    def with_structured_output(self, pydantic_model: Type[BaseModel], method: str = "json_mode"):
        """
        Return a new wrapper that will parse the cleaned output into `pydantic_model`.
        `method` is accepted for API parity but this wrapper always expects JSON.
        """
        return HandcraftASAReactWrapper(self.model, self.answer_system_prompt, self.tools_system_prompt, self.tools, pydantic_model, self.max_iterations)

    async def ainvoke(self, input: Any) -> Any:
        """
        Async invoke. Will try to use underlying .ainvoke if present, else run .invoke in thread.
        """
        # Create initial state
        init_task = HumanMessage(content=A_PREFIX + input + self.tools_prompt)
        messages = [
            SystemMessage(content=self.roles_system_prompt),
            init_task,
        ]
        tools_model = self.model.with_structured_output(SAReAct_ToolCall, method="json_mode")
        for i in range(self.max_iterations):
            try:
                # In each react round, call tools and append the messages
                llm_result = await tools_model.ainvoke(messages)
                if isinstance(llm_result, SAReAct_ToolCall):
                    llm_content = llm_result.model_dump_json(indent=4, exclude_none=True)
                else:
                    llm_content = str(llm_result)
                messages.append(AIMessage(content=llm_content))
                if llm_result.enough_information:
                    break
                else:
                    history_queries = llm_result.history_queries
                    candidate_queries = llm_result.candidate_queries
                    history_chunks = []
                    for query in history_queries:
                        history_chunks.extend(await self.tools[0].ainvoke(query))
                    candidate_chunks = []
                    for query in candidate_queries:
                        candidate_chunks.extend(await self.tools[1].ainvoke(query))
                    messages.append(HumanMessage(content="Detail information from history:\n===============\n" + "===============\n".join(history_chunks) + "\n==============================Detail information from candidate:\n===============\n" + "===============\n".join(candidate_chunks)))
            except Exception:
                logger.error("ASA-ReAct tool round failed")
                break

        # After all react rounds, call the answer model to get the final answer
        answer_model = self.model.with_structured_output(self.pydantic_model, method="json_mode")
        messages.append(HumanMessage(content=self.answer_prompt))
        answer_result = await answer_model.ainvoke(messages)
        if isinstance(answer_result, self.pydantic_model):
            messages.append(AIMessage(content=answer_result.model_dump_json(indent=4, exclude_none=True)))
        else:
            messages.append(AIMessage(content=str(answer_result)))

        response = {
            "messages": messages,
            "structured_response": answer_result,
        }

        return response
