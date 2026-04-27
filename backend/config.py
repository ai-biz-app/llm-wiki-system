import os
from pathlib import Path
from pydantic_settings import BaseSettings


def get_hermes_config() -> dict:
    """Read API keys from Hermes config files if available."""
    result = {}
    hermes_home = Path.home() / ".hermes"
    env_file = hermes_home / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    result[k.strip()] = v.strip().strip('"').strip("'")
    return result


HERMES_ENV = get_hermes_config()


class Settings(BaseSettings):
    wiki_path: str = "/root/Documents/Obsidian Vault/LLM-Wiki"
    llm_model: str = "kimi-k2.5"
    llm_provider: str = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = HERMES_ENV.get("OPENROUTER_API_KEY", HERMES_ENV.get("KIMI_API_KEY", ""))
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    max_upload_mb: int = 50
    job_queue_path: str = "/root/llm-wiki-system/backend/jobs/queue.jsonl"
    job_results_path: str = "/root/llm-wiki-system/backend/jobs/results"

    @property
    def wiki_dir(self) -> Path:
        return Path(self.wiki_path).expanduser()

    @property
    def raw_sources_dir(self) -> Path:
        return self.wiki_dir / "raw" / "sources"

    @property
    def raw_assets_dir(self) -> Path:
        return self.wiki_dir / "raw" / "assets"

    @property
    def wiki_sources_dir(self) -> Path:
        return self.wiki_dir / "wiki" / "sources"

    @property
    def wiki_entities_dir(self) -> Path:
        return self.wiki_dir / "wiki" / "entities"

    @property
    def wiki_concepts_dir(self) -> Path:
        return self.wiki_dir / "wiki" / "concepts"

    @property
    def wiki_analyses_dir(self) -> Path:
        return self.wiki_dir / "wiki" / "analyses"

    # Graphify integration
    graphify_enabled: bool = True
    graphify_mode: str = "standard"
    graphify_obsidian_export: bool = True
    graphify_directed: bool = False
    whisper_model: str = "base"

    # Graphify timeouts (seconds) - strict to prevent hangs
    graphify_timeout_default: int = 10      # General API calls
    graphify_timeout_query: int = 30        # Graph queries (natural language)
    graphify_timeout_ingest: int = 300      # Full corpus ingestion (5 min)
    graphify_timeout_sync: int = 5          # Graph sync service operations

    class Config:
        env_prefix = "LLM_WIKI_"
        env_file = ".env"


settings = Settings()


def get_settings() -> Settings:
    return settings
