#!/usr/bin/env python3
"""Fresh strawberries on a plate -- procedural still life.

One ingredient: fresh strawberries. Pure Python 3.13 stdlib, no network,
no external assets. Writes one 1024x1024 PNG to /output/entry.png by
default, or to argv[1] when given. Fully deterministic.
"""
import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


class Canvas:
    def __init__(self):
        self.px = bytearray(W * H * 3)

    def set(self, x, y, r, g, b):
        if 0 <= x < W and 0 <= y < H:
            i = (y * W + x) * 3
            self.px[i] = int(clamp(r, 0, 255))
            self.px[i + 1] = int(clamp(g, 0, 255))
            self.px[i + 2] = int(clamp(b, 0, 255))

    def get(self, x, y):
        i = (y * W + x) * 3
        return (self.px[i], self.px[i + 1], self.px[i + 2])

    def blend(self, x, y, r, g, b, a):
        """Blend colour (r,g,b) over pixel (x,y) with alpha a in [0,1]."""
        if 0 <= x < W and 0 <= y < H and a > 0:
            i = (y * W + x) * 3
            px = self.px
            px[i] = int(clamp(px[i] + (r - px[i]) * a, 0, 255))
            px[i + 1] = int(clamp(px[i + 1] + (g - px[i + 1]) * a, 0, 255))
            px[i + 2] = int(clamp(px[i + 2] + (b - px[i + 2]) * a, 0, 255))

    def disc(self, cx, cy, rad, r, g, b, a=1.0):
        """Filled disc, centre (cx,cy), radius rad (float)."""
        if rad <= 0:
            return
        x0 = max(0, int(cx - rad) - 1)
        x1 = min(W - 1, int(cx + rad) + 1)
        y0 = max(0, int(cy - rad) - 1)
        y1 = min(H - 1, int(cy + rad) + 1)
        r2 = rad * rad
        for y in range(y0, y1 + 1):
            dy = y - cy
            for x in range(x0, x1 + 1):
                dx = x - cx
                if dx * dx + dy * dy <= r2:
                    if a >= 1.0:
                        self.set(x, y, r, g, b)
                    else:
                        self.blend(x, y, r, g, b, a)


def background(cv):
    # Deterministic linen tile, 64x64 values in -7..7. Per-cell LCG hash
    # (uncorrelated across cells) so the grain reads as fine linen,
    # not diagonal bands.
    tile = []
    for ty in range(64):
        row = []
        for tx in range(64):
            seed = tx * 57 + ty * 131 + 17
            n = ((seed * 9301 + 49297) % 233280) / 233280.0
            row.append(int(n * 15) - 7)
        tile.append(row)
    top = (255, 246, 228)
    bot = (243, 212, 176)
    px = cv.px
    for y in range(H):
        t = y / (H - 1)
        br = lerp(top[0], bot[0], t)
        bg = lerp(top[1], bot[1], t)
        bb = lerp(top[2], bot[2], t)
        ty = y & 63
        trow = tile[ty]
        # Warm glow from top-left, precomputed per-row falloff.
        dy = y - 120
        ny = (y - 512) / 512.0
        row = y * W * 3
        for x in range(W):
            dx = x - 180
            d2 = dx * dx + dy * dy
            glow = 0.0
            if d2 < 810000:
                glow = 1.0 - d2 / 810000.0
            n = trow[x & 63]
            nx = (x - 512) / 512.0
            vig = 1.0 - 0.05 * min(1.0, nx * nx + ny * ny)
            r = (br + 20 * glow + n) * vig
            g = (bg + 14 * glow + n) * vig
            b = (bb + 6 * glow + n) * vig
            i = row + x * 3
            px[i] = int(clamp(r, 0, 255))
            px[i + 1] = int(clamp(g, 0, 255))
            px[i + 2] = int(clamp(b, 0, 255))


def ellipse_shadow(cv, cx, cy, rx, ry, strength):
    x0 = max(0, int(cx - rx))
    x1 = min(W - 1, int(cx + rx))
    y0 = max(0, int(cy - ry))
    y1 = min(H - 1, int(cy + ry))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rx
            q = dx * dx + dy * dy
            if q <= 1.0:
                cv.blend(x, y, 74, 52, 38, strength * (1.0 - q * 0.55))


def plate(cv):
    cx, cy, rx, ry = 512, 668, 402, 168
    ellipse_shadow(cv, cx, cy + 26, rx + 6, 34, 0.20)
    x0, x1 = cx - rx - 1, cx + rx + 1
    y0, y1 = cy - ry - 1, cy + ry + 1
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rx
            q = dx * dx + dy * dy
            if q > 1.0:
                continue
            # Light from top-left.
            light = clamp(0.72 + 0.28 * (-0.7 * dx - 0.7 * dy), 0.0, 1.0)
            r = 250 + 4 * light
            g = 249 + 4 * light
            b = 246 + 4 * light
            if q > 0.78:  # rim band, slightly darker
                f = (q - 0.78) / 0.22
                r = lerp(r, 226, f * 0.7)
                g = lerp(g, 224, f * 0.7)
                b = lerp(b, 218, f * 0.7)
            elif q < 0.46:  # well, slightly warmer / darker
                f = 1.0 - q / 0.46
                r = lerp(r, 240, f * 0.55)
                g = lerp(g, 236, f * 0.55)
                b = lerp(b, 226, f * 0.55)
            if 0.965 < q <= 1.0:  # thin rim line
                r, g, b = 198, 194, 186
            cv.set(x, y, r, g, b)


def berry_halfwidth(v):
    """Half-width factor at normalised height v in [0,1], top to tip."""
    hw = (1.0 - v ** 3.0) ** 0.42 * (0.94 + 0.06 * math.cos(math.pi * v))
    if v < 0.18:
        # Narrower at the very top so the shoulder rounds over instead
        # of ending in a flat, square-cut top edge.
        hw *= 0.25 + 0.75 * math.sin(math.pi / 2 * v / 0.18)
    hw *= 1.0 - 0.12 * v  # stronger taper toward the tip
    return hw


def berry_colour(u, v, hw):
    # Light from top-left.
    L = clamp(0.55 + 0.45 * (-0.8 * u - 0.6 * (v - 0.5)), 0.0, 1.0)
    dark = (138, 12, 10)
    mid = (205, 28, 18)
    bright = (242, 74, 40)
    if L < 0.55:
        c = mix(dark, mid, L / 0.55)
    else:
        c = mix(mid, bright, (L - 0.55) / 0.45)
    tip = 1.0 - 0.16 * v * v
    ridge = 1.0 + 0.035 * math.sin(9 * u + 3 * v)
    r, g, b = c[0] * tip * ridge, c[1] * tip * ridge, c[2] * tip * ridge
    # Soft white gloss, upper-left of the berry: kept small and tight
    # so it reads as a highlight, not a pale wash across the berry.
    du = (u + 0.42) / 0.22
    dv = (v - 0.28) / 0.16
    d2 = du * du + dv * dv
    if d2 < 1.0:
        a = (1.0 - d2) * 0.35
        r = lerp(r, 255, a)
        g = lerp(g, 235, a)
        b = lerp(b, 220, a)
    # Warm rim light on the right edge.
    if u > 0 and hw > 0 and abs(u) > hw * 0.80:
        a = ((abs(u) / hw - 0.80) / 0.20) * 0.35
        r = lerp(r, 255, a)
        g = lerp(g, 176, a)
        b = lerp(b, 118, a)
    return r, g, b


def draw_leaf(cv, apex, base_ang, spread_deg, length, max_hw):
    """One lens-shaped calyx leaf from the apex, spread from straight up."""
    ang = math.radians(base_ang + spread_deg)
    # Direction: up is -y; spread rotates around it.
    dx = math.sin(ang)
    dy = -math.cos(ang)
    steps = 24
    pts = []
    for s in range(steps + 1):
        t = s / steps
        hw = max_hw * math.sin(math.pi * (t ** 0.85))
        px = apex[0] + dx * t * length
        py = apex[1] + dy * t * length
        pts.append((px, py, hw, t))
        if hw > 0.4:
            cv.disc(px, py, hw, *mix((44, 104, 26), (78, 156, 42), t))
    # Centre vein, darker.
    for s in range(4, steps - 2):
        px, py, hw, t = pts[s]
        cv.disc(px, py, 1.1, 38, 88, 22)


def draw_stem(cv, apex, base_ang):
    ang = math.radians(base_ang)
    dx = math.sin(ang)
    dy = -math.cos(ang)
    for s in range(0, 27, 3):
        cv.disc(apex[0] + dx * s, apex[1] + dy * s, 2.6, 101, 78, 43)


def draw_droplet(cv, x, y, rad=5.0):
    cv.disc(x, y, rad, 255, 255, 255, 0.30)
    cv.disc(x - rad * 0.25, y - rad * 0.3, rad * 0.42, 255, 255, 255, 0.85)


def berry(cv, cx, cy, w, h, angle_deg, droplets):
    """Draw one strawberry. Returns nothing; draws shadow, body, seeds,
    calyx and stem. Local u in [-1,1] across, v in [0,1] top to tip."""
    ang = math.radians(angle_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    hw2, hh2 = w / 2.0, h / 2.0
    # Soft shadow on the plate, just under the berry.
    ellipse_shadow(cv, cx, cy + hh2 * 0.82, w * 0.42, h * 0.085, 0.22)

    # Bounding box of the rotated berry.
    ex = hw2 * abs(ca) + hh2 * abs(sa)
    ey = hw2 * abs(sa) + hh2 * abs(ca)
    x0 = max(0, int(cx - ex) - 1)
    x1 = min(W - 1, int(cx + ex) + 1)
    y0 = max(0, int(cy - ey) - 1)
    y1 = min(H - 1, int(cy + ey) + 1)
    for y in range(y0, y1 + 1):
        dy = y - cy
        for x in range(x0, x1 + 1):
            dx = x - cx
            # Inverse rotation into berry-local coords.
            lx = dx * ca + dy * sa
            ly = -dx * sa + dy * ca
            u = lx / hw2
            v = (ly + hh2) / h
            if v < 0.0 or v > 1.0 or u < -1.0 or u > 1.0:
                continue
            hw = berry_halfwidth(v)
            if abs(u) > hw:
                continue
            r, g, b = berry_colour(u, v, hw)
            cv.set(x, y, r, g, b)

    # Apex in canvas coords (local (0, -hh2) rotated).
    ax = cx + (0 * ca - (-hh2) * sa)
    ay = cy + (0 * sa + (-hh2) * ca)
    apex = (ax, ay)

    # Seeds: rows v, spacing 0.30 in u, alternate rows shifted half a step.
    seed_rows = [0.20, 0.28, 0.40, 0.52, 0.64, 0.76, 0.86, 0.93]
    srx, sry = 0.0135 * w, 0.017 * h
    for ri, v in enumerate(seed_rows):
        hw = berry_halfwidth(v)
        off = 0.15 if ri % 2 else 0.0
        u = -0.8 * hw + off
        while u <= 0.8 * hw:
            if abs(u) <= 0.8 * hw:
                # Seed centre, local -> canvas.
                lx = u * hw2
                ly = (v - 0.5) * h
                sx = cx + lx * ca - ly * sa
                sy = cy + lx * sa + ly * ca
                # Small dark shadow offset down-right, then pale seed.
                cv.disc(sx + 1.6, sy + 1.8, srx, 120, 20, 12, 0.55)
                # Ellipse: draw as a disc squashed vertically via two
                # passes is overkill; a small disc reads as a seed at
                # this scale, stretched by drawing a vertical pair.
                cv.disc(sx, sy, srx, 255, 233, 158)
                cv.disc(sx, sy - sry * 0.35, srx * 0.7, 255, 233, 158)
                cv.disc(sx, sy + sry * 0.35, srx * 0.7, 255, 233, 158)
            u += 0.30

    # Calyx: 5 lens leaves fanning from the apex. Leaf bases sink
    # ~14 px into the berry so the calyx sits on the fruit instead of
    # floating above it; shorter leaves read less spiky.
    sink = 14.0
    sang = math.radians(angle_deg)
    base = (apex[0] - math.sin(sang) * sink,
            apex[1] + math.cos(sang) * sink)
    scales = [0.78, 0.92, 1.0, 0.92, 0.78]
    for i, spread in enumerate([-68, -34, 0, 34, 68]):
        draw_leaf(cv, base, angle_deg, spread,
                  scales[i] * 0.27 * w, 0.035 * w)
    draw_stem(cv, apex, angle_deg)

    # Water droplets.
    for (du, dv, rad) in droplets:
        lx = du * hw2
        ly = (dv - 0.5) * h
        x = cx + lx * ca - ly * sa
        y = cy + lx * sa + ly * ca
        draw_droplet(cv, x, y, rad)


def write_png(path, cv):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += cv.px[y * W * 3:(y + 1) * W * 3]
    data = zlib.compress(bytes(raw), 9)

    def chunk(kind, payload):
        c = struct.pack(">I", len(payload)) + kind + payload
        c += struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", data) + chunk(b"IEND", b""))
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    cv = Canvas()
    background(cv)
    plate(cv)
    # Back berries first, hero last.
    berry(cv, 300, 430, 240, 300, -14,
          [(-0.30, 0.45, 4.0), (0.25, 0.60, 4.0)])
    berry(cv, 716, 425, 232, 292, 12,
          [(0.30, 0.42, 4.0), (-0.20, 0.62, 4.0)])
    berry(cv, 512, 620, 330, 400, -3,
          [(-0.45, 0.35, 5.0), (0.10, 0.50, 5.0), (-0.15, 0.65, 4.5),
           (0.35, 0.42, 4.5), (0.00, 0.78, 4.0)])
    n = write_png(out, cv)
    print(f"wrote {out} ({n} bytes)")


if __name__ == "__main__":
    main()
