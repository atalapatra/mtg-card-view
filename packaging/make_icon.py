"""Generate packaging/graphmtg.ico (no dependencies): gold card-shaped nodes joined
by links on a dark rounded square, echoing the app's graph view.

    python packaging/make_icon.py
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

BG = (27, 30, 36)
GOLD = (212, 169, 55)
EDGE = (154, 163, 181)
NODES = [(0.27, 0.30, True), (0.70, 0.24, False), (0.76, 0.66, True), (0.32, 0.74, False), (0.52, 0.48, False)]
LINKS = [(0, 4), (1, 4), (2, 4), (3, 4), (0, 1), (2, 3), (1, 2)]


def render(size: int) -> bytes:
    """RGBA pixels, drawn with 4x4 supersampling."""
    ss = 4
    n = size * ss
    px = [[(0, 0, 0, 0)] * n for _ in range(n)]
    radius = 0.18 * n

    def inside_rounded(x: float, y: float) -> bool:
        m = 0.04 * n
        cx = min(max(x, m + radius), n - m - radius)
        cy = min(max(y, m + radius), n - m - radius)
        return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2 and m <= x <= n - m and m <= y <= n - m

    def seg_dist(x, y, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(x - (ax + t * dx), y - (ay + t * dy))

    pts = [(fx * n, fy * n, hub) for fx, fy, hub in NODES]
    lw = 0.035 * n
    for y in range(n):
        row = px[y]
        for x in range(n):
            if not inside_rounded(x + 0.5, y + 0.5):
                continue
            color = BG
            for a, b in LINKS:
                if seg_dist(x, y, pts[a][0], pts[a][1], pts[b][0], pts[b][1]) < lw / 2:
                    color = EDGE
            for cx, cy, hub in pts:
                w = (0.17 if hub else 0.12) * n
                h = w * 1.4
                if abs(x - cx) <= w / 2 and abs(y - cy) <= h / 2:
                    border = 0.025 * n
                    edge = abs(x - cx) > w / 2 - border or abs(y - cy) > h / 2 - border
                    color = GOLD if (hub or not edge) else (240, 236, 222)
                    if hub and not edge:
                        color = (60, 52, 30)
            row[x] = (*color, 255)

    out = bytearray()
    for y in range(size):
        for x in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    p = px[y * ss + sy][x * ss + sx]
                    for i in range(4):
                        acc[i] += p[i]
            a = acc[3] / (ss * ss)
            if a == 0:
                out += bytes(4)
            else:
                out += bytes([round(acc[0] / (acc[3] / 255)), round(acc[1] / (acc[3] / 255)),
                              round(acc[2] / (acc[3] / 255)), round(a)])
    return bytes(out)


def png(size: int, rgba: bytes) -> bytes:
    raw = b"".join(b"\x00" + rgba[y * size * 4:(y + 1) * size * 4] for y in range(size))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return header + entries + blobs


if __name__ == "__main__":
    sizes = [16, 32, 48, 64, 128, 256]
    images = [(s, png(s, render(s))) for s in sizes]
    out = Path(__file__).with_name("graphmtg.ico")
    out.write_bytes(ico(images))
    Path(__file__).with_name("graphmtg-256.png").write_bytes(images[-1][1])
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
