"""Startup security guard: refuse an insecure JWT secret outside development."""
import pytest

from app.config import INSECURE_DEFAULT_SECRET, Settings


def _settings(**overrides) -> Settings:
    s = Settings()
    for key, value in overrides.items():
        setattr(s, key, value)
    return s


def test_dev_tolerates_insecure_default():
    _settings(APP_ENV="dev", JWT_SECRET=INSECURE_DEFAULT_SECRET).validate()  # no raise


def test_prod_rejects_default_secret():
    with pytest.raises(RuntimeError):
        _settings(APP_ENV="prod", JWT_SECRET=INSECURE_DEFAULT_SECRET).validate()


def test_prod_rejects_short_secret():
    with pytest.raises(RuntimeError):
        _settings(APP_ENV="prod", JWT_SECRET="too-short").validate()


def test_prod_accepts_strong_secret():
    _settings(APP_ENV="prod", JWT_SECRET="x" * 32).validate()  # no raise
