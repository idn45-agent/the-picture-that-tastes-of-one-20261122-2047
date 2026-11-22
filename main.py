#!/usr/bin/env python3
"""The picture that tastes of one ingredient.

A procedural still life of fresh strawberries on a white ceramic plate,
drawn from scratch with the Python standard library only. No image files,
no network, no third-party packages: every pixel is computed here, and
the PNG encoder below is written by hand (zlib + struct + CRC32).

Run:  python3 main.py [output-path]
Default output: /output/entry.png (1024x1024, deterministic).
"""

import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def smooth(a, b, x):
    """Smoothstep between a and b (requires a < b)."""
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    t = (x - a) / (b - a)
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    return a + (b - a) * t


def hash2(ix, iy, salt):
    """Deterministic integer hash -> float in [0, 1)."""
    h = (ix * 374761393 + iy * 668265263 + salt * 974634211) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFFFF) / 16777216.0


class Berry:
    """One strawberry: centre, size, lean and seed layout."""

    def __init__(self, cx, cy, w, h, lean, seed_salt):
        self.cx = cx
        self.cy = cy
        self.w = w
        self.h = h
        self.lean = lean
        self.salt = seed_salt
        # Seed positions in berry-local coordinates, fixed by hash.
        # Also bucket them into a coarse grid so each pixel only tests
        # the handful of seeds that could possibly cover it.
        self.seeds = []
        self.seed_cells = {}
        for i in range(36):
            su = hash2(i, 7, seed_salt)
            sv = hash2(i, 13, seed_salt)
            # Spread seeds over the berry body, denser near the middle.
            u = (su - 0.5) * 1.55
            v = sv * 0.92 - 0.28
            sr = 0.020 + 0.012 * hash2(i, 29, seed_salt)
            sx = cx + u * w * 0.5
            sy = cy + v * h * 0.5
            seed = (sx, sy, sr)
            self.seeds.append((u, v, sr))
            for gx in (int(sx // 28) - 1, int(sx // 28), int(sx // 28) + 1):
                for gy in (int(sy // 28) - 1, int(sy // 28), int(sy // 28) + 1):
                    self.seed_cells.setdefault((gx, gy), []).append(seed)

    def inside(self, x, y):
        """Shape value: < 0 inside the berry, > 0 outside."""
        dx = (x - self.cx) / (self.w * 0.5)
        dy = (y - self.cy) / (self.h * 0.5) + self.lean * dx * 0.35
        # The berry narrows toward its tip (dy -> +1).
        taper = 1.0 - 0.52 * smooth(-0.1, 1.0, dy)
        taper = max(taper, 0.28)
        qx = dx / taper
        # Slightly flattened shoulders at the top.
        r = math.sqrt(qx * qx + dy * dy)
        # Push the top edge out a touch for plump shoulders.
        r -= 0.06 * math.exp(-((dy + 0.55) * (dy + 0.55)) / 0.08)
        return r - 1.0


def berry_colour(berry, x, y, shape):
    """Fresh red flesh: bright lit top-left, deep red base, gloss."""
    dx = (x - berry.cx) / (berry.w * 0.5)
    dy = (y - berry.cy) / (berry.h * 0.5)
    # Light comes from the upper left.
    light = clamp(0.72 - 0.55 * dx - 0.45 * dy, 0.0, 1.0)
    # Vertical ripeness gradient: glowing red up top, wine red at tip.
    grad = clamp(0.5 - dy * 0.5, 0.0, 1.0)
    base_r = mix(168.0, 232.0, grad)
    base_g = mix(18.0, 74.0, grad)
    base_b = mix(26.0, 58.0, grad)
    # Warm light lift + cool shadow falloff.
    lift = 0.62 + 0.55 * light
    r = base_r * lift
    g = base_g * lift
    b = base_b * lift
    # Fine skin speckle: tiny darker pores, deterministic, cheap hash.
    n = ((x * 374761393 + y * 668265263 + 3 * 974634211) & 0xFFFFFFFF) % 1000 / 1000.0
    if n < 0.10:
        r *= 0.88
        g *= 0.85
        b *= 0.88
    # Soft specular gloss on the upper-left shoulder.
    gx = (x - (berry.cx - berry.w * 0.26)) / (berry.w * 0.30)
    gy = (y - (berry.cy - berry.h * 0.30)) / (berry.h * 0.26)
    gloss = math.exp(-(gx * gx + gy * gy) * 2.2)
    gloss *= smooth(0.15, 0.75, -shape)  # fade at the very edge
    r = mix(r, 255.0, gloss * 0.55)
    g = mix(g, 235.0, gloss * 0.45)
    b = mix(b, 225.0, gloss * 0.45)
    # Seeds: small golden ovals, slightly sunk into the skin.
    # Only the seeds bucketed near this pixel are tested.
    for (sx, sy, sr) in berry.seed_cells.get((int(x // 28), int(y // 28)), ()):
        ex = (x - sx) / (sr * berry.w * 0.5)
        ey = (y - sy) / (sr * berry.h * 0.5 * 1.5)
        d = ex * ex + ey * ey
        if d < 1.0:
            # Seed sits slightly sunk: darker rim, bright centre.
            centre = 1.0 - smooth(0.0, 0.55, d)
            r = mix(r, 226.0, 0.62)
            g = mix(g, 184.0, 0.62)
            b = mix(b, 96.0, 0.62)
            r *= 0.82 + 0.18 * centre
            g *= 0.82 + 0.18 * centre
            b *= 0.82 + 0.18 * centre
            break
    return (int(clamp(r, 0, 255)), int(clamp(g, 0, 255)),
            int(clamp(b, 0, 255)))


def leaf_colour(x, y, cx, cy, angle, length, width):
    """One pointed calyx leaf; returns None when outside the leaf."""
    dx = x - cx
    dy = y - cy
    ca = math.cos(angle)
    sa = math.sin(angle)
    # Rotate into leaf space: leaf points along +u.
    u = dx * ca + dy * sa
    v = -dx * sa + dy * ca
    if u < -6.0 or u > length:
        return None
    t = clamp(u / length, 0.0, 1.0)
    half = width * (1.0 - t * 0.92) * (0.35 + 0.65 * math.sin(math.pi * min(t * 1.15, 1.0)))
    if abs(v) > half:
        return None
    edge = 1.0 - smooth(half * 0.55, half, abs(v))
    shade = 0.72 + 0.45 * (1.0 - t) * edge
    vein = 0.9 + 0.1 * math.cos(v * 0.9)
    return (int(clamp(52 * shade * vein, 0, 255)),
            int(clamp(128 * shade * vein, 0, 255)),
            int(clamp(58 * shade * vein, 0, 255)))


def draw_leaf(px, cx, cy, angle, length, width):
    """Paint one leaf into the pixel buffer (in place)."""
    x0 = int(cx - length - width - 4)
    x1 = int(cx + length + width + 4)
    y0 = int(cy - length - width - 4)
    y1 = int(cy + length + width + 4)
    for yy in range(max(0, y0), min(H, y1 + 1)):
        for xx in range(max(0, x0), min(W, x1 + 1)):
            c = leaf_colour(xx, yy, cx, cy, angle, length, width)
            if c is not None:
                idx = (yy * W + xx) * 3
                px[idx] = c[0]
                px[idx + 1] = c[1]
                px[idx + 2] = c[2]


def render():
    px = bytearray(W * H * 3)
    # --- Warm cream backdrop, brighter toward the upper left. ---
    # Glow is separable: glow(x, y) = gx(x) * gy(y); precompute both.
    gx = [math.exp(-((x / (W - 1) - 0.30) ** 2) * 1.6) for x in range(W)]
    gy = [math.exp(-((y / (H - 1) - 0.22) ** 2) * 1.6) for y in range(H)]
    for y in range(H):
        fy = y / (H - 1)
        grow = gy[y]
        base_r = mix(233.0, 252.0, 1.0 - fy)
        base_g = mix(214.0, 240.0, 1.0 - fy)
        base_b = mix(188.0, 222.0, 1.0 - fy)
        row = y * W * 3
        for x in range(W):
            glow = gx[x] * grow
            # Faint linen grain, cheap deterministic pattern.
            grain = (((x * 31 + y * 17) % 11) - 5) * 0.5
            idx = row + x * 3
            px[idx] = int(clamp(base_r + 10.0 * glow + grain, 0, 255))
            px[idx + 1] = int(clamp(base_g + 8.0 * glow + grain, 0, 255))
            px[idx + 2] = int(clamp(base_b + 6.0 * glow + grain, 0, 255))

    # --- Soft contact shadow under the plate. ---
    pcx, pcy, prx, pry = 512.0, 668.0, 392.0, 158.0
    for y in range(int(pcy - pry - 30), int(pcy + pry + 34)):
        if y < 0 or y >= H:
            continue
        for x in range(int(pcx - prx - 30), int(pcx + prx + 34)):
            if x < 0 or x >= W:
                continue
            ex = (x - pcx) / (prx + 26.0)
            ey = (y - (pcy + 14.0)) / (pry + 22.0)
            d = math.sqrt(ex * ex + ey * ey)
            sh = (1.0 - smooth(0.72, 1.0, d)) * 0.34
            if sh > 0.0:
                idx = (y * W + x) * 3
                px[idx] = int(px[idx] * (1.0 - sh))
                px[idx + 1] = int(px[idx + 1] * (1.0 - sh))
                px[idx + 2] = int(px[idx + 2] * (1.0 - sh))

    # --- White ceramic plate: rim, well, inner glaze ring. ---
    for y in range(int(pcy - pry), int(pcy + pry) + 1):
        if y < 0 or y >= H:
            continue
        for x in range(int(pcx - prx), int(pcx + prx) + 1):
            if x < 0 or x >= W:
                continue
            ex = (x - pcx) / prx
            ey = (y - pcy) / pry
            d = math.sqrt(ex * ex + ey * ey)
            if d >= 1.0:
                continue
            idx = (y * W + x) * 3
            # Rim catches the light; the well dips slightly warmer.
            rim = smooth(0.86, 1.0, d)
            well = smooth(0.72, 0.86, d)
            r = mix(255.0, 243.0, well) + 6.0 * rim
            g = mix(253.0, 238.0, well) + 5.0 * rim
            b = mix(250.0, 228.0, well) + 4.0 * rim
            # Thin glaze ring near the rim.
            ring = math.exp(-((d - 0.80) ** 2) / 0.00045)
            r -= 14.0 * ring
            g -= 13.0 * ring
            b -= 11.0 * ring
            # Gentle top-light shading across the plate.
            shade = 0.94 + 0.06 * clamp(1.0 - (x / W + y / H), 0.0, 1.0)
            px[idx] = int(clamp(r * shade, 0, 255))
            px[idx + 1] = int(clamp(g * shade, 0, 255))
            px[idx + 2] = int(clamp(b * shade, 0, 255))

    # --- Strawberries: two behind, one hero in front. ---
    berries = [
        Berry(372.0, 560.0, 300.0, 330.0, -0.10, 101),
        Berry(662.0, 548.0, 296.0, 322.0, 0.12, 202),
        Berry(514.0, 618.0, 348.0, 372.0, 0.0, 303),
    ]
    # Berry shadows on the plate, painted before the berries.
    for b in berries:
        for y in range(int(b.cy + b.h * 0.18), int(b.cy + b.h * 0.62)):
            if y < 0 or y >= H:
                continue
            for x in range(int(b.cx - b.w * 0.62), int(b.cx + b.w * 0.62)):
                if x < 0 or x >= W:
                    continue
                ex = (x - (b.cx + 26.0)) / (b.w * 0.58)
                ey = (y - (b.cy + b.h * 0.42)) / (b.h * 0.20)
                d = math.sqrt(ex * ex + ey * ey)
                sh = (1.0 - smooth(0.55, 1.0, d)) * 0.22
                if sh > 0.0:
                    idx = (y * W + x) * 3
                    px[idx] = int(px[idx] * (1.0 - sh))
                    px[idx + 1] = int(px[idx + 1] * (1.0 - sh))
                    px[idx + 2] = int(px[idx + 2] * (1.0 - sh))
    # Berry bodies, back to front.
    for b in berries:
        x0 = int(b.cx - b.w * 0.55)
        x1 = int(b.cx + b.w * 0.55)
        y0 = int(b.cy - b.h * 0.55)
        y1 = int(b.cy + b.h * 0.55)
        for y in range(max(0, y0), min(H, y1 + 1)):
            for x in range(max(0, x0), min(W, x1 + 1)):
                s = b.inside(x, y)
                if s >= 0.0:
                    continue
                c = berry_colour(b, x, y, s)
                idx = (y * W + x) * 3
                # Feather the rim by one pixel for a clean edge.
                a = 1.0 - smooth(-0.045, 0.0, s)
                px[idx] = int(mix(px[idx], c[0], a))
                px[idx + 1] = int(mix(px[idx + 1], c[1], a))
                px[idx + 2] = int(mix(px[idx + 2], c[2], a))

    # --- Green calyx crowns on each berry. ---
    for b in berries:
        top_y = b.cy - b.h * 0.46
        for k in range(5):
            ang = -math.pi / 2 + (k - 2) * 0.52 + b.lean * 0.3
            draw_leaf(px, b.cx, top_y + 6.0, ang,
                      b.w * 0.30, b.w * 0.085)
        # Short slim stem, tucked between the leaves.
        for yy in range(int(top_y - 16), int(top_y + 4)):
            for xx in range(int(b.cx - 3), int(b.cx + 4)):
                if 0 <= xx < W and 0 <= yy < H:
                    idx = (yy * W + xx) * 3
                    px[idx] = 74
                    px[idx + 1] = 112
                    px[idx + 2] = 52

    # --- Warm vignette to hold the eye on the plate. ---
    # Squared distance keeps this pass cheap (no sqrt per pixel).
    for y in range(H):
        ey = (y - 500.0) / 640.0
        ey2 = ey * ey
        row = y * W * 3
        for x in range(W):
            ex = (x - 512.0) / 640.0
            vg = smooth(0.85, 2.10, ex * ex + ey2) * 0.10
            if vg > 0.0:
                idx = row + x * 3
                px[idx] = int(px[idx] * (1.0 - vg))
                px[idx + 1] = int(px[idx + 1] * (1.0 - vg))
                px[idx + 2] = int(px[idx + 2] * (1.0 - vg))
    return px


def write_png(path, px):
    """Minimal hand-rolled PNG writer: RGB, filter 0, zlib level 6."""
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(kind, data):
        c = struct.pack(">I", len(data)) + kind + data
        c += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main(argv):
    out = argv[1] if len(argv) > 1 else "/output/entry.png"
    px = render()
    size = write_png(out, px)
    print(f"wrote {out} ({W}x{H}, {size} bytes)")


if __name__ == "__main__":
    main(sys.argv)
