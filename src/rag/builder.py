# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from src.rag.structured import StructuredBM25Retriever
from src.rag.retriever import Retriever

def build_structured_retriever(structured_resources: dict, task: str) -> Retriever | None:
    return StructuredBM25Retriever(structured_resources, task)
