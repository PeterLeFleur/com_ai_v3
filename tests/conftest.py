"""
Pytest configuration and shared fixtures for COM-AI v3
"""

import pytest
import sys
from pathlib import Path

# Add src directory to Python path for testing
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "src"))


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    return {
        "environment": "testing",
        "log_level": "DEBUG",
        "openai_api_key": "test_key",
        "anthropic_api_key": "test_key",
        "gemini_api_key": "test_key",
    }


@pytest.fixture
def mock_brain():
    """Mock brain instance for testing"""
    try:
        from src.brain.cerebrum.cadre import CerebrumCadre
        return CerebrumCadre()
    except ImportError:
        # Return mock for initial setup
        class MockBrain:
            def __init__(self):
                self.providers = {}
            
            def add_provider(self, name, provider):
                self.providers[name] = provider
            
            def get_status(self):
                return {"active_providers": list(self.providers.keys())}
        
        return MockBrain()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location"""
    for item in items:
        # Mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)