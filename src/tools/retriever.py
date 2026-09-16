# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
from typing import Optional, Type
from langchain_core.tools import BaseTool
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from pydantic import BaseModel, Field

from src.rag import Document, Retriever, Resource, build_structured_retriever
from src.utils.prepare_prompts import parse_image

logger = logging.getLogger(__name__)


class RetrieverInput(BaseModel):
    keywords: str = Field(description="search keywords to look up")


class RetrieverTool(BaseTool):
    name: str = Field(
        default="local_search_tool",
        description="The name of the tool",
    )
    description: str = Field(
        default="Useful for retrieving information from the file with `rag://` uri prefix, it should be higher priority than the web search or writing code. Input should be a search keywords.",
        description="The description of the tool",
    )
    args_schema: Type[BaseModel] = Field(default_factory=RetrieverInput)

    retriever: Retriever = Field(default_factory=Retriever)
    resources: list[Resource] = Field(default_factory=list)

    def _run(
        self,
        keywords: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> list[Document]:
        logger.debug("Retriever tool invoked")
        documents = self.retriever.query_relevant_documents(keywords, self.resources)
        if not documents:
            return "No results found from the local knowledge base."
        return [doc.__str__() for doc in documents]

    async def _arun(
        self,
        keywords: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> list[Document]:
        return self._run(keywords, run_manager.get_sync())


class ProductRetrieverTool(RetrieverTool):
    response_format: str = "content_and_artifact"
    def _run(
        self,
        keywords: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> list[Document]:
        logger.debug("Retriever tool invoked")
        documents = self.retriever.query_relevant_documents(keywords, self.resources)
        if not documents:
            return "No results found from the local knowledge base."

        # Build textual summary (or fallback) for content
        text_content = []
        image_blocks = []
        for doc in documents:
            # Suppose each doc has .text and .images attributes
            text_desc, images_src = parse_image(doc.page_content)
            text_content.append(text_desc)
            #for url in images_src[:2]:
            #    encoded_block = self._download_and_encode_image(url)
            #    if encoded_block:
            #        image_blocks.append(encoded_block)

        # We include both text content and the image artifacts
        return text_content, {"images": image_blocks}


def get_structured_retriever_tool(structured_resources: dict, task: str, name: str = "structured_search_tool") -> RetrieverTool | None:
    if not structured_resources:
        return None
    logger.info(f"create structured retriever tool")
    retriever = build_structured_retriever(structured_resources, task)

    if not retriever:
        return None
    return ProductRetrieverTool(name=name,
                         description=(
                             "Useful for retrieving structured detailed information. "
                             "You can use product title to search information of a certain product or"
                             "use some keywords to search relevant products and videos in the user history."
                         ),
                         args_schema=RetrieverInput,
                         retriever=retriever,
                         resources=retriever.list_resources())
