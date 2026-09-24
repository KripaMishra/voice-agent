from dataclasses import FrozenInstanceError

import pytest

from config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_SESSION_BUDGET_S,
    ConfigurationError,
    Settings,
)


def test_defaults_to_a_five_minute_budget():
    assert Settings.from_env({}).session_budget_s == DEFAULT_SESSION_BUDGET_S
    assert DEFAULT_SESSION_BUDGET_S == 300


def test_reads_budget_from_env():
    assert Settings.from_env({"SESSION_BUDGET_S": "120"}).session_budget_s == 120


@pytest.mark.parametrize("raw", ["", "   "])
def test_blank_budget_falls_back_to_default(raw):
    assert Settings.from_env({"SESSION_BUDGET_S": raw}).session_budget_s == 300


@pytest.mark.parametrize("raw", ["five minutes", "5m", "300.5"])
def test_unparseable_budget_is_rejected(raw):
    with pytest.raises(ConfigurationError, match="SESSION_BUDGET_S"):
        Settings.from_env({"SESSION_BUDGET_S": raw})


@pytest.mark.parametrize("raw", ["0", "-1"])
def test_non_positive_budget_is_rejected(raw):
    with pytest.raises(ConfigurationError, match="positive"):
        Settings.from_env({"SESSION_BUDGET_S": raw})


def test_defaults_to_a_local_sqlite_file():
    assert Settings.from_env({}).database_url == DEFAULT_DATABASE_URL


def test_database_url_overrides_default():
    settings = Settings.from_env({"DATABASE_URL": "sqlite:///:memory:"})
    assert settings.database_url == "sqlite:///:memory:"


def test_blank_database_url_falls_back_to_default():
    assert (
        Settings.from_env({"DATABASE_URL": "  "}).database_url == DEFAULT_DATABASE_URL
    )


def test_overrides_replace_individual_fields():
    base = Settings.from_env({})
    patched = base.with_overrides(session_budget_s=60)
    assert patched.session_budget_s == 60
    assert patched.database_url == base.database_url


def test_search_key_defaults_to_none():
    assert Settings.from_env({}).tavily_api_key is None


def test_search_key_is_read_from_env():
    assert Settings.from_env({"TAVILY_API_KEY": " abc "}).tavily_api_key == "abc"


@pytest.mark.parametrize("raw", ["", "   "])
def test_blank_search_key_is_treated_as_unset(raw):
    assert Settings.from_env({"TAVILY_API_KEY": raw}).tavily_api_key is None


def test_settings_are_immutable():
    with pytest.raises(FrozenInstanceError):
        Settings.from_env({}).session_budget_s = 10
