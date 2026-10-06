"""Check that a Pydantic AI agent can reach the model through Portkey.

    .venv/bin/python smoke_test.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

HW_DIR = Path(__file__).resolve().parents[1]

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
for env_file in (HW_DIR / ".env", HW_DIR.parent / ".env"):  # repo .env first
    load_dotenv(env_file)
api_key = os.environ.get("PORTKEY_API_KEY")
if not api_key:
    sys.exit("PORTKEY_API_KEY is not set. Copy .env.example to .env and fill it in.")

client = AsyncOpenAI(
    api_key=api_key,
    base_url="https://api.portkey.ai/v1",
    default_headers={
        "x-portkey-api-key": api_key,
        "x-portkey-provider": "openai",
    },
)
model_name = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
model = OpenAIResponsesModel(model_name, provider=OpenAIProvider(openai_client=client))
agent = Agent(
    model,
    instructions="You are the Campus Customs shopping assistant. Reply in one short sentence.",
    model_settings=OpenAIResponsesModelSettings(
        openai_reasoning_effort=os.getenv("OPENAI_REASONING_EFFORT", "high"),
    ),
)

try:
    result = agent.run_sync("Say hello to a customer.")
except Exception as exc:
    sys.exit(f"Smoke test failed ({type(exc).__name__}). Check the model name and Portkey setup.")
print(f"{model_name}: {result.output}")
