# Using and choosing agents

An agent is a Markdown definition with YAML frontmatter and a task prompt. Claude Code uses its short description for routing, then loads its instructions when invoked. This follows the official [subagent format](https://code.claude.com/docs/en/sub-agents).

## Give the agent a bounded assignment

Name the specialist, the relevant files or workflow, the desired result, and any constraints:

```text
Use backend-developer to fix concurrent redemption of a single-use invitation.
Inspect the existing service and database constraints. Preserve the public
response contract, add a meaningful race regression test, and report the
commands actually run. Do not deploy the service.
```

For plugin agents, include the plugin name when ambiguity is possible: “Use code-reviewer from voltagent-quality.” For project or user copies, use their frontmatter name. Check `/agents` in a new session after changing installations.

## Choose between overlapping roles

| When the work is… | Start with | Related boundary |
| :-- | :-- | :-- |
| An external API contract | `api-designer` | `backend-developer` implements server behavior |
| One user journey across layers | `fullstack-developer` | Use a narrower specialist for a single-layer change |
| Relational schema and integrity | `database-designer` | `sql-specialist` handles queries; `database-administrator` handles operations |
| A reported regression without a reliable reproduction | `regression-triager` | `debugging-specialist` owns code repair |
| Existing code changes to review | `code-reviewer` | It returns findings and does not edit the patch |
| Retrieval and citation quality | `rag-engineer` | `vector-search-engineer` handles index recall and latency |
| Model-tool integration | `llm-engineer` | `prompt-engineer` handles instruction revisions |
| Selecting specialists | `agent-organizer` | `workflow-orchestrator` executes authorized stages |
| A compact continuation note | `context-manager` | `handoff-coordinator` handles recipient ownership and prerequisites |

Definitions contain their own scope guidance and a concrete example task. Install only categories useful for the work; every agent description adds routing context.

## Tool profiles

The frontmatter is the actual declared tool list. Review it before use. Tools still operate within the host's permissions, and an agent prompt is not an access-control boundary.

| Profile | Intended work | Tool behavior |
| :-- | :-- | :-- |
| Analysis | Local review, planning, handoff, and source exploration | Read, Glob, and Grep; no shell, direct writes, or delegation |
| Research | Source-based questions and synthesis | Inspection plus WebFetch and WebSearch; no shell or direct writes |
| Documents | Documentation, requirements, and product specifications | Inspection, direct file editing, and web research; execution checks return to the parent |
| Analysis with execution | Benchmarks, data analysis, compatibility probes | Bash is available and can write files or make network requests; this profile is not read-only |
| Implementation | Code, tests, configuration, and bounded local operations | Inspection, direct file editing, and Bash |
| Coordination | Work that benefits from delegated execution | Implementation tools plus Agent, subject to runtime limits and the parent assignment |

Some roles add web tools to inspect current advisories. The review manifest records the profile of each definition. If a check needs a tool absent from the definition, the agent must label it unexecuted and provide the exact check to the parent conversation.

Adding Bash, Write, Edit, Agent, or an MCP tool changes what the agent can do. Do not describe a definition as read-only after adding an execution or delegation path.

## Definition structure

The maintained code reviewer starts with:

```yaml
---
name: code-reviewer
description: "Use when you need to review changes for concrete defects and maintainability risks."
tools: Read, Glob, Grep
model: inherit
---
```

Its body defines scope and tool use, an approach, task boundaries, an example task, and completion evidence. `model: inherit` keeps the session's model choice; the collection does not route roles to fixed model tiers. Customize a local copy when needed and review the [contribution rules](../CONTRIBUTING.md) before submitting changes.

## Meta orchestration

`voltagent-meta` works best with other categories installed. An organizer should discover available specialists, give workers bounded ownership, preserve other changes, and verify integration. It must provide a parent-executable plan when a tool, specialist, or nesting capability is unavailable. Installing the category does not guarantee a particular runtime concurrency or nesting limit.

Only roles that need delegated execution receive Agent. Planning, progress auditing, and context summarization do not require it. A request to plan a deployment is not permission to perform it.
