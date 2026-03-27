"""
llm_agent.response_parser
~~~~~~~~~~~~~~~~~~~~~~~~~
Extracts the code block from the LLM's markdown response.
"""

from __future__ import annotations

import re


def parse_code_block(response_text: str) -> str:
    """
    Extract the content of the first markdown code block from the response.
    If no code block is found, returns the entire response text stripped.
    """
    # Regex to match ```language ... ```
    # Match group 1 is the language (optional), group 2 is the code.
    pattern = re.compile(r"```(?:\w+)?\n(.*?)\n```", re.DOTALL)
    match = pattern.search(response_text)

    if match:
        return match.group(1).strip()
    
    # Fallback: if the LLM didn't use backticks, just return the raw text
    return response_text.strip()
