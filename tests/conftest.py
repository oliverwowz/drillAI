"""Pytest configuration and shared fixtures for DrillAI tests.

Provides synthetic test images, mocks for Gemini, mss, and OpenCV,
and isolated test directories.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure drill-ai root is on sys.path
TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


@pytest.fixture
def temp_project_dir(tmp_path):
    """Provide a temporary directory with logs and results subdirs."""
    logs_dir = tmp_path / "logs"
    results_dir = tmp_path / "results"
    logs_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def synthetic_rgb_image():
    """Create a synthetic PIL Image with patterns for testing."""
    from PIL import Image, ImageDraw
    
    img = Image.new("RGB", (400, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw simple shapes and text-like blocks
    draw.rectangle([20, 20, 380, 80], fill=(220, 220, 250), outline=(0, 0, 0))
    draw.text((30, 40), "Test Question: 2 + 2 = ?", fill=(0, 0, 0))
    draw.text((30, 100), "A. 3", fill=(0, 0, 0))
    draw.text((30, 130), "B. 4", fill=(0, 0, 0))
    draw.text((30, 160), "C. 5", fill=(0, 0, 0))
    draw.text((30, 190), "D. 6", fill=(0, 0, 0))
    return img


@pytest.fixture
def synthetic_blank_image():
    """Create a blank uniform PIL Image."""
    from PIL import Image
    return Image.new("RGB", (400, 300), color=(0, 0, 0))


@pytest.fixture
def mock_mss_monitors():
    """Mock monitor data returned by mss."""
    return [
        {"left": 0, "top": 0, "width": 3840, "height": 1080},   # 0: Virtual desktop
        {"left": 0, "top": 0, "width": 1920, "height": 1080},   # 1: Primary
        {"left": 1920, "top": 0, "width": 1920, "height": 1080}, # 2: Secondary
    ]
