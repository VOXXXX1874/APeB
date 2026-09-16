# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import enum
import os


class SearchEngine(enum.Enum):
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    BRAVE_SEARCH = "brave_search"
    ARXIV = "arxiv"


SELECTED_SEARCH_ENGINE = os.getenv("SEARCH_API", SearchEngine.DUCKDUCKGO.value)
