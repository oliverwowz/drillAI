"""Tests for DrillAI Configuration Management."""

import pytest
from pathlib import Path
from config import AppConfig, parse_region, load_config


def test_default_config_creation():
    """Verify default AppConfig initialization."""
    config = AppConfig()
    assert config.gemini_model == "gemini-3.8-flash"
    assert config.screenshot_interval == 1.0
    assert config.monitor_index == 1
    assert config.change_threshold == 0.03
    assert config.api_cooldown == 3.0
    assert config.mouse_enabled is False
    assert config.mouse_dry_run is True


def test_missing_api_key_raises_error():
    """Verify require_api_key raises ValueError when key is empty."""
    config = AppConfig(gemini_api_key="")
    with pytest.raises(ValueError, match="GEMINI_API_KEY is not set"):
        config.require_api_key()


def test_valid_api_key_does_not_raise():
    """Verify require_api_key passes when key is present."""
    config = AppConfig(gemini_api_key="AIzaSyDummyTestKey")
    config.require_api_key()  # Should not raise


def test_parse_region_valid():
    """Verify valid region string parsing."""
    res = parse_region("200, 150, 1200, 800")
    assert res == (200, 150, 1200, 800)


@pytest.mark.parametrize("invalid_region", [
    "200,150,1200",          # Not 4 parts
    "200,150,1200,800,100",  # 5 parts
    "abc,150,1200,800",      # Non-integer
    "200,150,-100,800",      # Negative width
    "200,150,1200,-50",      # Negative height
    "-10,150,1200,800",      # Negative X
    "200,-5,1200,800",       # Negative Y
    "0,0,0,100",             # Zero width
    "0,0,100,0",             # Zero height
])
def test_parse_region_invalid(invalid_region):
    """Verify parse_region rejects invalid values."""
    with pytest.raises(ValueError):
        parse_region(invalid_region)


def test_config_validation():
    """Verify AppConfig.validate detects out-of-bound settings."""
    config = AppConfig(
        screenshot_interval=0.01,  # Too small (<0.1)
        change_threshold=1.5,      # Too big (>1.0)
        api_cooldown=-1.0,         # Negative
        monitor_index=-2,          # Negative
        max_mouse_actions=-5,      # Negative (must be >= 0)
        ambiguous_image_policy="invalid_policy",
        log_level="SUPER_DEBUG",
    )
    errors = config.validate()
    assert len(errors) >= 7
    assert any("interval" in e.lower() for e in errors)
    assert any("threshold" in e.lower() for e in errors)
    assert any("cooldown" in e.lower() for e in errors)
    assert any("monitor" in e.lower() for e in errors)
    assert any("mouse" in e.lower() for e in errors)
    assert any("policy" in e.lower() for e in errors)
    assert any("log level" in e.lower() for e in errors)


def test_load_config_from_env(monkeypatch, tmp_path):
    """Verify load_config reads values from environment variables."""
    monkeypatch.setenv("GEMINI_API_KEY", "env_test_key_123")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
    monkeypatch.setenv("SCREENSHOT_INTERVAL", "2.5")
    monkeypatch.setenv("MONITOR_INDEX", "2")
    monkeypatch.setenv("CHANGE_THRESHOLD", "0.08")
    monkeypatch.setenv("API_COOLDOWN", "5.0")
    monkeypatch.setenv("REGION_ENABLED", "true")
    monkeypatch.setenv("REGION_X", "10")
    monkeypatch.setenv("REGION_Y", "20")
    monkeypatch.setenv("REGION_WIDTH", "500")
    monkeypatch.setenv("REGION_HEIGHT", "400")

    cfg = load_config(base_dir=tmp_path)
    assert cfg.gemini_api_key == "env_test_key_123"
    assert cfg.gemini_model == "gemini-1.5-pro"
    assert cfg.screenshot_interval == 2.5
    assert cfg.monitor_index == 2
    assert cfg.change_threshold == 0.08
    assert cfg.api_cooldown == 5.0
    assert cfg.region_enabled is True
    assert cfg.region == (10, 20, 500, 400)
