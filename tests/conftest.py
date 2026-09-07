from pathlib import Path

import pytest

from hydgap.config import load_config

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def tiny_config():
    return load_config(FIXTURES / "model_tiny.yaml")
