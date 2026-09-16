import re
from typing import Any, Optional, Type, Union
from langchain_core.output_parsers.pydantic import PydanticOutputParser
from src.utils.json_utils import repair_json_output

# If you use Pydantic v2, `BaseModel` import path may differ; usually:
from pydantic import BaseModel

class _MessageLike:
    """Small shim that exposes both .text and .content like different LLM result shapes."""
    __slots__ = ("text", "content")
    def __init__(self, text: str):
        self.text = text
        self.content = text

class GeminiReactWrapper:
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

    def __init__(self, react_agent: Any, pydantic_model: Optional[Type[BaseModel]] = None):
        self.react_agent = react_agent
        self.pydantic_model = pydantic_model

        # if provided, also prepare a LangChain PydanticOutputParser for fallback
        self._lc_parser: Optional[PydanticOutputParser] = None
        if pydantic_model is not None:
            self._lc_parser = PydanticOutputParser(pydantic_object=pydantic_model)

    def with_structured_output(self, pydantic_model: Type[BaseModel], method: str = "json_mode"):
        """
        Return a new wrapper that will parse the cleaned output into `pydantic_model`.
        `method` is accepted for API parity but this wrapper always expects JSON.
        """
        return GeminiReactWrapper(self.react_agent, pydantic_model=pydantic_model)

    # ---------- Helpers ----------
    @staticmethod
    def _extract_text(resp: Any) -> str:
        """
        Extract the final text output from the react agent response.
        """
        candidate = resp["messages"][-1]
        if hasattr(candidate, "content"):
            return candidate.content
        return str(candidate)


    # ---------- Sync/Async API ----------
    def invoke(self, input: Any) -> Any:
        """
        Synchronous invoke. Calls underlying LLM.invoke, cleans output, and optionally parses.
        Returns:
          - If pydantic_model is set: an instance of that model (or raises with helpful debug)
          - Else: cleaned text (str)
        """
        if self.pydantic_model is None:
            raw_resp = self.react_agent.invoke(input = input)
            text = self._extract_text(raw_resp)
            return _MessageLike(text)

        if self._lc_parser is not None:
            raw_resp = self.react_agent.invoke(input = input)
            text = repair_json_output(self._extract_text(raw_resp))
            try:
                # parse_result expects message-like; pass AIMessage
                shim = _MessageLike(text)
                return self._lc_parser.parse_result([shim])
            except Exception as e:
                raise ValueError(
                    "ReactWrapper: LangChain parser failed on text output. "
                    f"Text output:\n{text}"
                ) from e

        # No parser available: raise with debug
        raise RuntimeError(f"Failed to parse text output into {self.pydantic_model}.\nText:\n{text}")

    async def ainvoke(self, input: Any) -> Any:
        """
        Async invoke. Will try to use underlying .ainvoke if present, else run .invoke in thread.
        """
        if self.pydantic_model is None:
            raw_resp = await self.react_agent.ainvoke(input = input)
            text = self._extract_text(raw_resp)
            return _MessageLike(text)

        if self._lc_parser is not None:
            raw_resp = await self.react_agent.ainvoke(input = input)
            text = repair_json_output(self._extract_text(raw_resp))
            try:
                shim = _MessageLike(text)
                return self._lc_parser.parse_result([shim])
            except Exception as e:
                raise ValueError(
                    "ReactWrapper (async): LangChain parser failed on text output. "
                    f"Text output:\n{text}"
                ) from e
        raise RuntimeError(f"(async) Failed to parse text output into {self.pydantic_model}.\nText:\n{text}")
