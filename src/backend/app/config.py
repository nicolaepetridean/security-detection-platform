"""Application configuration, sourced from environment variables with sane defaults."""
import os

INSECURE_DEFAULT_SECRET = "dev-insecure-secret-change-me"
_MIN_SECRET_BYTES = 32


class Settings:
    # dev | prod. Controls fail-fast security checks; defaults to dev so the demo and
    # tests run out of the box. Set APP_ENV=prod in any real deployment.
    APP_ENV: str = os.getenv("APP_ENV", "dev")

    # SQLite file lives alongside the backend by default; override via env for tests.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./detections.db")

    # JWT signing. In a real deployment this MUST come from a secret manager.
    JWT_SECRET: str = os.getenv("JWT_SECRET", INSECURE_DEFAULT_SECRET)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

    # Permissive CORS for local development (Vite dev server).
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")

    def validate(self) -> None:
        """Fail fast on an insecure JWT secret outside development.

        In dev we tolerate the weak default so the project runs with zero setup; in a
        non-dev environment an unset/default/short secret would let anyone forge an
        admin token, so we refuse to start.
        """
        if self.APP_ENV == "dev":
            return
        if self.JWT_SECRET == INSECURE_DEFAULT_SECRET:
            raise RuntimeError(
                "JWT_SECRET is the insecure default. Set a strong, random "
                "JWT_SECRET (32+ bytes) via the environment when APP_ENV is not 'dev'."
            )
        if len(self.JWT_SECRET) < _MIN_SECRET_BYTES:
            raise RuntimeError(
                f"JWT_SECRET is too short ({len(self.JWT_SECRET)} bytes); use at least "
                f"{_MIN_SECRET_BYTES} bytes when APP_ENV is not 'dev'."
            )


settings = Settings()
