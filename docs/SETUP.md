# Bluesky Stats Setup Guide

Put a Bluesky account's follower, following and post counts on your board in about a minute.

## Overview

**What it does:** shows any public Bluesky profile's display name, handle and counts, plus how much each count changed since the first reading of the day (for example `+12`).

**Prerequisites:**
- A FiestaBoard install with internet access
- The Bluesky handle you want to show (yours or anyone's). No Bluesky account, sign-in or API key is needed.

## Quick Setup

1. **Enable:** open **Integrations**, find **Bluesky Stats** and turn it on.
2. **Configure:** enter the handle, for example `alice.bsky.social`. A leading `@` is fine, and a bare name like `alice` means `alice.bsky.social`. Custom-domain handles (`example.com`) and DIDs (`did:plc:...`) also work. Save.
3. **Template:** create a page and add variables such as `{{bluesky_stats.followers}}` and `{{bluesky_stats.followers_change}}`, or start from the plugin's demo page.
4. **View:** the board updates on the refresh interval (every 15 minutes by default).

## Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{{bluesky_stats.display_name}}` | Display name (the handle when none is set) | `ALICE RIVERS` |
| `{{bluesky_stats.handle}}` | Handle without the @ | `ALICE.BSKY.SOCIAL` |
| `{{bluesky_stats.followers}}` | Followers | `12,345` |
| `{{bluesky_stats.followers_short}}` | Followers, abbreviated | `12.3K` |
| `{{bluesky_stats.following}}` | Accounts followed | `321` |
| `{{bluesky_stats.following_short}}` | Accounts followed, abbreviated | `321` |
| `{{bluesky_stats.posts}}` | Posts | `4,567` |
| `{{bluesky_stats.posts_short}}` | Posts, abbreviated | `4.6K` |
| `{{bluesky_stats.followers_count}}` | Followers as a plain number | `12345` |
| `{{bluesky_stats.following_count}}` | Following as a plain number | `321` |
| `{{bluesky_stats.posts_count}}` | Posts as a plain number | `4567` |
| `{{bluesky_stats.followers_change}}` | Change in followers today | `+12` |
| `{{bluesky_stats.following_change}}` | Change in following today | `+1` |
| `{{bluesky_stats.posts_change}}` | Change in posts today | `+3` |

## Configuration Reference

| Setting | Key | Default | Description |
|---------|-----|---------|-------------|
| Enable Bluesky Stats | `enabled` | `false` | Turn the plugin on |
| Bluesky Handle | `handle` | (required) | The account to show |
| Show Today's Change | `show_change` | `true` | Fill the `*_change` variables; when off they are empty |
| Refresh Interval (seconds) | `refresh_seconds` | `900` | How often to fetch; at least 60 |

**Environment variables:** none. The plugin uses Bluesky's public API, which needs no key.

## Troubleshooting

**"Bluesky: Profile not found (...)"** - check the spelling of the handle. Handles are the full domain (`alice.bsky.social`), not the display name.

**The change is always `+0`** - the baseline is the first reading of the day, so the change grows as the day goes on. It also starts over when FiestaBoard restarts or the handle changes.

**The numbers stopped updating** - when Bluesky cannot be reached or rate-limits requests, the board keeps showing the last good numbers and the plugin retries on the next refresh. Raise the refresh interval if you share an IP with many other Bluesky clients.

**Emoji are missing from the display name** - the board has no tiles for them, so they are dropped. If nothing is left, the handle is shown instead.
