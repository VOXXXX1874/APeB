from __future__ import annotations

import logging

from src.tools.decorators import log_io


def test_tool_logging_omits_inputs_and_outputs(caplog) -> None:
    @log_io
    def sample_tool(value: str) -> str:
        return value + " OUTPUT MARKER"

    with caplog.at_level(logging.DEBUG):
        assert sample_tool("INPUT MARKER").endswith("OUTPUT MARKER")
    text = caplog.text
    assert "INPUT MARKER" not in text
    assert "OUTPUT MARKER" not in text
    assert "sample_tool" in text
