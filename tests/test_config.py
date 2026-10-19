"""Preflight-валидация конфигурации: ловит незаполненные .env человеческим языком."""

import config


def test_valid_config_passes(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "1234567890:" + "aA0_" * 10)
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "LLM_API_KEY", "sk-real-key-123")
    assert config.validate_config() == []


def test_placeholder_token_detected(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "ВАШ_ТЕЛЕГРАМ_ТОКЕН_ОТ_BotFather")
    problems = config.validate_config()
    assert any("заглушку" in p for p in problems)


def test_missing_token_reported(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    problems = config.validate_config()
    assert any("TELEGRAM_BOT_TOKEN" in p for p in problems)


def test_malformed_token_reported(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "не-токен")
    problems = config.validate_config()
    assert any("некорректно" in p for p in problems)


def test_missing_llm_key_reported(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "1234567890:" + "aA0_" * 10)
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    problems = config.validate_config()
    assert any("ключ нейросети" in p for p in problems)


def test_gemini_provider_uses_gemini_key(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "1234567890:" + "aA0_" * 10)
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    problems = config.validate_config()
    assert any("GEMINI_API_KEY" in p for p in problems)


def test_unknown_provider_reported(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "1234567890:" + "aA0_" * 10)
    monkeypatch.setattr(config, "LLM_PROVIDER", "claude")
    monkeypatch.setattr(config, "LLM_API_KEY", "sk-x")
    problems = config.validate_config()
    assert any("не поддерживается" in p for p in problems)
