# Security and trust boundaries

Agent definitions are instructions that run within Claude Code's permissions. Read the definition and its frontmatter before installing it. File contents, downloaded pages, and tool output can contain untrusted instructions; the agents direct the model to treat that material as evidence rather than as authority over the user's task.

## What is checked

The installer validates catalog paths and selected names, downloads over HTTPS, verifies source hashes before writes, refuses selected symlinks, preserves conflicting files, and coordinates writers with a target lock. CI checks ownership handling and failure paths in temporary directories. Plugins contain agent definitions and listing assets, with no bundled hooks or MCP connections.

The source review checks each definition's scope, tools, concrete workflow, failure considerations, and example result. These are source and packaging checks, not proof that a model will follow every instruction or solve every assigned task correctly.

## Boundaries

- Catalog hashes are fetched from the same repository as the files. They are integrity checks, not independent publisher signatures.
- Bash can modify files, launch programs, and contact services even when Write and Edit are absent. Agent can delegate to other tool-bearing definitions. Neither is a read-only capability.
- Atomic rename protects a single file replacement. Agent and ownership-file updates are not one transaction, and a whole batch is not transactional.
- The installer lock coordinates cooperating installers. It does not protect against a malicious process with write access to the same directory or stop simultaneous edits by an editor.
- A prompt cannot authorize production operations, prevent all prompt injection, or replace the host's tool permissions and review controls.

Use an immutable commit for reproducible installation and follow the [recovery guide](docs/INSTALLATION.md#interrupted-runs-and-concurrent-access) after an interrupted write.

## Reporting a vulnerability

Use this repository's [private vulnerability report form](https://github.com/crankyjediii/claude-code-subagents/security/advisories/new) when available. Include the affected commit, a minimal non-destructive reproduction, and the impact. Do not include live credentials or personal data. If private reporting is unavailable, open a public issue requesting a private reporting channel without disclosing exploit details.

This project has no published response-time or long-term-support guarantee. Fixes are described in the changelog and validated through the repository checks.
