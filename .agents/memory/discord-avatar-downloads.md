---
name: Discord avatar downloads
description: Prefer discord.py Asset.read() over a separate HTTP client for avatar bytes.
---

Use `user.display_avatar.with_size(...).read()` when a feature needs Discord avatar data.

**Why:** The Discord library already handles the CDN request and its routing; a second raw `aiohttp` request can fail even when embeds and normal avatar URLs work.

**How to apply:** Decode the returned bytes locally, enforce a size limit before image processing, and catch Discord HTTP errors around the read.