# Repository instructions

This repository distributes Markdown subagents, ten category plugins, and a Bash installer. Read CONTRIBUTING.md before editing agent definitions.

- Treat `categories/*/agents/*.md` as the agent source of truth. `agent-installer.md` is an additional standalone utility and is not counted in the category badge.
- `collection.json` defines category order, plugin names, repository identity, marketplace name, and release version. The default branch is main.
- Run `python3 tools/sync.py` after agent edits. It generates category README files, the marked README index, `.claude-plugin/marketplace.json`, category plugin manifests, `tools/catalog.tsv`, and the count badge.
- Review every changed definition's routing, example result, and tool access; deliberately refresh its entry in `evals/cases.jsonl` only after that review. Run `python3 tools/audit_agents.py` and include its `--check` mode in verification. Illustrative cases do not claim model execution.
- Keep instructions vendor-neutral. Product promotion belongs only in the explicit README sponsorship section. Do not fabricate sponsors or contact details.
- Installer changes must preserve Bash 3.2 compatibility and local operation without curl. Remote operation downloads only over HTTPS and verifies selected files against catalog SHA-256 values before writes.
- Preserve unmanaged or edited target files. Force operations must retain backups. Refuse symlinks at selected target and state paths. Do not use eval, source downloaded content, or run remote agent instructions as shell commands.
- Stage and verify downloads before locking the target; recheck conflicts under the lock before writes. Category removal selects only managed members. Keep agent and state writes atomic per file and describe whole-batch recovery limits accurately.
- Run `python3 tools/validate.py`, `python3 -m unittest discover -s tests -v`, and `shellcheck install-agents.sh`. Validate the marketplace and each category using `claude plugin validate` when the CLI is available.
- Tests use temporary directories. Do not install agents into the contributor's actual user scope as a verification shortcut.
- Release assets come from committed Git trees via `tools/release.py`. Run `tools/check_release.py` against the exact assets before publication. Every plugin must include LICENSE. Never replace assets on an already public release.

Maintenance uses Python 3.10+ with the standard library. Installation uses Bash and ordinary Unix utilities; remote downloads additionally need curl. Do not add a Python dependency to the user installer.
