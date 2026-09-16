"""Lazy tool exports keep validation and non-agent CLIs lightweight."""

from importlib import import_module


_EXPORTS = {
    "crawl_tool": ("src.tools.crawl", "crawl_tool"),
    "python_repl_tool": ("src.tools.python_repl", "python_repl_tool"),
    "get_web_search_tool": ("src.tools.search", "get_web_search_tool"),
    "get_structured_retriever_tool": (
        "src.tools.retriever",
        "get_structured_retriever_tool",
    ),
}


def __getattr__(name: str):
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


__all__ = sorted(_EXPORTS)
