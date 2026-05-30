from __future__ import annotations

import json
from typing import Any


def render_creator_prompt(*, task_id: str, context: dict[str, Any]) -> str:
    serialized_context = json.dumps(context, sort_keys=True, indent=2, allow_nan=False)
    return f"""You are the Creator in a creation-first autonomy loop.

Task id: {task_id}

Create first: propose one concrete, buildable creation before analysis expands. Use the
provided report context to choose a practical next object that can be implemented and
verified in this repository.

Return exactly one JSON object matching the CreationObject fields:
- id
- kind
- title
- hypothesis
- why_now
- first_code_change
- expected_experiment
- status
- continuation_reason
- evidence_refs
- target_files
- verification_commands
- uses_real_capital
- live_order_routing

Safety constraints:
- Do not use real capital.
- Do not perform live order routing.
- Do not access wallets.
- Do not request, reveal, or depend on exchange trading secrets.
- Set uses_real_capital=false.
- Set live_order_routing=false.

Serialized context:
{serialized_context}
"""


def render_builder_prompt(
    *, creation_json: dict[str, Any], runner_commands: list[str]
) -> str:
    serialized_creation = json.dumps(creation_json, sort_keys=True, indent=2, allow_nan=False)
    serialized_commands = json.dumps(runner_commands, sort_keys=True, indent=2, allow_nan=False)
    return f"""You are the Builder for a creation-first autonomy loop.

Write real project code for the creation object below. Keep changes focused on the
requested creation, add or update tests when behavior changes, and leave unrelated files
alone.

Forbidden live behavior:
- No live trading.
- No wallet access.
- No exchange order routing.
- No secret reads, including API keys, wallet seeds, exchange credentials, or trading
  secrets.

Creation JSON:
{serialized_creation}

Runner commands:
{serialized_commands}
"""
