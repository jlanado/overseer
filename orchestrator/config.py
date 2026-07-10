import os


class Settings:
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")

    # LiteLLM proxy mode (local models) — used instead of anthropic_api_key
    # when set. See .env.example "Mode A vs Mode B".
    litellm_base_url: str = os.environ.get("LITELLM_BASE_URL", "")
    litellm_api_key: str = os.environ.get("LITELLM_API_KEY", "")
    anthropic_model: str = os.environ.get("ANTHROPIC_MODEL", "")
    anthropic_small_fast_model: str = os.environ.get("ANTHROPIC_SMALL_FAST_MODEL", "")
    reviewer_model: str = os.environ.get("REVIEWER_MODEL", "")

    @property
    def using_litellm(self) -> bool:
        return bool(self.litellm_base_url)

    postgres_user: str = os.environ.get("POSTGRES_USER", "overseer")
    postgres_password: str = os.environ.get("POSTGRES_PASSWORD", "")
    postgres_db: str = os.environ.get("POSTGRES_DB", "overseer")
    postgres_host: str = os.environ.get("POSTGRES_HOST", "postgres")
    postgres_port: str = os.environ.get("POSTGRES_PORT", "5432")

    webhook_secret: str = os.environ.get("WEBHOOK_SECRET", "")
    workspace_dir: str = os.environ.get("WORKSPACE_DIR", "/workspace")
    max_fix_attempts: int = int(os.environ.get("MAX_FIX_ATTEMPTS", "3"))
    approval_timeout_seconds: int = int(os.environ.get("APPROVAL_TIMEOUT_SECONDS", "1800"))

    # Scopes the Fixer's Claude Code Edit permission to only the files
    # touched by the triggering diff, and tells it up front which files
    # those are — see nodes/fixer.py. Off by default: this is a soft,
    # prompt/allowedTools-level constraint (Bash stays unscoped, so it's
    # not a hard security boundary), and narrowing Fixer's visibility can
    # cost it useful context on some fixes. Validate the token-savings
    # tradeoff against your own runs before turning this on.
    diff_only_mode: bool = os.environ.get("DIFF_ONLY_MODE", "false").lower() == "true"

    registry_url: str = os.environ.get("REGISTRY_URL", "localhost:5000")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password}"
        )


settings = Settings()
