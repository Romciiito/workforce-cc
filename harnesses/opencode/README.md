# opencode harness adapter

opencode looks for agent files under `.opencode/agents/`. The adapter writes a single context agent that surfaces workforce-cc artifacts to opencode sessions.

**Limitations:** orchestration must happen in Claude Code; opencode sessions are context-aware but don't run intent-validator / conductor / alignment-guard.
