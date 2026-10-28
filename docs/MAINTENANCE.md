# Maintenance and releases

Agent files are maintained directly. The scratch process used to create the initial collection is not a runtime or maintenance dependency.

## Generated distribution

Run `python3 tools/sync.py` after changing category agents or collection metadata. This reads the ten configured directories and produces:

- `.claude-plugin/marketplace.json` with one entry per category.
- `categories/*/.claude-plugin/plugin.json`, with metadata for each category. Definitions use the standard `agents/` directory at each plugin root so Claude Code discovers them directly.
- `categories/*/LICENSE`, ensuring every separately installed plugin includes the MIT notice.
- Category README files and the marked root README index.
- `tools/catalog.tsv`, containing category, plugin, name, routing description, source path, and SHA-256, separated by pipes.
- `docs/agent-count.svg`, counting category definitions only.
- `docs/assets/banner.svg` and per-plugin PNG icons, rendered deterministically by `tools/branding.py` without image-library dependencies.

The standalone `agent-installer.md` is maintained separately. If renaming the repository, update `collection.json`, the shell installer default, the standalone agent installer, and the README download and badge URLs together. Validation checks identity presence; review all links after a rename.

The last-update badge uses GitHub's latest commit date for main. No scheduled timestamp commits are needed. The catalog and count badge change only when their source content changes. CI rejects stale generated files and never writes into pull-request branches.

## Verify a change

```sh
python3 tools/sync.py --check
python3 tools/validate.py
python3 tools/audit_agents.py --check
python3 -m unittest discover -s tests -v
bash -n install-agents.sh
shellcheck install-agents.sh
python3 tools/check_plugins.py
```

Python tests use the local fixture downloader to exercise standalone behavior without live network dependencies. The installer does not accept arbitrary HTTP base URLs; production downloads are restricted to GitHub raw HTTPS URLs.

`tools/check_plugins.py` runs the official validator, installs all ten local plugins with a temporary `CLAUDE_CONFIG_DIR`, and checks the component inventory for every expected agent. It does not alter your normal plugin configuration or invoke a model. This catches a valid manifest whose files are not discovered at runtime.

CI installs the Claude Code version recorded in `collection.json` under `validation.claude-code`. Update it deliberately and rerun plugin inventory checks before changing the pin. Workflow concurrency cancels superseded runs, and workflow tokens have read-only contents access.

The per-agent review record must match the source being released. Review the changed scope, tools, example request, and expected result before updating its source digest. Run `python3 tools/audit_agents.py` to render the index. Do not turn an illustrative record into a runtime pass claim; keep actual execution evidence separate.

After publication, verify raw access by downloading the installer into a fresh temporary directory. Install one agent with `--standalone --ref COMMIT --target DIRECTORY`, verify the digest, then uninstall it using the same target. Use an actual commit hash from the published repository in place of COMMIT. Never use your real global agents directory for smoke tests.

## Release

1. Update `collection.json` version with a semantic version appropriate to the changes. Agent and plugin renames can break invocation names.
2. Regenerate metadata and complete all checks.
3. Merge into main, wait for CI, and verify the raw-download smoke test against that commit.
4. Create and push an annotated tag matching `vVERSION` from that verified main commit. The release workflow reuses the full validation workflow, requires the tag's version to match collection metadata, and requires the commit to belong to main.
5. The workflow builds deterministic source ZIP/tar archives, ten plugin ZIPs, a commit-pinned downloadable installer, `release-manifest.json`, and `SHA256SUMS`. It tests the extracted source and every individual plugin ZIP, including live pinned installer downloads, before creating a draft, uploading all assets, and publishing the release.
6. Verify the public release's tag, assets, checksums, and installation path. Do not reuse a published version for different artifacts. A failed draft can be resumed; a rerun refuses to overwrite an already public release.

The build can also be reproduced from a committed revision:

```sh
python3 tools/release.py --ref HEAD --tag v1.1.0 --output dist
python3 tools/check_release.py dist --online
```

Use the actual version tag for a later release. `dist` must be absent or empty. Building HEAD requires a clean working tree. The builder reads the committed tree, so untracked workstation files and `.git/` are excluded. Archives normalize ordering, timestamps, owners, and file modes; identical inputs with the same Python/zlib toolchain produce identical bytes. The release manifest records the exact source commit. The downloadable installer differs from the source script only in its default ref, which is pinned to that commit.

Release workflows have read-only permissions during validation; only the tag publication job receives contents write permission. Third-party actions are pinned to full commit hashes and monitored by Dependabot. Main branch protection requires the named validation checks and disables force pushes and deletion for contributors; repository administrators retain GitHub's normal bypass capability.

Users update marketplace plugins with Claude Code's plugin commands. Individual installations update by rerunning the installer; edited files require explicit force and are backed up. SHA-256 values detect mismatches between catalog and agents, not compromise of the repository itself. For repeatable installation, pin both the installer URL and `--ref` to the same commit.

## Sponsor listings

Accept product exposure only in the README sponsorship section. Label paid listings, record the approved sponsor name and URL accurately, and remove expired listings. Agent definitions and generated descriptions remain vendor-neutral. There are no initial sponsors.
