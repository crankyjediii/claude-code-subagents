# Contributing

An agent belongs here when it solves a specific development task with instructions a Claude Code user can apply in a real repository. Describe when to invoke it, what to inspect, how to perform the task, how to verify results, and which failure modes require attention.

Use vendor-neutral criteria. A language or framework specialist may discuss its actual ecosystem. An agent must not primarily promote a company, service, personal project, affiliate link, or sponsor. Sponsor listings belong only in the README sponsorship section.

## Add or improve an agent

1. Look for an existing specialist with the same responsibility. Improve that file when the proposed agent would duplicate its trigger and workflow.
2. Put the definition in the matching `categories/NN-category/agents/` directory with a lowercase hyphenated filename. Agent names are unique across the collection and match filenames.
3. Use this repository's frontmatter subset: `name`, a JSON-quoted `description`, a comma-separated `tools` scalar, and `model: inherit`. JSON-quoted strings are valid YAML and keep maintenance dependency-free. The description should be 20–240 characters and explain the routing trigger. Supported tools are Read, Glob, Grep, Bash, Write, Edit, Agent, WebFetch, and WebSearch; include only what the task requires.
4. Write a standalone body of at least 160 words with `## Approach`, `## Task boundaries`, and `## Completion`. The length check is a floor, not a reason to add filler. Give concrete task-specific checks. Do not refer to a private instruction file, require another agent implicitly, embed credentials, or instruct permission bypasses.
5. Run `python3 tools/sync.py`. Do not edit generated catalog entries, category indexes, count badges, or manifests by hand.
6. Run the checks below and explain the behavior or coverage your change adds in the pull request.

```sh
python3 tools/validate.py
python3 -m unittest discover -s tests -v
shellcheck install-agents.sh
claude plugin validate .
```

Changes to installer behavior need regression tests with temporary homes and targets. Do not write tests into a contributor's real `.claude/` directory. Test network behavior through the fixture downloader and check the real raw-download path after publication.

The ten categories and their plugin names are defined in `collection.json`. Changing numbering, folders, or plugin names is a compatibility change. Coordinate all references and migration instructions. `voltagent-meta` must keep its documented dependency on available specialists and a fallback for unavailable delegation.

Keep descriptions specific and short. Do not claim that a prompt guarantees security, correctness, or test execution. Distinguish checks actually run from suggested checks. Use real sources for external factual claims.

Contributions are provided under the repository's MIT license. Do not submit material you cannot license under those terms.
