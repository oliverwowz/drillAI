"""Tests for DrillAI Gemini API Client."""

import json
from unittest.mock import MagicMock, patch
import pytest

from gemini_client import (
    GeminiClient,
    GeminiAuthError,
    GeminiModelError,
    GeminiRateLimitError,
    GeminiClientError,
)


def test_init_without_api_key():
    """Verify GeminiClient raises GeminiAuthError when API key is empty."""
    with pytest.raises(GeminiAuthError, match="API key is required"):
        GeminiClient(api_key="")


def test_parse_response_clean_json():
    """Verify parsing clean JSON response."""
    with patch("gemini_client.genai.Client"):
        client = GeminiClient(api_key="AIzaSyTest")
        mock_resp = MagicMock()
        mock_resp.text = '{"question_detected": true, "question_text": "Sample?"}'

        result = client._parse_response(mock_resp)
        assert result["question_detected"] is True
        assert result["question_text"] == "Sample?"


def test_parse_response_markdown_fenced_json():
    """Verify parsing JSON wrapped in markdown code fences."""
    with patch("gemini_client.genai.Client"):
        client = GeminiClient(api_key="AIzaSyTest")
        mock_resp = MagicMock()
        mock_resp.text = '```json\n{"question_detected": false, "warnings": []}\n```'

        result = client._parse_response(mock_resp)
        assert result["question_detected"] is False
        assert result["warnings"] == []


def test_parse_response_malformed_json():
    """Verify fallback to raw_text on malformed JSON."""
    with patch("gemini_client.genai.Client"):
        client = GeminiClient(api_key="AIzaSyTest")
        mock_resp = MagicMock()
        mock_resp.text = "This is not JSON at all."

        result = client._parse_response(mock_resp)
        assert result.get("parse_error") is True
        assert result.get("raw_text") == "This is not JSON at all."


def test_analyze_image_skips_duplicate(synthetic_rgb_image):
    """Verify identical hash skips API call."""
    with patch("gemini_client.genai.Client") as mock_client:
        mock_models = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = '{"question_detected": true}'
        mock_models.generate_content.return_value = mock_resp
        mock_client.return_value.models = mock_models

        client = GeminiClient(api_key="AIzaSyTest")

        # First call with hash
        res1 = client.analyze_image(synthetic_rgb_image, "sys", "prompt", image_hash="hash123")
        assert res1.get("question_detected") is True
        assert mock_models.generate_content.call_count == 1

        # Second call with same hash
        res2 = client.analyze_image(synthetic_rgb_image, "sys", "prompt", image_hash="hash123")
        assert res2.get("_skipped") is True
        assert mock_models.generate_content.call_count == 1


def test_analyze_image_retries_on_rate_limit(synthetic_rgb_image):
    """Verify retry behavior and rate limit error on exhaustion."""
    with patch("gemini_client.genai.Client") as mock_client:
        mock_models = MagicMock()
        mock_models.generate_content.side_effect = Exception("429 Resource exhausted: quota exceeded")
        mock_client.return_value.models = mock_models

        client = GeminiClient(api_key="AIzaSyTest", max_retries=2, base_delay=0.01)

        with pytest.raises(GeminiRateLimitError, match="Rate limit exceeded"):
            client.analyze_image(synthetic_rgb_image, "sys", "prompt")

        assert mock_models.generate_content.call_count >= 3  # initial + retries (+ fallback)


def test_analyze_image_does_not_retry_auth_error(synthetic_rgb_image):
    """Verify auth errors are raised immediately without retry."""
    with patch("gemini_client.genai.Client") as mock_client:
        mock_models = MagicMock()
        mock_models.generate_content.side_effect = Exception("403 Forbidden: Invalid API key")
        mock_client.return_value.models = mock_models

        client = GeminiClient(api_key="AIzaSyTest", max_retries=3)

        with pytest.raises(GeminiAuthError, match="Authentication failed"):
            client.analyze_image(synthetic_rgb_image, "sys", "prompt")

        assert mock_models.generate_content.call_count == 1
