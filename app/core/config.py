"""Application settings, loaded once from the environment / .env file."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.model_profile import ModelProfile, get_model_profile
from app.core.token_budget import effective_context_window


class Settings(BaseSettings):
    # `protected_namespaces=()` is required: pydantic v2 reserves the `model_`
    # prefix, and this app deliberately uses `model_name` / `model_num_ctx`.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # --- app ---
    app_name: str = "Catronaut"
    app_env: Literal["dev", "prod"] = "dev"

    # --- model serving (Ollama) ---
    ollama_base_url: str = "http://localhost:11434"
    # dev: qwen3:4b | prod: qwen3.8-27b (decided). The prod tag is not in the
    # public Ollama library — it needs a Modelfile / private registry on the GPU box.
    model_name: str = "qwen3:4b"

    # Context window handed to Ollama. Ollama's own default is much smaller and truncates
    # silently, so a value is always sent explicitly — but the value comes from the model
    # profile, not from here. `None` means "use the whole window this model has"
    # (`ModelProfile.context_window`), so pointing MODEL_NAME at a bigger model widens the
    # window with no second setting to remember.
    #
    # Set MODEL_NUM_CTX only to *constrain* a run below the model's real capability — a
    # local CPU box short on RAM. Never to describe the model: that is the profile's job,
    # and a hardcoded number here silently caps every model behind it (the old 4096 default
    # held `qwen3:4b` to 1/8 of its own 32768 window).
    model_num_ctx: int | None = None

    # Local CPU inference is slow (measured: ~150s for 158 tokens on qwen3:4b),
    # so the default is generous on purpose.
    model_timeout_s: float = 600.0

    # Qwen3 is a hybrid-reasoning model. Sent as Ollama's `think` flag.
    # NOTE: qwen3:4b currently ignores it and still emits reasoning inline —
    # see OllamaProvider.extract_content, which strips the leaked block.
    model_think: bool = False

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def model_profile(self) -> ModelProfile:
        """Capabilities of the currently configured model. See app/core/model_profile.py."""
        return get_model_profile(self.model_name)

    @property
    def effective_num_ctx(self) -> int:
        """The window actually sent to the backend: the profile's, unless MODEL_NUM_CTX
        constrains it further. This is the one value to read — `model_num_ctx` alone is the
        raw override and is `None` in the normal case."""
        return effective_context_window(self.model_profile, self.model_num_ctx)

    @property
    def expose_raw_response(self) -> bool:
        """Only leak the full provider payload to HTTP clients in dev."""
        return self.is_dev


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
