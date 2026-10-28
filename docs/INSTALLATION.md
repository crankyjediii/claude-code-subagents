# Installation and recovery

Choose either category plugins or copied Markdown agents. A plugin's agents are namespaced; copied definitions use the `name` in their frontmatter. Installing the same specialist both ways creates separately managed copies.

## Requirements

Plugin installation needs Claude Code. The shell installer needs Bash 3.2+ and standard Unix utilities. Install, uninstall, and ownership checks need `sha256sum` or `shasum`; standalone catalog and file downloads also need `curl`. Local installation makes no network requests and does not require Python or Git.

The installer is tested on Linux and macOS. On Windows, use an appropriate Unix environment such as WSL; native PowerShell execution has not been tested.

Plugin validation and discovery are tested with Claude Code 2.1.309. That is a tested version, not a claim that every older version is unsupported. Maintenance uses Python 3.10+; CI runs Python 3.12.

## Versioned release downloads

The [latest release](https://github.com/crankyjediii/claude-code-subagents/releases/latest) includes source ZIP and tar archives, ten separately packaged category plugins, `install-agents.sh`, `release-manifest.json`, and `SHA256SUMS`.

The downloadable installer defaults to the release's full source commit. Unlike the script from a rolling main checkout, it does not need an extra `--ref` to keep agent downloads on that revision:

```sh
curl --fail --location --proto '=https' --proto-redir '=https' \
  https://github.com/crankyjediii/claude-code-subagents/releases/download/v1.1.0/install-agents.sh \
  -o install-agents.sh
bash install-agents.sh --help
```

Review the script, then run `bash install-agents.sh --install python-specialist --project .` or use its interactive browser. `--repo` and `--ref` remain explicit overrides. `--help` prints the actual default source.

To verify every attached file, download the complete asset set into one directory and run `sha256sum -c SHA256SUMS` on Linux or `shasum -a 256 -c SHA256SUMS` on macOS. When downloading only one asset, compare its computed SHA-256 with that asset's line in `SHA256SUMS`. These checks verify transfer integrity, not an independent publisher signature.

Each category ZIP contains one plugin directory with its definitions, README, manifest, artwork, and MIT license. Extract it and use `claude --plugin-dir ./voltagent-lang` to load that category locally, or use the marketplace for managed installation and updates.

Source archives contain the complete maintained repository. Their included script retains the rolling-main default for standalone mode; use the separate pinned installer asset or supply the release's commit with `--ref` when running a source-archive script remotely.

## Plugin installation

```sh
claude plugin marketplace add crankyjediii/claude-code-subagents
claude plugin install voltagent-core-dev@voltagent-subagents
```

From a checkout, register the directory with `claude plugin marketplace add .`. Each `categories/NN-category/` directory is a plugin root; definitions live in its standard `agents/` directory. Root marketplace entries point to these category roots.

Update or uninstall through Claude Code:

```sh
claude plugin marketplace update voltagent-subagents
claude plugin update voltagent-core-dev@voltagent-subagents
claude plugin uninstall voltagent-core-dev@voltagent-subagents
```

Start a new session and inspect `/agents`. Plugin management follows the official [marketplace guide](https://code.claude.com/docs/en/plugin-marketplaces) and [plugin reference](https://code.claude.com/docs/en/plugins-reference).

## Shell installation

From a checkout, `bash install-agents.sh` opens the category browser. For automation:

```sh
bash install-agents.sh --list
bash install-agents.sh --list --category voltagent-lang
bash install-agents.sh --install python-specialist,code-reviewer --project .
bash install-agents.sh --install --category voltagent-infra --global
bash install-agents.sh --install --all --project . --dry-run
bash install-agents.sh --help
```

No-action mode requires a terminal. Explicit actions do not ask for a second confirmation. `--dry-run` checks the selection and conflicts without taking a lock or changing the target; it does not download every selected definition.

| Target option | Destination | Availability |
| :-- | :-- | :-- |
| No target option | `.claude/agents/` under the current directory | Current project |
| `--project DIRECTORY` | `DIRECTORY/.claude/agents/` | Selected project |
| `--global` | `~/.claude/agents/` | All projects |
| `--target DIRECTORY` | Exact directory supplied | Depends on Claude Code configuration |

The interactive browser asks for project or global scope if no target flag is supplied. A project agent with the same name takes precedence over a user agent, as documented in the official [subagent scope reference](https://code.claude.com/docs/en/sub-agents).

## Standalone sources and pinning

Download the script from the raw GitHub URL in the [README](../README.md#installation), review it, and run `bash install-agents.sh --standalone`. The standalone source defaults to `crankyjediii/claude-code-subagents` at `main`. `--repo OWNER/REPOSITORY` selects a fork; `--ref` accepts a branch, tag, or commit. `--local DIRECTORY` selects a local checkout and cannot be combined with a remote source.

For a repeatable install, use an actual published commit hash in both the installer URL and the installer's `--ref`. Pinning only the downloaded script leaves its catalog and agents on the default branch. A moving branch can change during a batch; a mismatch fails checksum verification before agent writes.

Catalog checksums come from the same source as the definitions. They detect mismatched or corrupted transfers, not a compromised repository. HTTPS-only redirects are enforced. No downloaded agent content is executed as a shell script.

## Ownership, conflicts, and backups

The installer records each managed name's installed SHA-256 value under `TARGET/.voltagent-state/`. It refuses to overwrite unmanaged or modified files without `--force`, even if an unmanaged file happens to match the downloaded definition. Force operations back up the original before adoption, replacement, or modified-file removal. Normal updates to unedited managed files also back up the old version.

Backups are stored in `TARGET/.voltagent-backups/backup.XXXXXXXX/`. Keep them until no longer needed. To restore a customization, inspect and copy the wanted file back to its original path. The next installer operation will recognize it as modified and preserve it unless explicitly forced.

Target components, selected agent files, and installer state may not be symlinks. macOS's fixed `/tmp`, `/var`, and `/etc` aliases are normalized first. Installer metadata paths must be directories, and stored ownership digests must be valid.

## Uninstall

```sh
bash install-agents.sh --installed --global
bash install-agents.sh --uninstall python-specialist --global
bash install-agents.sh --uninstall --category voltagent-lang --project .
bash install-agents.sh --uninstall --all --project . --dry-run
```

Category removal selects only managed agents from that category, preserving manual copies. Explicit-name and all-managed removal work offline from ownership records, even if an agent no longer exists upstream. Category removal needs the catalog, so standalone category removal needs network access. `--uninstall --all` never selects unrelated agent files.

The shell installer does not remove plugin-managed agents. Use Claude Code's plugin uninstall command for those.

## Interrupted runs and concurrent access

All selected definitions are staged and checksum-verified before agent files are written. The installer then acquires `TARGET/.voltagent-lock/`, rechecks conflicts, and writes each file by atomic rename. A second installer targeting the same directory fails with an actionable lock message. Read-only catalog listing and dry runs do not take the lock.

The batch and ownership records are not one filesystem transaction. A disk error or process interruption can leave a partial batch, or a new agent file without a matching record. Inspect the target and rerun; if an unrecorded file is reported as unmanaged, review it before an explicit backed-up adoption with `--force`.

Normal exit and handled termination clean up the lock and pending temporary files. SIGKILL or power loss cannot run cleanup. If a lock remains, confirm the process recorded in its `pid` file is no longer an active installer before removing that lock directory. A stale PID alone is not proof of ownership because process IDs can be reused. Never remove a lock while another installer may be writing. The lock coordinates installer processes; it does not prevent another program from editing the directory.

## Common problems

- **Agent does not appear:** verify the target and frontmatter, start a new Claude Code session, then inspect `/agents`.
- **Modified or unmanaged file:** compare the existing definition with the intended update. Keep the customization or use `--force` to preserve a backup and proceed.
- **Checksum mismatch:** retry with the script and `--ref` pinned to the same commit. Do not disable verification.
- **Invalid ownership record:** inspect the record and file together. Restore the original record from trusted evidence or treat the file as a manual copy; do not invent a digest to bypass a conflict.
- **Scope confusion:** use `--installed` against the same target used for installation. Global and project directories are independent.
