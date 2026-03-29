"""
llm_agent.llm_client
~~~~~~~~~~~~~~~~~~~~
Interfaces with the google-genai API to run the generated prompts
and return the refactored code.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class LLMClient:
    """Synchronous client to send prompts to the Gemini model."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        # Explicitly load .env file from the llm_agent directory if present
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv()  # Fallback to CWD

        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "API key must be provided or set in the GEMINI_API_KEY environment variable."
            )

        self.client = genai.Client(api_key=self.api_key)

    def generate_response(self, prompt: str, max_retries: int = 10) -> str:
        """
        Send a prompt to the LLM and return the text response.
        Implements basic exponential backoff for rate limits (429/503).
        """
        retry_delay = 5

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
                return response.text

            except Exception as e:
                err_msg = str(e).lower()
                if "429" in err_msg or "quota" in err_msg or "503" in err_msg:
                    # Try to extract the server's recommended retry delay (e.g., 'retryDelay': '56s')
                    wait_time = retry_delay
                    import re
                    match = re.search(r"retrydelay':\s*'(\d+)s'", err_msg)
                    if match:
                        wait_time = int(match.group(1)) + 2 # Add buffer
                        logger.info("Server recommended wait: %ds", wait_time)
                    else:
                        if "quota" in err_msg:
                            wait_time += 15 # Heavier penalty for quota
                    
                    logger.warning(
                        "Rate limit or server error on attempt %d/%d. Waiting %ds...",
                        attempt, max_retries, wait_time
                    )
                    time.sleep(wait_time)
                    # For next attempt, grow the baseline but respect server delay
                    retry_delay = max(retry_delay * 2, wait_time // 2)
                else:
                    # Non-retriable error
                    logger.error("LLM API Error: %s. Model: %s", e, self.model)
                    raise

        raise RuntimeError(f"Failed to generate response after {max_retries} attempts.")
