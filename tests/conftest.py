"""Shared fixtures for the Bluesky Stats plugin tests.

``bsky`` patches ``requests.get`` with a fake Bluesky AppView that answers
``app.bsky.actor.getProfile`` with a payload shaped like the real
``profileViewDetailed`` (lexicon app.bsky.actor.defs). No test touches the
network. All accounts are invented.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from plugins.bluesky_stats import BlueskyStatsPlugin

MANIFEST_PATH = Path(__file__).parent.parent / "manifest.json"
PROFILE_URL = "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile"


class FakeResponse:
    def __init__(self, body=None, status_code=200):
        self._body = body
        self.status_code = status_code

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def profile(handle="alice.bsky.social", **overrides):
    body = {
        "did": "did:plc:testexample0000000000000",
        "handle": handle,
        "displayName": "Alice Rivers",
        "followersCount": 12345,
        "followsCount": 321,
        "postsCount": 4567,
        "indexedAt": "2026-01-01T00:00:00.000Z",
    }
    body.update(overrides)
    return body


class FakeBluesky:
    def __init__(self):
        self.profile = profile()
        self.queued = []
        self.calls = []

    def respond(self, response):
        """Queue a raw response (or exception) for the next call."""
        self.queued.append(response)

    def __call__(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        if self.queued:
            response = self.queued.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return FakeResponse(dict(self.profile))


@pytest.fixture
def manifest():
    return json.loads(MANIFEST_PATH.read_text())


@pytest.fixture
def bsky():
    fake = FakeBluesky()
    with patch("plugins.bluesky_stats.requests.get", side_effect=fake):
        yield fake


@pytest.fixture
def plugin(manifest):
    p = BlueskyStatsPlugin(manifest)
    p.config = {"enabled": True, "handle": "alice.bsky.social"}
    return p
