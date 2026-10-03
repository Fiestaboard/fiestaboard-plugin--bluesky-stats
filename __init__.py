"""Bluesky Stats plugin for FiestaBoard.

Shows a Bluesky account's followers, following and post counts, and how
much each has changed since the first reading of the day.

Uses the public Bluesky AppView, which needs no sign-in or API key:

* ``GET https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor=<handle or DID>``
  returns ``app.bsky.actor.defs#profileViewDetailed`` (``handle``,
  ``displayName``, ``followersCount``, ``followsCount``, ``postsCount``).

The daily baseline is kept in memory only: it starts over at local midnight,
when the handle changes, and when FiestaBoard restarts.
"""

import logging
import re
import unicodedata
from datetime import date
from typing import Any, Dict, List, Optional

import requests
from src.board_chars import BoardChars
from src.plugins.base import PluginBase, PluginResult

logger = logging.getLogger(__name__)

PROFILE_URL = "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile"
USER_AGENT = "FiestaBoard Bluesky Stats Plugin (https://github.com/Fiestaboard/fiestaboard-plugin--bluesky-stats)"
REQUEST_TIMEOUT_SECONDS = 10
MIN_REFRESH_SECONDS = 60
COUNTS = (("followers", "followersCount"), ("following", "followsCount"), ("posts", "postsCount"))


class BlueskyError(Exception):
    """A failed fetch. *transient* errors may fall back to the last good data."""

    def __init__(self, message: str, *, transient: bool):
        super().__init__(message)
        self.transient = transient


def _today() -> date:
    return date.today()


def normalize_handle(raw: Any) -> str:
    """``@Alice`` -> ``alice.bsky.social``; DIDs pass through unchanged."""
    handle = str(raw or "").strip().lstrip("@")
    if not handle or handle.startswith("did:"):
        return handle
    handle = handle.lower()
    return handle if "." in handle else f"{handle}.bsky.social"


def board_safe(text: Any) -> str:
    """Uppercase *text*, fold accents and drop characters the board cannot show."""
    folded = unicodedata.normalize("NFKD", str(text or ""))
    kept = []
    for ch in folded.upper():
        if ch.isspace():
            kept.append(" ")
        elif ch not in "{}" and BoardChars.get_char_code(ch) is not None:
            kept.append(ch)
    return re.sub(r" {2,}", " ", "".join(kept)).strip()


def format_count(n: int) -> str:
    return f"{n:,}"


def format_short(n: int) -> str:
    """12345 -> 12.3K, 1260000 -> 1.3M. Below 1000 the number is unchanged."""
    if n < 1000:
        return str(n)
    value = float(n)
    for suffix in ("K", "M", "B"):
        value /= 1000
        if round(value, 1) < 1000 or suffix == "B":
            break
    return f"{value:.1f}".rstrip("0").rstrip(".") + suffix


def format_change(delta: int) -> str:
    return f"{delta:+,}"


class BlueskyStatsPlugin(PluginBase):
    """Public Bluesky profile counts with a daily change."""

    def __init__(self, manifest: Dict[str, Any]):
        super().__init__(manifest)
        self._baseline: Optional[Dict[str, int]] = None
        self._baseline_day: Optional[date] = None
        self._last_data: Optional[Dict[str, Any]] = None

    @property
    def plugin_id(self) -> str:
        return "bluesky_stats"

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        errors = []
        handle = normalize_handle(config.get("handle"))
        if not handle:
            errors.append("Bluesky handle is required")
        elif " " in handle:
            errors.append("Bluesky handle cannot contain spaces")
        refresh = config.get("refresh_seconds", MIN_REFRESH_SECONDS)
        if not isinstance(refresh, int) or refresh < MIN_REFRESH_SECONDS:
            errors.append(f"Refresh interval must be at least {MIN_REFRESH_SECONDS} seconds")
        return errors

    def on_config_change(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> None:
        if normalize_handle(old_config.get("handle")) != normalize_handle(new_config.get("handle")):
            self._baseline = None
            self._baseline_day = None
            self._last_data = None

    def _get_profile(self, handle: str) -> Dict[str, Any]:
        try:
            response = requests.get(
                PROFILE_URL,
                params={"actor": handle},
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.warning("Bluesky request failed: %s", exc)
            raise BlueskyError("Could not reach Bluesky", transient=True) from exc

        if response.status_code == 400:
            try:
                body = response.json()
                reason = body.get("message") or body.get("error")
            except (ValueError, AttributeError):
                reason = None
            raise BlueskyError(f"Bluesky: {reason or 'request rejected'} ({handle})", transient=False)
        if response.status_code == 429:
            raise BlueskyError("Bluesky rate limit reached; will retry", transient=True)
        if response.status_code != 200:
            raise BlueskyError(f"Bluesky API error: {response.status_code}", transient=True)
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            raise BlueskyError("Bluesky sent an unreadable response", transient=True)
        return body

    def _changes(self, counts: Dict[str, int]) -> Dict[str, str]:
        today = _today()
        if self._baseline is None or self._baseline_day != today:
            self._baseline = dict(counts)
            self._baseline_day = today
        if not self.config.get("show_change", True):
            return {f"{name}_change": "" for name in counts}
        return {f"{name}_change": format_change(counts[name] - self._baseline[name]) for name in counts}

    def fetch_data(self) -> PluginResult:
        handle = normalize_handle(self.config.get("handle"))
        if not handle:
            return PluginResult(available=False, error="Bluesky handle not configured")

        try:
            body = self._get_profile(handle)
        except BlueskyError as exc:
            if exc.transient and self._last_data is not None:
                return PluginResult(available=True, data=self._last_data)
            return PluginResult(available=False, error=str(exc))

        counts = {name: int(body.get(field) or 0) for name, field in COUNTS}
        shown_handle = board_safe(body.get("handle") or handle)
        data: Dict[str, Any] = {
            "display_name": board_safe(body.get("displayName")) or shown_handle,
            "handle": shown_handle,
        }
        for name, n in counts.items():
            data[name] = format_count(n)
            data[f"{name}_short"] = format_short(n)
            data[f"{name}_count"] = n
        data.update(self._changes(counts))
        self._last_data = data
        return PluginResult(available=True, data=data)
