"""Manifest contract checks: categories, previews and docs consistency."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALID_CATEGORIES = {"art", "data", "entertainment", "home", "transit", "utility", "weather"}


def tiles(row: str) -> int:
    """Board width of a literal row: {NN} and {/name} codes count as one and zero tiles."""
    row = re.sub(r"\{/[a-z]+\}", "", row)
    return len(re.sub(r"\{\d+\}", "#", row))


def test_required_fields(manifest):
    for key in ("id", "name", "version", "settings_schema", "variables", "teaser", "previews"):
        assert key in manifest
    assert manifest["category"] in VALID_CATEGORIES
    assert "oauth" not in manifest  # public API, no sign-in


def test_teaser_and_previews_fit(manifest):
    assert tiles(manifest["teaser"]) <= 15
    sizes = {"flagship": (22, 6), "note": (15, 3)}
    seen = set()
    for preview in manifest["previews"]:
        cols, rows = sizes[preview["device_type"]]
        seen.add(preview["device_type"])
        assert len(preview["rows"]) <= rows
        assert all(tiles(r) <= cols for r in preview["rows"])
        assert "{{" not in "".join(preview["rows"])
    assert seen == {"flagship", "note"}


def test_variables_are_documented(manifest):
    readme = (ROOT / "README.md").read_text()
    setup = (ROOT / "docs" / "SETUP.md").read_text()
    for name in manifest["variables"]["simple"]:
        assert f"{{{{bluesky_stats.{name}}}}}" in readme
        assert f"{{{{bluesky_stats.{name}}}}}" in setup
    for key in manifest["settings_schema"]["properties"]:
        assert f"`{key}`" in readme
        assert f"`{key}`" in setup


def test_docs_section_order():
    readme = (ROOT / "README.md").read_text()
    order = ["# Bluesky Stats Plugin", "![Bluesky Stats Display](./docs/board-display.png)",
             "**→ [Setup Guide](./docs/SETUP.md)**", "## Overview", "## Template Variables",
             "## Example Templates", "## Configuration", "## Features", "## Author"]
    positions = [readme.index(s) for s in order]
    assert positions == sorted(positions)
    setup = (ROOT / "docs" / "SETUP.md").read_text()
    order = ["# Bluesky Stats Setup Guide", "## Overview", "## Quick Setup", "## Template Variables",
             "## Configuration Reference", "## Troubleshooting"]
    positions = [setup.index(s) for s in order]
    assert positions == sorted(positions)
