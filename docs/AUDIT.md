# Public-release audit

Audit date: October 27, 2026. Scope: all 170 category agents, the standalone installer agent, marketplace and category packaging, installation and removal, maintenance tooling, CI, documentation, and source distribution. The changes are tracked under collection version 1.1.0.

## Method and limits

Every category definition was read for routing, scope, task-specific steps, failure checks, completion evidence, tool access, and vendor neutrality. Each received a concrete illustrative request and expected result. The [per-agent index](AGENT_REVIEW.md) links every definition and the digest of the reviewed source. The machine-readable records are in [evals/cases.jsonl](../evals/cases.jsonl).

These are source-level reviews. The same examples appear in the definitions, so they are not held-out model evaluations. No claim is made that 170 model-run tasks passed, that every model will obey these prompts, or that the definitions received an independent security certification. Source digests make changes since review detectable; they do not make the review itself correct.

The installation audit uses isolated homes, temporary targets, fixture downloads, real local plugin installation, and post-publication GitHub smoke checks. The installer and packaging checks do not exercise a production deployment, physical hardware, or every possible host configuration. Tested shell environments are Linux and macOS; native Windows execution is outside the verified scope.

## Findings and changes

| ID | Finding | Resolution and evidence |
| :-- | :-- | :-- |
| A01 | Installer conflict checks occurred before downloads, so a file created during staging could be overwritten. Concurrent writers were not coordinated. | Stage and verify first, acquire a per-target lock, then recheck conflicts. A fixture creates a personal file during download; it is preserved. Existing-lock tests cover install and uninstall. |
| A02 | Category uninstall required every catalog member to have been installed. Partial-category installs could not be removed as a category. | Remove only managed members of the selected category, preserve manual copies, and treat an empty managed selection as a no-op. |
| A03 | Review, planning, and documentation roles had broad write, shell, or delegation access without a task-specific need. | Assign explicit tool profiles. Local inspection and source-research profiles exclude execution and direct writes. Document that Bash and Agent remain execution paths. Profile regression checks reject silent widening. |
| A04 | Short prompts gave few concrete invocation examples and overlapping roles lacked handoff boundaries. | Add a reviewed example and expected outcome to every category definition. Clarify API/implementation, schema/query/operations, retrieval/indexing, debugging/triage, and orchestration/planning boundaries. |
| A05 | Newlines in a selected-names argument could cause input after the first line to be silently ignored. Ownership records and metadata-directory types were not consistently validated. | Validate the complete selection before parsing, reject invalid ownership digests and non-directory state paths, and test that failures preserve content. |
| A06 | Identical unmanaged definitions could be silently adopted, and pending target files could survive a failed rename. | Require explicit adoption with a backup, track pending writes for cleanup, and test failed-rename behavior. |
| A07 | Link checks skipped HTML assets and local fragments. Nested definitions could load in Claude Code while remaining absent from the flat catalog. | Check Markdown and HTML file references and anchors. Reject nested or misplaced agent definitions and symlinked source roots. |
| A08 | Tests asserted exactly 170 agents and 17 per category, preventing legitimate additions despite the documented contribution process. | Compare installed and listed names with the actual source inventory, while retaining the minimum 161-agent and ten-category requirements. |
| A09 | The installer agent defaulted to a project target but its plugin command used the CLI's default user scope. Remote preview and install could also refer to different moving revisions. | Specify project/user plugin scope and pin the downloaded script, previews, catalog, and installation to one resolved commit. The CLI scope flag was checked against the installed command help. |
| A10 | CI used an unpinned Claude Code validator, and plugin listing validation warned about missing artwork. | Record the validator version in collection metadata, install that version in CI, and generate per-category PNG icons. Keep actual component-discovery checks alongside manifest validation. |

## Agent review coverage

All ten categories have 17 reviewed definitions. Each file now states its scope and tool use, approach, task boundaries, an example request and expected result, and a completion contract. All definitions retain `model: inherit`; none requires an external MCP service or embeds a product promotion.

Read-only inspection is deliberately narrower than analysis with execution. A definition with Bash can write or contact services even without Write or Edit. A coordinator with Agent can delegate to workers with further tools. Documentation-only profiles return execution checks to the parent instead of claiming they ran. The [usage guide](USAGE.md#tool-profiles) and per-agent index make these distinctions visible.

Eight orchestration roles retain Agent for delegated execution. Other planning, summarization, and audit roles provide assignments or findings for the parent to act on. Meta prompts keep discovery, ownership, shared-codebase preservation, runtime limits, and unavailable-delegation fallback instructions.

## Verification process

The repeatable commands are:

```sh
python3 tools/sync.py --check
python3 tools/validate.py
python3 tools/audit_agents.py --check
python3 -m unittest discover -s tests -v
bash -n install-agents.sh
shellcheck install-agents.sh
python3 tools/check_plugins.py
```

The test suite covers complete and selective installs; global and project destinations; filenames with spaces; interactive terminal selection; local and fixture-based standalone sources; checksum and transfer failure; ownership, customization, and backups; symlinks; invalid selections; dry runs; offline removal; lock contention; download-time conflicts; corrupt state; cleanup after failed writes; metadata drift; review coverage; and generated assets and documentation references.

Two intentionally defective installer copies were tested outside the source tree. Removing target-lock acquisition caused the lock regression case to fail. Removing checksum verification caused the tampered-download case to fail. Both originals remained unchanged. This establishes that those tests detect their intended defects; it is not a project-wide mutation score.

Plugin checks install each category under a temporary `CLAUDE_CONFIG_DIR` and require every expected agent name in Claude Code's actual component inventory. They validate the marketplace and category roots with the official CLI. CI repeats source and installer tests on Linux and macOS. Published-source smoke checks download the exact installer commit, install selected agents from GitHub raw, inspect ownership, remove them offline, and install a category from the GitHub marketplace in an isolated configuration.

## Remaining operating limits

- Agent and ownership-file changes are atomic per file, not one transaction across a batch. Interruption recovery is documented and requires inspection before adopting an unrecorded file.
- A process killed with SIGKILL or power loss cannot clean up its lock. The installer will refuse subsequent writes until the operator verifies and removes a stale lock.
- Locks coordinate cooperating installer processes. They do not prevent an editor or a malicious process with directory access from making concurrent changes.
- Catalog checksums share the source repository's trust. Pinning helps reproducibility but is not independent signature verification.
- Model behavior, domain correctness on future assignments, actual screen-reader use, physical-device behavior, and production operational outcomes are not established by these source and distribution checks.

README badges link to this repository's state. Artwork and plugin icons are generated from maintained code, and the category index and counts come from the actual definitions. The sponsorship section contains no unverified listings.
