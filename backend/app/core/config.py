from functools import lru_cache
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRET_FRAGMENTS = (
    "change-me",
    "changeme",
    "local-dev",
    "replace",
    "placeholder",
    "example",
    "sample",
    "dummy",
    "your_",
    "your_real",
    "your-",
    "todo",
    "test",
)


class Settings(BaseSettings):
    app_name: str = "Personal AI OS API"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/personal_ai_os"
    database_connect_timeout_seconds: int = 2

    jwt_secret_key: str = Field(default="change-me-before-use")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    internal_webhook_secret: str = "change-me-before-use"
    webhook_signature_algorithm: str = "HMAC-SHA256"
    webhook_timestamp_tolerance_seconds: int = 60

    # DEPRECATED (passe 0 socle toolbox): n8n is out of the production path.
    # The WR bridges are now direct backend calls (app/services/imperium/wr_bridge.py)
    # and the only execution mechanism is the runner. Kept until the VPS container is
    # confirmed exported and cut (user action, out of pass).
    n8n_base_url: str | None = None
    n8n_webhook_secret: str | None = None
    n8n_request_timeout_seconds: int = 10
    n8n_dry_run: bool = True
    wr_n8n_qwen_dry_run_webhook_path: str = "imperium/wr/interactive-start-qwen-dry-run"
    wr_n8n_answers_integrate_webhook_path: str = "imperium/wr/answers-integrate-qwen-dry-run"

    qwen_enabled: bool = False
    qwen_base_url: str | None = None
    qwen_request_timeout_seconds: int = 60
    qwen_dry_run: bool = True

    # Ported n8n WR bridges (wr_bridge.py): when True, the launch/answer flows run
    # the bridge inline (same behavior the n8n workflows had when reachable and
    # not dry-run). Default False preserves today's queued-task behavior.
    wr_bridge_enabled: bool = False

    # Feature flags (socle): everything is born disabled; activation is explicit.
    real_ai_enabled: bool = False
    embeddings_enabled: bool = False
    runner_enabled: bool = False
    notifications_enabled: bool = False
    # Spawns the APScheduler/LISTEN threads at app startup (deployment sets it;
    # tests keep it off and drive execute_job directly).
    runner_scheduler_autostart: bool = False

    # Embedding serving (Tower GPU, Tailscale-only). GET /health + POST /embed.
    embedding_base_url: str | None = None
    embedding_request_timeout_seconds: int = 30
    embedding_expected_dimensions: int = 1024
    embedding_batch_size: int = 32

    # Travel v0 (Google Directions). very_high privacy NEVER reaches a provider.
    google_directions_api_key: str | None = None
    travel_request_timeout_seconds: int = 5

    # Prayer (MAWAQIT client). Provider URL is environment-specific (doc 41 §6.3).
    mawaqit_base_url: str | None = None
    mawaqit_request_timeout_seconds: int = 10

    imperium_canonical_user_id: UUID | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def validate_for_startup(self) -> None:
        self._validate_secret("JWT_SECRET_KEY", self.jwt_secret_key)
        self._validate_secret("INTERNAL_WEBHOOK_SECRET", self.internal_webhook_secret)
        if self.environment not in {"local", "test"} and self.imperium_canonical_user_id is None:
            raise RuntimeError(
                "IMPERIUM_CANONICAL_USER_ID must be set outside local/test environments. "
                "Run python -m app.cli.create_user, then export the resulting user UUID as IMPERIUM_CANONICAL_USER_ID."
            )
        if self.n8n_webhook_secret is not None:
            self._validate_secret("N8N_WEBHOOK_SECRET", self.n8n_webhook_secret)

    @staticmethod
    def _validate_secret(name: str, value: str) -> None:
        normalized = value.strip().lower()
        if any(fragment in normalized for fragment in PLACEHOLDER_SECRET_FRAGMENTS):
            raise RuntimeError(f"{name} must be changed before startup.")
        if len(value.strip()) < 32:
            raise RuntimeError(f"{name} must be at least 32 characters.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
