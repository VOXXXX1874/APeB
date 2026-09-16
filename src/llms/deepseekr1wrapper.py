import re
from typing import Any, Optional, Type, Union
from langchain_core.output_parsers.pydantic import PydanticOutputParser

# If you use Pydantic v2, `BaseModel` import path may differ; usually:
from pydantic import BaseModel

class _MessageLike:
    """Small shim that exposes both .text and .content like different LLM result shapes."""
    __slots__ = ("text", "content")
    def __init__(self, text: str):
        self.text = text
        self.content = text

class DeepSeekR1Wrapper:
    """
    Wraps a raw LangChain LLM (e.g. AzureChatOpenAI) to:
      - strip `<think>...</think>` blocks from model output
      - optionally parse cleaned JSON into a Pydantic model
    Usage:
      raw_llm = get_llm_by_type(... )   # returns AzureChatOpenAI()
      llm = DeepSeekR1Wrapper(raw_llm).with_structured_output(Plan)
      res = llm.invoke(messages)        # returns Plan instance
      --or--
      res = llm.invoke(messages)        # returns cleaned string if not using with_structured_output
    """

    THINK_RE = re.compile(r"(?is)<think>.*?</think>")  # case-insensitive, DOTALL

    def __init__(self, raw_llm: Any, pydantic_model: Optional[Type[BaseModel]] = None):
        self.raw_llm = raw_llm
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
        return DeepSeekR1Wrapper(self.raw_llm, pydantic_model=pydantic_model)

    def bind_tools(self, tools):
        return self.raw_llm.bind_tools(tools)

    # ---------- Helpers ----------
    @staticmethod
    def _extract_text(resp: Any) -> str:
        """
        Normalize several possible LangChain return shapes into a text string.
        Accepts: str, AIMessage, BaseMessage, list[...] etc.
        """
        # list (take first element)
        if isinstance(resp, (list, tuple)) and len(resp) > 0:
            candidate = resp[0]
            if hasattr(candidate, "content"):
                return candidate.content
            return str(candidate)

        # message-like object
        if hasattr(resp, "content"):
            return resp.content

        # plain string or other
        return str(resp)

    @classmethod
    def _clean_think_block(cls, text: str) -> str:
        # remove any <think>...</think> block
        cleaned = cls.THINK_RE.sub("", text).strip()
        return cleaned

    # ---------- Sync/Async API ----------
    def invoke(self, messages: Any) -> Any:
        """
        Synchronous invoke. Calls underlying LLM.invoke, cleans output, and optionally parses.
        Returns:
          - If pydantic_model is set: an instance of that model (or raises with helpful debug)
          - Else: cleaned text (str)
        """
        if self.pydantic_model is None:
            raw_resp = self.raw_llm.invoke(messages)
            text = self._extract_text(raw_resp)
            cleaned = self._clean_think_block(text)
            return _MessageLike(cleaned)

        if self._lc_parser is not None:
            last_exception = None
            cleaned = ""
            for _ in range(3):
                raw_resp = self.raw_llm.invoke(messages)
                text = self._extract_text(raw_resp)
                cleaned = self._clean_think_block(text)
                try:
                    # parse_result expects message-like; pass AIMessage
                    shim = _MessageLike(cleaned)
                    return self._lc_parser.parse_result([shim])
                except Exception as e:
                    last_exception = e

            raise ValueError(
                "DeepSeekR1Wrapper: LangChain parser failed on cleaned output after 3 retries. "
                f"Cleaned output:\n{cleaned}"
            ) from last_exception

        # No parser available: raise with debug
        raise RuntimeError(f"Failed to parse cleaned output into {self.pydantic_model}.\nCleaned:\n{cleaned}")

    async def ainvoke(self, messages: Any) -> Any:
        """
        Async invoke. Will try to use underlying .ainvoke if present, else run .invoke in thread.
        """
        if self.pydantic_model is None:
            raw_resp = await self.raw_llm.ainvoke(messages)
            text = self._extract_text(raw_resp)
            cleaned = self._clean_think_block(text)
            return _MessageLike(cleaned)

        if self._lc_parser is not None:
            last_exception = None
            cleaned = ""
            for _ in range(3):
                raw_resp = await self.raw_llm.ainvoke(messages)
                text = self._extract_text(raw_resp)
                cleaned = self._clean_think_block(text)
                try:
                    shim = _MessageLike(cleaned)
                    return self._lc_parser.parse_result([shim])
                except Exception as e:
                    last_exception = e

            raise ValueError(
                "DeepSeekR1Wrapper (async): LangChain parser failed on cleaned output after 3 retries. "
                f"Cleaned output:\n{cleaned}"
            ) from last_exception
        raise RuntimeError(f"(async) Failed to parse cleaned output into {self.pydantic_model}.\nCleaned:\n{cleaned}")