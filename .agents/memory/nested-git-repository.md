---
name: Nested Git repository access
description: The bot source is a nested repository with its own GitHub origin and must be pushed from that repository, not the workspace root.
---

The bot source has its own Git history and remote inside the project workspace. Workspace-level Git helpers may not detect that nested origin, so repository operations should be run from the bot repository itself.

**Why:** The workspace root and the bot repository are separate Git repositories, and the root has no GitHub origin for the bot.

**How to apply:** Inspect the nested repository status and remote before committing; push from the nested repository when changes are intended for the bot's GitHub project.