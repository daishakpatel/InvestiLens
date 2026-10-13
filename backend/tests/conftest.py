"""Keep the whole suite on mock providers and built-in defaults, whatever the developer's `.env`
or shell selects (DR-004): no `.env` file is read, so a real API key can never reach a test."""

import os

from app.config import Settings

Settings.model_config["env_file"] = None
os.environ["PROVIDER_MODE"] = "mock"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "mock"
