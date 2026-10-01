"""
Central configuration for the RISKON backend. Every environment-dependent
value the backend reads comes through this one module — nothing else in
`backend/` calls `os.environ` directly, so there is exactly one place to look
when adding a new setting or checking what's actually configurable.

Loads `.env` from the repo root (not `backend/.env` — one file, one place to
paste the API key). Safe to import with no `.env`
present at all: every value has a sane default, and `ai_configured` simply
comes back False rather than raising.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name, default=False):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # --- Anthropic / Claude -------------------------------------------------
    # ANTHROPIC_API_KEY is the exact environment-variable name the official
    # `anthropic` Python SDK itself looks for when no api_key= is passed to
    # the client constructor — using the same name here means a user only
    # ever sets it once, in .env, and both this backend AND (if ever wired up
    # for real) engine/pipeline.ts's `new Anthropic()` would pick it up
    # identically.
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    anthropic_model: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5").strip()
    anthropic_timeout_seconds: float = float(os.environ.get("ANTHROPIC_TIMEOUT_SECONDS", "30"))
    anthropic_max_tokens: int = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "1536"))

    # --- AI provider switch ---------------------------------------------------
    # Which service backend/services/ai/provider.py routes analyze_incident()
    # calls to: "claude" or "nvidia_nim". Defaults to "claude" so an existing
    # deployment with only ANTHROPIC_API_KEY set keeps working exactly as
    # before with zero config changes -- switching a given environment to the
    # free NVIDIA NIM tier for V0 is an explicit AI_PROVIDER=nvidia_nim (plus
    # NVIDIA_API_KEY) in that environment's own .env/variables, never a
    # silent default change.
    ai_provider: str = os.environ.get("AI_PROVIDER", "claude").strip().lower()

    # --- NVIDIA NIM (free, OpenAI-compatible; used only when ai_provider is
    # "nvidia_nim") -------------------------------------------------------------
    # Get a key (free, no credit card) at https://build.nvidia.com/ .
    nvidia_api_key: str = os.environ.get("NVIDIA_API_KEY", "").strip()
    nvidia_nim_model: str = os.environ.get("NVIDIA_NIM_MODEL", "nvidia/nemotron-3-ultra-550b-a55b").strip()
    nvidia_nim_base_url: str = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()
    # Nemotron Ultra is a reasoning model -- it spends a large share of its
    # completion tokens on a visible chain-of-thought (returned separately as
    # reasoning_content) before writing the final JSON answer. 2048/60s
    # measured as NOT enough against a real incident (truncated mid-JSON);
    # 8192/150s is what an actual successful real call against this free
    # eval endpoint needed -- expect ~1-2.5 minutes per analysis, not
    # Claude's few-seconds latency.
    nvidia_nim_timeout_seconds: float = float(os.environ.get("NVIDIA_NIM_TIMEOUT_SECONDS", "150"))
    nvidia_nim_max_tokens: int = int(os.environ.get("NVIDIA_NIM_MAX_TOKENS", "8192"))

    # --- Database ------------------------------------------------------------
    # The SAME SQLite file every Python script in this repo already reads/
    # writes (database/generate_database.py, risk_intelligence/engine.py,
    # learning_engine/engine.py, ...) — no second database is introduced.
    database_path: Path = Path(os.environ.get("DATABASE_PATH", str(ROOT / "database" / "riskon.db")))

    # --- Server ---------------------------------------------------------------
    host: str = os.environ.get("RISKON_HOST", "0.0.0.0")
    # Most hosting platforms (Railway, Render, Fly.io, Heroku-likes) assign a
    # port at runtime via the plain `PORT` env var and expect the app to bind
    # to exactly that — not a fixed number. `PORT` wins when present;
    # `RISKON_PORT` remains for explicit local overrides; 8743 is the
    # long-standing local-dev default.
    port: int = int(os.environ.get("PORT") or os.environ.get("RISKON_PORT", "8743"))
    cors_origins: list = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]

    # --- Demo access gate (NOT real authentication) ----------------------------
    # Empty by default, which disables the gate entirely -- local dev and the
    # existing test suite are completely unaffected. Set both to protect a
    # public demo deployment behind a single shared username/password using
    # the browser's built-in HTTP Basic Auth prompt, before real per-user
    # accounts exist.
    demo_access_username: str = os.environ.get("DEMO_ACCESS_USERNAME", "").strip()
    demo_access_password: str = os.environ.get("DEMO_ACCESS_PASSWORD", "").strip()

    # --- Real per-user auth enforcement (opt-in) ------------------------------
    # Off by default: signup/login/sessions are fully real either way, but
    # this specifically controls whether unauthenticated requests get BLOCKED.
    # With this off (the default), RISKON keeps behaving exactly as it always
    # has -- open access, free "Viewing as (demo)" role switching -- so
    # nothing about the existing sales-demo experience changes unless this is
    # explicitly turned on for a real access-controlled pilot deployment.
    auth_required: bool = _bool("AUTH_REQUIRED", False)

    # Whether the session cookie gets Secure (HTTPS-only). An explicit env
    # var rather than sniffing request.url.scheme, because Railway (and most
    # PaaS) terminate TLS at their edge and forward plain HTTP to the
    # container -- scheme-sniffing would see "http" even in production and
    # silently omit Secure. Defaults to True outside local dev, so the common
    # cases need no extra configuration.
    session_cookie_secure: bool = _bool(
        "SESSION_COOKIE_SECURE", os.environ.get("RISKON_ENV", "development").strip() != "development"
    )

    # --- Misc -------------------------------------------------------------------
    log_level: str = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    environment: str = os.environ.get("RISKON_ENV", "development").strip()

    @property
    def ai_configured(self) -> bool:
        """True only when the ACTIVE provider (see ai_provider) has a
        non-empty API key. Never True by accident — an empty string,
        whitespace-only value, or the literal placeholder from .env.example
        all evaluate to False. A key set for the inactive provider does not
        count; this reflects whether AI features actually work right now."""
        if self.ai_provider == "nvidia_nim":
            return bool(self.nvidia_api_key)
        return bool(self.anthropic_api_key)

    @property
    def active_ai_model(self) -> str:
        return self.nvidia_nim_model if self.ai_provider == "nvidia_nim" else self.anthropic_model

    @property
    def demo_gate_enabled(self) -> bool:
        return bool(self.demo_access_password)

    def as_public_dict(self) -> dict:
        """Safe to return to a client (e.g. GET /api/health) — never
        includes the API key itself, only whether one is present."""
        return {
            "environment": self.environment,
            "ai_configured": self.ai_configured,
            "ai_provider": self.ai_provider,
            "ai_model": self.active_ai_model,
            "anthropic_model": self.anthropic_model,
            "database_path": str(self.database_path),
            "demo_gate_enabled": self.demo_gate_enabled,
            "auth_required": self.auth_required,
        }


settings = Settings()
