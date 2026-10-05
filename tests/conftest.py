import os
import sys

import pytest

# Let tests import app modules (config, data_source, ...) from the project folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def no_password_by_default(monkeypatch):
    """Tests start with the app open; password tests switch it on themselves."""
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("APP_USERNAME", raising=False)
