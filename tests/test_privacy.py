from src.workflow import build_structured_resources


def _inputs() -> dict:
    return {
        "prompt": "<query>synthetic</query>",
        "history_actions_informations": {},
        "candidates_informations": {"candidate_p_001": "synthetic"},
    }


def test_deerflow_resources_keep_only_evaluation_fields() -> None:
    resources = build_structured_resources(_inputs())
    assert set(resources) == {
        "history_actions_informations",
        "candidates_informations",
    }
