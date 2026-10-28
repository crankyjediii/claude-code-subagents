"""Small deterministic SVG and PNG assets, generated without image dependencies."""
from __future__ import annotations

import struct
import zlib

COLORS = ('#c8ec9a', '#a8caf5', '#ebbc88', '#eaa6b1', '#b8b0ec',
          '#99d8cd', '#d7cb83', '#e5b8d9', '#a6d2b1', '#a6cbd8')


def icon_png(accent: str) -> bytes:
    size = 512
    background = (20, 31, 28)
    color = tuple(bytes.fromhex(accent[1:]))
    pixels = bytearray(bytes(background) * size * size)

    def rect(x: int, y: int, width: int, height: int, rgb: tuple[int, ...]) -> None:
        row = bytes(rgb) * width
        for current in range(y, y + height):
            offset = (current * size + x) * 3
            pixels[offset:offset + width * 3] = row

    def line(x1: int, y1: int, x2: int, y2: int) -> None:
        steps = max(abs(x2 - x1), abs(y2 - y1))
        for step in range(steps + 1):
            x = round(x1 + (x2 - x1) * step / steps)
            y = round(y1 + (y2 - y1) * step / steps)
            rect(x - 6, y - 6, 12, 12, color)

    line(194, 170, 110, 256)
    line(110, 256, 194, 342)
    line(280, 170, 364, 256)
    line(364, 256, 280, 342)
    line(270, 122, 225, 390)
    for x, y in ((68, 68), (412, 68), (68, 412), (412, 412)):
        rect(x, y, 32, 32, color)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))

    rows = b''.join(b'\x00' + pixels[y * size * 3:(y + 1) * size * 3] for y in range(size))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', size, size, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def banner_svg(count: int, category_count: int) -> str:
    labels = ('CORE', 'LANGUAGES', 'INFRA', 'QUALITY', 'DATA + AI',
              'DEV TOOLS', 'SYSTEMS', 'PRODUCT', 'ORCHESTRATION', 'RESEARCH')
    tiles = []
    for index, label in enumerate(labels):
        x, y = 1000 + (index % 2) * 238, 88 + (index // 2) * 68
        tiles.append(f'<rect x="{x}" y="{y}" width="216" height="52" rx="8" fill="#1c2b26" stroke="#3b5146"/>'
                     f'<circle cx="{x + 24}" cy="{y + 26}" r="5" fill="{COLORS[index]}"/>'
                     f'<text x="{x + 44}" y="{y + 31}" fill="#e7eadf" font-size="14" letter-spacing="1">{label}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1560 540" width="1560" height="540" role="img" aria-labelledby="title desc">
<title id="title">Claude Code Subagents</title>
<desc id="desc">A specialist for the next task. {count} development agents across {category_count} categories.</desc>
<rect width="1560" height="540" rx="20" fill="#141f1c"/>
<path d="M930 56V444M64 454H1496" stroke="#3b5146"/>
<g font-family="Arial,Helvetica,sans-serif">
<text x="72" y="89" fill="#c8ec9a" font-size="17" letter-spacing="3.2">CLAUDE CODE SUBAGENTS</text>
<g font-family="Georgia,Times,serif" font-size="85" fill="#f3f1e7">
<text x="65" y="214">A specialist for</text><text x="65" y="310">the next task.</text>
</g>
<text x="72" y="381" fill="#a7b6ac" font-size="23">Development agents with explicit scope and verification.</text>
{''.join(tiles)}
<g font-size="16" letter-spacing="1.2">
<text x="72" y="501" fill="#c8ec9a">{count} AGENTS</text>
<text x="296" y="501" fill="#c8ec9a">{category_count} CATEGORIES</text>
<text x="561" y="501" fill="#a7b6ac">MODEL: INHERIT</text>
<text x="1296" y="501" fill="#a7b6ac">MIT LICENSE</text>
</g></g></svg>
'''


def assets(count: int, categories: list[dict]) -> dict[str, str | bytes]:
    result: dict[str, str | bytes] = {'docs/assets/banner.svg': banner_svg(count, len(categories))}
    for index, category in enumerate(categories):
        result[f"categories/{category['directory']}/.claude-plugin/icon.png"] = icon_png(COLORS[index])
    return result
