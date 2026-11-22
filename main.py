#!/usr/bin/env python3
"""The picture that tastes of one ingredient.

A program that draws one picture of food: three fresh strawberries on a
white ceramic plate, warm morning light, drawn procedurally with plain
Python 3.13 stdlib only (no PIL, no network). Writes one PNG to
/output/entry.png (or to the path given as argv[1]).

The picture is a single ingredient - strawberry - rendered as a soft
painterly still life: glossy red berries with pale seeds, green calyx
leaves, water droplets, a ceramic plate and a warm cream background.
"""

import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024

# --------------------------------------------------------------------------
# Canvas
# --------------------------------------------------------------------------

buf = bytearray(W * H * 3)


def put(x, y, r, g, b):
    i = (y * W + x) * 3
    buf[i] = r
    buf[i + 1] = g
    buf[i + 2] = b


def blend(x, y, r, g, b, a):
    """Blend colour (r,g,b) over the pixel at (x,y) with coverage a in [0,1]."""
    if a <= 0.0:
        return
    if a >= 1.0:
        put(x, y, r, g, b)
        return
    i = (y * W + x) * 3
    ia = 1.0 - a
    buf[i] = int(buf[i] * ia + r * a + 0.5)
    buf[i + 1] = int(buf[i + 1] * ia + g * a + 0.5)
    buf[i + 2] = int(buf[i + 2] * ia + b * a + 0.5)


def clamp255(v):
    if v < 0:
        return 0
    if v > 255:
        return 255
    return int(v + 0.5)


# Deterministic linen-noise tile (64x64, values -7..7), tiled over the image.
_noise = []
_seed = 1234567
for _ in range(64 * 64):
    _seed = (_seed * 1103515245 + 12345) & 0x7FFFFFFF
    _noise.append((_seed % 15) - 7)

# Separable vignette factors: darken up to ~9% toward the corners.
_vx = [1.0 - 0.055 * ((x - 512.0) / 512.0) ** 2 for x in range(W)]
_vy = [1.0 - 0.055 * ((y - 512.0) / 512.0) ** 2 for y in range(H)]


def draw_background():
    # Vertical gradient: warm cream at the top, soft sand at the bottom,
    # plus a warm glow from the top-left corner.
    for y in range(H):
        t = y / (H - 1)
        # Base gradient.
        br = 255.0 - 12.0 * t
        bg = 246.0 - 34.0 * t
        bb = 228.0 - 52.0 * t
        # Top-left glow.
        glow = 10.0 * max(0.0, 1.0 - y / 700.0)
        vy = _vy[y]
        row = y * W * 3
        for x in range(W):
            n = _noise[(x & 63) + (y & 63) * 64]
            gx = max(0.0, 1.0 - x / 700.0)
            g = glow * (0.5 + 0.5 * gx)
            v = _vx[x] * vy
            buf[row + x * 3] = clamp255((br + g + n) * v)
            buf[row + x * 3 + 1] = clamp255((bg + g * 0.9 + n) * v)
            buf[row + x * 3 + 2] = clamp255((bb + g * 0.7 + n) * v)


def soft_ellipse(cx, cy, rx, ry, r, g, b, a):
    """Filled ellipse with a soft (2-layer) edge, blended over the canvas."""
    x0 = max(0, int(cx - rx - 3))
    x1 = min(W - 1, int(cx + rx + 3))
    y0 = max(0, int(cy - ry - 3))
    y1 = min(H - 1, int(cy + ry + 3))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        dy2 = dy * dy
        if dy2 >= 1.21:
            continue
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rx
            d2 = dx * dx + dy2
            if d2 >= 1.0:
                continue
            # Smooth falloff in the outer 18% of the radius.
            edge = (1.0 - d2) / 0.18
            cov = 1.0 if edge >= 1.0 else edge
            blend(x, y, r, g, b, a * cov)


# --------------------------------------------------------------------------
# Plate
# --------------------------------------------------------------------------

def draw_plate():
    # Soft shadow of the plate on the table.
    soft_ellipse(516, 792, 428, 52, 96, 70, 40, 0.20)
    soft_ellipse(514, 786, 410, 46, 96, 70, 40, 0.16)
    # Plate body: big shallow ellipse, brighter toward the top-left.
    cx, cy, rx, ry = 512.0, 668.0, 402.0, 168.0
    x0 = max(0, int(cx - rx))
    x1 = min(W - 1, int(cx + rx))
    y0 = max(0, int(cy - ry))
    y1 = min(H - 1, int(cy + ry))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        dy2 = dy * dy
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rx
            d2 = dx * dx + dy2
            if d2 >= 1.0:
                continue
            light = 0.5 + 0.5 * (-dx * 0.6 - dy * 0.5)
            shade = 0.94 + 0.06 * light
            # Rim ring: slightly darker band near the edge.
            rim = 1.0
            if d2 > 0.82:
                rim = 0.965
            # Inner well: a touch warmer/darker inside the rim.
            well = 1.0
            if d2 < 0.62:
                well = 0.985
            v = shade * rim * well
            put(x, y, clamp255(253 * v), clamp255(250 * v), clamp255(244 * v))
    # Thin rim line.
    for k in range(360):
        ang = math.radians(k)
        ex = int(cx + (rx - 4) * math.cos(ang))
        ey = int(cy + (ry - 4) * math.sin(ang))
        if 0 <= ex < W and 0 <= ey < H:
            blend(ex, ey, 214, 205, 190, 0.55)


# --------------------------------------------------------------------------
# Strawberry
# --------------------------------------------------------------------------

def berry_half_width(v):
    """Half-width of the berry silhouette at height v (0 top, 1 tip).

    Plump shoulders, a gentle taper and a softly rounded tip. The top
    rounds in toward the stem (the calyx covers the middle of it).
    """
    base = (1.0 - v ** 2.6) ** 0.42 * (0.94 + 0.06 * math.cos(math.pi * v))
    if v < 0.18:
        base *= 0.72 + 0.28 * math.sin((math.pi / 2.0) * (v / 0.18))
    return base


def draw_berry(cx, cy, w, h, tilt_deg, seed_rows=True):
    """Draw one strawberry centred at (cx, cy), bounding box w x h."""
    tilt = math.radians(tilt_deg)
    ct = math.cos(tilt)
    st = math.sin(tilt)
    hw2 = w / 2.0
    hh2 = h / 2.0
    top_y = cy - hh2

    # --- soft shadow of the berry on the plate ---------------------------
    soft_ellipse(cx + 14, cy + hh2 * 0.86, w * 0.42, h * 0.10, 90, 60, 35, 0.20)
    soft_ellipse(cx + 10, cy + hh2 * 0.82, w * 0.34, h * 0.075, 90, 60, 35, 0.16)

    # --- body ------------------------------------------------------------
    x0 = max(0, int(cx - hw2 - 4))
    x1 = min(W - 1, int(cx + hw2 + 4))
    y0 = max(0, int(cy - hh2 - 4))
    y1 = min(H - 1, int(cy + hh2 + 4))
    for y in range(y0, y1 + 1):
        dy = y - cy
        for x in range(x0, x1 + 1):
            dx = x - cx
            # Rotate into the berry's local frame.
            lx = dx * ct + dy * st
            ly = -dx * st + dy * ct
            u = lx / hw2
            v = ly / h + 0.5
            if v < 0.0 or v > 1.0:
                continue
            hw = berry_half_width(v)
            au = abs(u)
            d = hw - au
            if d <= 0.0:
                continue
            # Light from the top-left.
            L = 0.55 + 0.45 * (-0.8 * u - 0.6 * (v - 0.5))
            if L < 0.0:
                L = 0.0
            elif L > 1.0:
                L = 1.0
            # Two-segment red ramp: deep -> mid -> bright.
            if L < 0.55:
                t = L / 0.55
                r = 138.0 + (205.0 - 138.0) * t
                g = 12.0 + (28.0 - 12.0) * t
                b = 10.0 + (18.0 - 10.0) * t
            else:
                t = (L - 0.55) / 0.45
                r = 205.0 + (242.0 - 205.0) * t
                g = 28.0 + (74.0 - 28.0) * t
                b = 18.0 + (40.0 - 18.0) * t
            # Darken toward the tip, faint vertical ridges.
            depth = 1.0 - 0.16 * v * v
            ridge = 1.0 + 0.035 * math.sin(u * 9.0 + v * 3.0)
            r *= depth * ridge
            g *= depth * ridge
            b *= depth * ridge
            # Glossy highlights (soft white blobs, upper-left).
            hx = u + 0.42
            hy = (v - 0.30) * 1.15
            hl = math.exp(-(hx * hx + hy * hy) / 0.10) * 0.34
            hx2 = u + 0.58
            hy2 = (v - 0.16) * 1.4
            hl += math.exp(-(hx2 * hx2 + hy2 * hy2) / 0.03) * 0.42
            # Warm rim light on the right edge.
            rim = math.exp(-((u - 0.88) ** 2) / 0.02) * 0.22
            r = r + (255.0 - r) * hl + (255.0 - r) * rim * 0.5
            g = g + (255.0 - g) * hl + (120.0 - g) * rim * 0.5
            b = b + (255.0 - b) * hl + (60.0 - b) * rim * 0.5
            # Anti-aliased edge.
            if d < 0.02:
                blend(x, y, clamp255(r), clamp255(g), clamp255(b), d / 0.02)
            else:
                put(x, y, clamp255(r), clamp255(g), clamp255(b))

    # --- stem ------------------------------------------------------------
    stem_top_x = cx - math.sin(tilt) * hh2 * 0.98
    stem_top_y = top_y - 26
    stem_bot_x = cx
    stem_bot_y = top_y + 4
    steps = 24
    for s in range(steps + 1):
        t = s / steps
        sx = stem_bot_x + (stem_top_x - stem_bot_x) * t
        sy = stem_bot_y + (stem_top_y - stem_bot_y) * t
        rad = 5.0 - 2.0 * t
        soft_ellipse(sx, sy, rad, rad, 96, 118, 52, 0.9)

    # --- calyx leaves ------------------------------------------------------
    # Five pointed leaves fanning from the top of the berry.
    leaf_len = w * 0.32
    leaf_wid = w * 0.070
    leaf_scale = [0.78, 0.92, 1.0, 0.92, 0.78]
    base_x = cx
    base_y = top_y + 8
    for k in range(5):
        spread = math.radians(-68 + k * 34)
        llen = leaf_len * leaf_scale[k]
        # Leaf direction in canvas space (up, fanned, then tilted).
        ang = tilt + spread
        dxn = math.sin(ang)
        dyn = -math.cos(ang)
        # Perpendicular.
        pxn = math.cos(ang)
        pyn = math.sin(ang)
        lx0 = int(base_x - dxn * llen * 0.5 - pxn * leaf_wid - 3)
        lx1 = int(base_x + dxn * llen * 0.5 + pxn * leaf_wid + 3)
        ly0 = int(base_y - llen * 0.6 - 3)
        ly1 = int(base_y + llen * 0.4 + 3)
        lx0 = max(0, lx0)
        lx1 = min(W - 1, lx1)
        ly0 = max(0, ly0)
        ly1 = min(H - 1, ly1)
        for y in range(ly0, ly1 + 1):
            for x in range(lx0, lx1 + 1):
                rx_ = x - base_x
                ry_ = y - base_y
                # Leaf-local coords: along in [0,1], across in [-1,1].
                along = rx_ * dxn + ry_ * dyn
                across = rx_ * pxn + ry_ * pyn
                if along < 0.0 or along > llen:
                    continue
                t = along / llen
                # Lens shape: pointed at base and tip, widest at the middle.
                half = leaf_wid * (math.sin(math.pi * t) ** 0.8)
                if half <= 0.0:
                    continue
                s = across / half
                if abs(s) >= 1.0:
                    continue
                # Green gradient: darker at the base, lighter at the tip.
                gr = 44.0 + 34.0 * t
                gg = 104.0 + 52.0 * t
                gb = 26.0 + 16.0 * t
                # Centre vein.
                if abs(s) < 0.045 and 0.08 < t < 0.95:
                    gr *= 0.72
                    gg *= 0.72
                    gb *= 0.72
                cov = 1.0
                if abs(s) > 0.85:
                    cov = (1.0 - abs(s)) / 0.15
                blend(x, y, clamp255(gr), clamp255(gg), clamp255(gb), cov)

    # --- seeds -------------------------------------------------------------
    if seed_rows:
        rows = [0.28, 0.40, 0.52, 0.64, 0.76, 0.86]
        srx = max(4.0, w * 0.018)
        sry = max(5.0, h * 0.022)
        for ri, v in enumerate(rows):
            hw = berry_half_width(v)
            spacing = 0.30
            avail = 2.0 * hw * 0.80
            count = int(avail / spacing)
            if count < 1:
                continue
            offset = (spacing * 0.5) if (ri % 2 == 1) else 0.0
            for k in range(count):
                u = -hw * 0.80 + spacing * 0.5 + k * spacing + offset
                if abs(u) > hw * 0.82:
                    continue
                # Canvas position of the seed (berry-local -> canvas).
                lx = u * hw2
                ly = (v - 0.5) * h
                sx = cx + lx * ct - ly * st
                sy = cy + lx * st + ly * ct
                # Seed shadow then pale seed, slightly tilted ellipse.
                soft_ellipse(sx + 1.5, sy + 2.0, srx, sry, 150, 70, 18, 0.45)
                soft_ellipse(sx, sy, srx, sry, 255, 233, 158, 0.95)
                blend(int(sx - 1), int(sy - sry * 0.45), 255, 250, 215, 0.8)

    # --- water droplets ------------------------------------------------------
    droplets = [(-0.30, 0.45, 7.0), (0.28, 0.60, 5.5), (-0.12, 0.72, 6.0),
                (0.45, 0.38, 4.5), (-0.52, 0.58, 4.0)]
    for (du, dv, dr) in droplets:
        lx = du * hw2
        ly = (dv - 0.5) * h
        dx_ = cx + lx * ct - ly * st
        dy_ = cy + lx * st + ly * ct
        soft_ellipse(dx_, dy_, dr, dr * 0.9, 255, 255, 255, 0.30)
        soft_ellipse(dx_ - dr * 0.3, dy_ - dr * 0.35, dr * 0.35, dr * 0.32,
                     255, 255, 255, 0.85)


# --------------------------------------------------------------------------
# PNG encoder (hand-rolled: zlib + struct, no PIL)
# --------------------------------------------------------------------------

def _chunk(tag, data):
    body = tag + data
    return (struct.pack(">I", len(data)) + body +
            struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))


def write_png(path, w, h, pixels):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)  # filter: none
        raw += pixels[y * stride:(y + 1) * stride]
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += _chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    draw_background()
    draw_plate()
    # Back berries first, hero berry last (in front).
    draw_berry(300, 430, 240, 300, -14)
    draw_berry(716, 425, 232, 292, 12)
    draw_berry(512, 620, 330, 400, -3)
    n = write_png(out, W, H, buf)
    print("wrote %s (%d bytes, %dx%d)" % (out, n, W, H))


if __name__ == "__main__":
    main()
