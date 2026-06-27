"""Pytest configuration and shared fixtures for oa_fetch_todo tests."""
import os
import sys
import json
import pytest

# Force dry-run for entire test session
os.environ.setdefault('OA_DRY_RUN', '1')

# Ensure project root is on sys.path so we can import ga
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@pytest.fixture
def mock_items():
    """Load 8 real items from oa_email_apply_2026-06-27.txt snapshot."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'oa_fetch_mock.json')
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def tmp_cwd(tmp_path, monkeypatch):
    """Provide a clean cwd for report file output."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
