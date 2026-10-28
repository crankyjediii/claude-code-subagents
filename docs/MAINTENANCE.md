# Maintenance and releases

Agent files are maintained directly. The scratch process used to create the initial collection is not a runtime or maintenance dependency.

## Generated distribution

Run `python3 tools/sync.py` after changing category agents or collection metadata. This reads the ten configured directories and produces:

- `.claude-plugin/marketplace.json` with one entry per category.
- `categories/*/.claude-plugin/plugin.json`, with metadata for each category. Definitions use the standard `agents/` directory at each plugin root so Claude Code discovers them directly.
- Category README files and the marked root README index.
- `tools/catalog.tsv`, containing category, plugin, name, routing description, source path, and SHA-256, separated by pipes.
- `docs/agent-count.svg`, counting category definitions only.

The standalone `agent-installer.md` is maintained separately. If renaming the repository, update `collection.json`, the shell installer default, the standalone agent installer, and the README download and badge URLs together. Validation checks identity presence; review all links after a rename.

The last-update badge uses GitHub's latest commit date for main. No scheduled timestamp commits are needed. The catalog and count badge change only when their source content changes. CI rejects stale generated files and never writes into pull-request branches.

## Verify a change

```sh
python3 tools/sync.py --check
python3 tools/validate.py
python3 -m unittest discover -s tests -v
bash -n install-agents.sh
shellcheck install-agents.sh
python3 tools/check_plugins.py
```

Python tests use the local fixture downloader to exercise standalone behavior without live network dependencies. The installer does not accept arbitrary HTTP base URLs; production downloads are restricted to GitHub raw HTTPS URLs.

`tools/check_plugins.py` runs the official validator, installs all ten local plugins with a temporary `CLAUDE_CONFIG_DIR`, and checks the component inventory for every expected agent. It does not alter your normal plugin configuration or invoke a model. This catches a valid manifest whose files are not discovered at runtime.

After publication, verify raw access by downloading the installer into a fresh temporary directory. Install one agent with `--standalone --ref COMMIT --target DIRECTORY`, verify the digest, then uninstall it using the same target. Use an actual commit hash from the published repository in place of COMMIT. Never use your real global agents directory for smoke tests.

## Release

1. Update `collection.json` version with a semantic version appropriate to the changes. Agent and plugin renames can break invocation names.
2. Regenerate metadata and complete all checks.
3. Merge into main, wait for CI, and verify the raw-download smoke test against that commit.
4. Create the version tag and release from the verified commit. Describe changed agent behavior and installer compatibility. Do not reuse a published version for different artifacts.

Users update marketplace plugins with Claude Code's plugin commands. Individual installations update by rerunning the installer; edited files require explicit force and are backed up. SHA-256 values detect mismatches between catalog and agents, not compromise of the repository itself. For repeatable installation, pin both the installer URL and `--ref` to the same commit.

## Sponsor listings

Accept product exposure only in the README sponsorship section. Label paid listings, record the approved sponsor name and URL accurately, and remove expired listings. Agent definitions and generated descriptions remain vendor-neutral. There are no initial sponsors.
