"""Prompt slicing helpers required by DeerFlow and local retrieval."""

import re


def prepare_grouped_actions(
    input: str,
    task: str,
    actions_index_list: list[int],
    candidates_index_list: list[int],
) -> str:
    query_matches = re.findall(r"<query>(.*?)</query>", input, re.DOTALL)
    query = query_matches[0].strip() if query_matches else ""
    if task == "predict_order":
        parts = ["<group>\n"]
        if actions_index_list:
            parts.append(
                prepare_grouped_content(
                    _tag_content(input, "history"), actions_index_list, "history"
                )
            )
        if candidates_index_list:
            parts.append(
                prepare_grouped_content(
                    _tag_content(input, "candidates"),
                    candidates_index_list,
                    "candidates",
                )
            )
        parts.extend(["</group>\n", f"<query>{query}</query>\n"])
        return "".join(parts)
    raise ValueError(f"unsupported task: {task}")


def _tag_content(value: str, tag: str) -> str:
    matches = re.findall(fr"<{tag}>(.*?)</{tag}>", value, re.DOTALL)
    return matches[0] if matches else ""


def prepare_grouped_content(contents: str, index_list: list[int], content_type: str) -> str:
    records = re.findall(r"\d+\.\s.*?(?=\n\d+\.|$)", contents, flags=re.DOTALL)
    selected = []
    for index in index_list:
        if index < 1 or index > len(records):
            raise ValueError(f"group index out of range: {index}")
        selected.append(records[index - 1].strip())
    body = "\n".join(selected)
    return f"<{content_type}>\n{body}\n</{content_type}>\n"


def parse_image(desc: str | None) -> tuple[str, list[str]]:
    if desc is None:
        return "", []
    image_tags = re.findall(r"<img .*?>", desc)
    sources = []
    for image_tag in image_tags:
        match = re.search(r'src="(.*?)"', image_tag)
        if match:
            sources.append(match.group(1))
    return re.sub(r"<img .*?>", "", desc), sources
