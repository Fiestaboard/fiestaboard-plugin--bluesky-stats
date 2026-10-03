"""Tests for the Bluesky Stats plugin. All HTTP is faked (see conftest)."""

from datetime import date
from unittest.mock import patch

import pytest
import requests

from plugins.bluesky_stats import (
    BlueskyStatsPlugin,
    board_safe,
    format_change,
    format_count,
    format_short,
    normalize_handle,
)

from .conftest import PROFILE_URL, FakeResponse, profile


# --- helpers ---------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("alice.bsky.social", "alice.bsky.social"),
        ("@Alice.Bsky.Social", "alice.bsky.social"),
        ("  alice  ", "alice.bsky.social"),
        ("did:plc:AbC123", "did:plc:AbC123"),
        ("example.com", "example.com"),
        ("", ""),
        (None, ""),
        ("@", ""),
    ],
)
def test_normalize_handle(raw, expected):
    assert normalize_handle(raw) == expected


@pytest.mark.parametrize(
    "n,count,short",
    [
        (0, "0", "0"),
        (999, "999", "999"),
        (1000, "1,000", "1K"),
        (4567, "4,567", "4.6K"),
        (12345, "12,345", "12.3K"),
        (999_949, "999,949", "999.9K"),
        (999_999, "999,999", "1M"),
        (1_260_000, "1,260,000", "1.3M"),
        (3_000_000_000, "3,000,000,000", "3B"),
    ],
)
def test_format_counts(n, count, short):
    assert format_count(n) == count
    assert format_short(n) == short


def test_format_change():
    assert format_change(12) == "+12"
    assert format_change(-3) == "-3"
    assert format_change(0) == "+0"
    assert format_change(1500) == "+1,500"


def test_board_safe_drops_emoji_and_braces():
    assert board_safe("Alice 🦋 {Rivers}") == "ALICE RIVERS"
    assert board_safe("Beyoncé") == "BEYONCE"
    assert board_safe(None) == ""


# --- config ----------------------------------------------------------------


def test_plugin_id(plugin):
    assert plugin.plugin_id == "bluesky_stats"


def test_validate_config(plugin):
    assert plugin.validate_config({"handle": "alice.bsky.social"}) == []
    assert plugin.validate_config({"handle": "@alice"}) == []
    assert plugin.validate_config({}) == ["Bluesky handle is required"]
    assert plugin.validate_config({"handle": "bad handle"}) == ["Bluesky handle cannot contain spaces"]
    assert plugin.validate_config({"handle": "a.b", "refresh_seconds": 10}) == [
        "Refresh interval must be at least 60 seconds"
    ]
    assert plugin.validate_config({"handle": "a.b", "refresh_seconds": "x"}) == [
        "Refresh interval must be at least 60 seconds"
    ]


# --- fetch -----------------------------------------------------------------


def test_fetch_success(plugin, bsky):
    result = plugin.fetch_data()
    assert result.available and result.error is None
    d = result.data
    assert d["display_name"] == "ALICE RIVERS"
    assert d["handle"] == "ALICE.BSKY.SOCIAL"
    assert d["followers"] == "12,345"
    assert d["followers_short"] == "12.3K"
    assert d["following"] == "321"
    assert d["following_short"] == "321"
    assert d["posts"] == "4,567"
    assert d["posts_short"] == "4.6K"
    assert (d["followers_count"], d["following_count"], d["posts_count"]) == (12345, 321, 4567)
    # First reading of the day is the baseline.
    assert (d["followers_change"], d["following_change"], d["posts_change"]) == ("+0", "+0", "+0")

    call = bsky.calls[0]
    assert call["url"] == PROFILE_URL
    assert call["params"] == {"actor": "alice.bsky.social"}
    assert call["timeout"] == 10
    assert "FiestaBoard" in call["headers"]["User-Agent"]
    assert "Authorization" not in call["headers"]


def test_bare_name_is_sent_as_bsky_social(plugin, bsky):
    plugin.config = {"handle": "@Alice"}
    plugin.fetch_data()
    assert bsky.calls[0]["params"] == {"actor": "alice.bsky.social"}


def test_missing_handle_makes_no_request(plugin, bsky):
    plugin.config = {"handle": "  "}
    result = plugin.fetch_data()
    assert not result.available
    assert result.error == "Bluesky handle not configured"
    assert bsky.calls == []


def test_missing_counts_and_name_fall_back(plugin, bsky):
    bsky.profile = {"did": "did:plc:x", "handle": "bob.test"}
    d = plugin.fetch_data().data
    assert d["display_name"] == "BOB.TEST"
    assert d["followers"] == "0" and d["posts_count"] == 0


def test_blank_display_name_uses_handle(plugin, bsky):
    bsky.profile = profile(displayName="🦋")
    assert plugin.fetch_data().data["display_name"] == "ALICE.BSKY.SOCIAL"


def test_daily_change_tracks_baseline(plugin, bsky):
    with patch("plugins.bluesky_stats._today", return_value=date(2026, 10, 1)):
        plugin.fetch_data()
        bsky.profile = profile(followersCount=12357, followsCount=320, postsCount=4570)
        d = plugin.fetch_data().data
    assert (d["followers_change"], d["following_change"], d["posts_change"]) == ("+12", "-1", "+3")

    # A new day starts a new baseline from that day's first reading.
    with patch("plugins.bluesky_stats._today", return_value=date(2026, 10, 2)):
        d = plugin.fetch_data().data
        assert d["followers_change"] == "+0"
        bsky.profile = profile(followersCount=12360)
        assert plugin.fetch_data().data["followers_change"] == "+3"


def test_change_hidden_when_disabled(plugin, bsky):
    plugin.config = {"handle": "alice.bsky.social", "show_change": False}
    plugin.fetch_data()
    bsky.profile = profile(followersCount=20000)
    d = plugin.fetch_data().data
    assert (d["followers_change"], d["following_change"], d["posts_change"]) == ("", "", "")


def test_handle_change_resets_baseline(plugin, bsky):
    plugin.fetch_data()
    old = dict(plugin.config)
    plugin.config = {"handle": "bob.bsky.social"}
    plugin.on_config_change(old, plugin.config)
    bsky.profile = profile(handle="bob.bsky.social", followersCount=10)
    assert plugin.fetch_data().data["followers_change"] == "+0"


def test_other_config_change_keeps_baseline(plugin, bsky):
    plugin.fetch_data()
    old = dict(plugin.config)
    plugin.config = {"handle": "alice.bsky.social", "refresh_seconds": 600}
    plugin.on_config_change(old, plugin.config)
    bsky.profile = profile(followersCount=12346)
    assert plugin.fetch_data().data["followers_change"] == "+1"


# --- errors ----------------------------------------------------------------


def test_profile_not_found(plugin, bsky):
    bsky.respond(FakeResponse({"error": "InvalidRequest", "message": "Profile not found"}, 400))
    result = plugin.fetch_data()
    assert not result.available
    assert result.error == "Bluesky: Profile not found (alice.bsky.social)"


def test_bad_request_without_body(plugin, bsky):
    bsky.respond(FakeResponse(ValueError("no json"), 400))
    assert plugin.fetch_data().error == "Bluesky: request rejected (alice.bsky.social)"


@pytest.mark.parametrize(
    "response,error",
    [
        (FakeResponse({"error": "RateLimitExceeded"}, 429), "Bluesky rate limit reached; will retry"),
        (FakeResponse(None, 502), "Bluesky API error: 502"),
        (requests.ConnectionError("down"), "Could not reach Bluesky"),
        (FakeResponse(ValueError("not json"), 200), "Bluesky sent an unreadable response"),
        (FakeResponse(["not", "a", "dict"], 200), "Bluesky sent an unreadable response"),
    ],
)
def test_transient_errors_without_cache(plugin, bsky, response, error):
    bsky.respond(response)
    result = plugin.fetch_data()
    assert not result.available
    assert result.error == error


def test_transient_error_keeps_last_good_data(plugin, bsky):
    good = plugin.fetch_data().data
    bsky.respond(requests.Timeout("slow"))
    result = plugin.fetch_data()
    assert result.available
    assert result.data == good


def test_not_found_does_not_serve_stale_data(plugin, bsky):
    plugin.fetch_data()
    bsky.respond(FakeResponse({"error": "InvalidRequest", "message": "Profile not found"}, 400))
    assert not plugin.fetch_data().available


def test_registered_with_core(manifest):
    assert BlueskyStatsPlugin(manifest).manifest["id"] == "bluesky_stats"
