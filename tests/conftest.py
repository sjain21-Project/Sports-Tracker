import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


class FakeClient:
    """Stands in for HttpClient and serves canned responses keyed by URL suffix."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[tuple[str, dict | None]] = []

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        for suffix, payload in self.responses.items():
            if url.endswith(suffix):
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise AssertionError(f"Unexpected request: {url}")


@pytest.fixture
def fixture():
    return load_fixture


@pytest.fixture
def fake_client():
    return FakeClient
