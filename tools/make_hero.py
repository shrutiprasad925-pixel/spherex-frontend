"""Render the hero image: a dotted Earth with continents, city lights and an
atmosphere, framed for the command deck layout in theme.py.

Run from the project folder:  python tools/make_hero.py
It overwrites assets/hero_globe.jpg, so run it after tools/make_assets.py.
Needs only numpy and Pillow.
"""
import os

import numpy as np
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "hero_globe.jpg")


def blur(a, r):
    if a.ndim == 3:
        return np.dstack([blur(a[..., i], r) for i in range(a.shape[2])])
    h, w = a.shape
    k = np.exp(-2 * (np.pi * r) ** 2 * (np.fft.fftfreq(h)[:, None] ** 2 + np.fft.rfftfreq(w)[None, :] ** 2))
    return np.fft.irfft2(np.fft.rfft2(a) * k, s=a.shape).astype(np.float32)


def fbm(w, h, rng, octaves=6, base=4, persistence=.55):
    out, amp, tot = np.zeros((h, w), np.float32), 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        small = rng.random((max(2, int(n * h / w)) + 1, n + 1)).astype(np.float32)
        out += amp * np.asarray(Image.fromarray(small, mode="F").resize((w, h), Image.BICUBIC))
        tot += amp
        amp *= persistence
    out /= tot
    return (out - out.min()) / (out.max() - out.min() + 1e-9)


def splat(canvas, xs, ys, color, weights):
    h, w = canvas.shape[:2]
    xi, yi = np.round(xs).astype(int), np.round(ys).astype(int)
    ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
    wt = np.broadcast_to(np.asarray(weights, np.float32), xs.shape)[ok]
    col = np.asarray(color, np.float32)
    for c in range(3):
        np.add.at(canvas[..., c], (yi[ok], xi[ok]), wt * col[c])


def render(w=2200, h=1222, seed=7):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    # space: nebula haze + stars
    up = lambda m: np.asarray(Image.fromarray(m, mode="F").resize((w, h), Image.BICUBIC))
    bg = np.full((h, w, 3), [.012, .02, .05], np.float32)
    bg += (up(fbm(w // 4, h // 4, rng, 6, 3)) ** 3)[..., None] * np.array([.05, .09, .26], np.float32) * 1.4
    bg += (up(fbm(w // 4, h // 4, rng, 5, 4)) ** 3)[..., None] * np.array([.17, .05, .22], np.float32) * .55
    st = np.zeros((h, w, 3), np.float32)
    n_st = 2200
    pal = np.array([[1, 1, 1], [.7, .85, 1], [1, .85, .65]], np.float32)
    tint = rng.choice(3, n_st, p=[.6, .25, .15])
    sx_, sy_ = rng.random(n_st) * w, rng.random(n_st) * h
    mag = .25 + rng.random(n_st) ** 6 * 1.5
    for t in range(3):
        m = tint == t
        splat(st, sx_[m], sy_[m], pal[t], mag[m])
    bg += blur(st, .7) * 2.4 + blur(st, 2.2) * 1.1

    # sphere geometry (centre and size match the .globe-box layout in theme.py)
    cx, cy, R = .545 * w, .66 * h, .533 * h
    dx, dy = (xx - cx) / R, (yy - cy) / R
    rr = np.hypot(dx, dy)
    inside = rr < 1
    z = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
    light = np.array([-.75, -.35, .55]); light /= np.linalg.norm(light)
    lam = np.clip(dx * light[0] + dy * light[1] + z * light[2], 0, 1)
    body = (.012 + .05 * lam)[..., None] * np.array([.4, .7, 1.2], np.float32)
    body += ((1 - z) ** 3)[..., None] * np.array([.1, .35, .9], np.float32) * .9
    img = np.where(inside[..., None], body, bg)

    # dotted land and ocean
    n = 120000
    i = np.arange(n) + .5
    phi, theta = np.arccos(1 - 2 * i / n), np.pi * (1 + 5 ** .5) * i
    px, py, pz = np.cos(theta) * np.sin(phi), np.sin(theta) * np.sin(phi), np.cos(phi)
    tilt = np.radians(-22)
    y2, z2 = py * np.cos(tilt) - pz * np.sin(tilt), py * np.sin(tilt) + pz * np.cos(tilt)
    lon, lat = np.arctan2(px, z2), np.arcsin(np.clip(y2, -1, 1))
    land_map = fbm(1024, 512, rng, 7, 6, .62)
    land = land_map[((lat / np.pi + .5) * 511).astype(int), ((lon / np.pi + 1) / 2 * 1023).astype(int)]
    is_land = land > np.quantile(land_map, .6)
    vis = z2 > .02
    sx, sy = cx + px * R, cy - y2 * R
    lamp = np.clip(px * light[0] - y2 * light[1] + z2 * light[2], 0, 1)
    dots = np.zeros((h, w, 3), np.float32)
    s1 = vis & is_land
    splat(dots, sx[s1], sy[s1], [.35, .85, 1.0], (.35 + 1.4 * lamp[s1] ** .8) * (.5 + z2[s1] * .5))
    s2 = vis & ~is_land & (rng.random(n) < .5)
    splat(dots, sx[s2], sy[s2], [.15, .35, .9], (.5 + .8 * lamp[s2]) * z2[s2])
    img += (blur(dots, 1.1) * 3.2 + blur(dots, 5) * 1.3) * inside[..., None]
    cl = np.zeros((h, w, 3), np.float32)
    city = vis & is_land & (rng.random(n) < .05) & (lamp < .25)
    splat(cl, sx[city], sy[city], [1, .8, .45], 1.8)
    img += (blur(cl, 1.2) * 2.6 + blur(cl, 6) * .8) * inside[..., None]

    # atmosphere and sun flare
    side = np.clip(.35 + 1.2 * (-dx * .6 - dy * .3), .1, 1.6)
    img += (np.exp(-((rr - 1) / .012) ** 2) * 1.4 * side)[..., None] * np.array([.25, .6, 1.0], np.float32)
    img += (np.where(rr >= 1, np.exp(-(rr - 1) / .05), 0) * .55 * side)[..., None] * np.array([.1, .3, .85], np.float32)
    fx, fy = cx - R * .93, cy - R * .34
    d = np.hypot(xx - fx, yy - fy)
    flare = np.exp(-d / 38) * 1.4 + np.exp(-d / 150) * .55 + np.exp(-d / 420) * .16
    flare += np.exp(-np.abs(yy - fy) / 5) * np.exp(-np.abs(xx - fx) / 520) * .55
    img += flare[..., None] * np.array([1, .92, .8], np.float32)

    # thin orbital arcs
    arcs = Image.new("RGB", (w, h))
    da = ImageDraw.Draw(arcs)
    for a, b in [(1.35, .45), (1.7, .62)]:
        da.arc([cx - R * a, cy - R * b - R * .2, cx + R * a, cy + R * b - R * .2], 200, 340, fill=(90, 160, 255), width=2)
    arr = np.asarray(arcs, np.float32) / 255
    img += blur(arr, 1.2) * .5 + blur(arr, 8) * .6

    img = 1 - np.exp(-img * 1.35)
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    img *= np.clip(1 - .5 * r ** 2.2, 0, 1)[..., None]
    return Image.fromarray((np.clip(img, 0, 1) ** .95 * 255).astype(np.uint8))


if __name__ == "__main__":
    render().save(OUT, "JPEG", quality=80, optimize=True)
    print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB")
