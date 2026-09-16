"""Small JSON helpers used by released evaluation methods."""

import json
import logging

import json_repair


logger = logging.getLogger(__name__)


def repair_json_output(content: str) -> str:
    """Repair a likely JSON response without logging the response body."""

    content = content.strip()
    if not (content.startswith(("{", "[")) or "```json" in content or "```ts" in content):
        return content
    if content.startswith("```json"):
        content = content.removeprefix("```json")
    elif content.startswith("```ts"):
        content = content.removeprefix("```ts")
    if content.endswith("```"):
        content = content.removesuffix("```")
    try:
        repaired = json_repair.loads(content)
        return json.dumps(repaired, ensure_ascii=False)
    except Exception:
        logger.warning("JSON response repair failed")
        return content
