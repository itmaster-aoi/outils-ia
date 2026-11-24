---
description: Recall relevant memories and knowledge from CortexDB
---

Search the CortexDB global brain for context relevant to the query below, then summarize what you find (cite the memory/knowledge ids). Prefer the unified `knowledge_memory_recall` tool; fall back to `memory_search` / `knowledge_search`. Expand the query into keywords and aliases before searching. Always pass the memory bucket of the atelier convention: `scope=user`, `user_id` = the normalized Windows login, `namespace=assistant`; without these filters the server searches another bucket and finds nothing. If nothing matches, check these filters before you say so. If nothing matches, say so plainly.

Recall:

$ARGUMENTS
