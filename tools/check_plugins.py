#!/usr/bin/env python3
"""Check actual Claude Code plugin discovery in an isolated configuration."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

from sync import ROOT, inventory


def main() -> int:
    if not shutil.which('claude'):
        raise SystemExit('Claude Code CLI is required for component discovery checks.')
    config, records = inventory()
    with tempfile.TemporaryDirectory(prefix='subagent-plugin-check-') as temporary:
        env = {**os.environ, 'CLAUDE_CONFIG_DIR': temporary}

        def run(*args: str) -> str:
            result = subprocess.run(['claude', *args], cwd=temporary, env=env,
                                    capture_output=True, text=True, timeout=60)
            if result.returncode:
                raise RuntimeError(f'claude {" ".join(args)} failed:\n{result.stdout}\n{result.stderr}')
            return result.stdout

        run('plugin', 'validate', str(ROOT))
        run('plugin', 'marketplace', 'add', str(ROOT))
        for category in config['categories']:
            plugin = category['plugin']
            folder = ROOT / 'categories' / category['directory']
            expected = [r['name'] for r in records if r['plugin'] == plugin]
            run('plugin', 'validate', str(folder))
            run('plugin', 'install', f'{plugin}@{config["marketplace"]}')
            details = run('plugin', 'details', plugin)
            count = re.search(r'Agents \((\d+)\)', details)
            if not count or int(count.group(1)) != len(expected):
                raise RuntimeError(f'{plugin}: expected {len(expected)} loaded agents:\n{details}')
            missing = [name for name in expected if not re.search(rf'(?<![\w-]){re.escape(name)}(?![\w-])', details)]
            if missing:
                raise RuntimeError(f'{plugin}: missing agent names in inventory: {missing}')
            print(f'{plugin}: {len(expected)} agents discovered')
    print('Marketplace and all 10 plugins validated and installed in an isolated configuration.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
