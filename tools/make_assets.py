"""Generate the artwork used by the dashboard (no downloads needed).

Run from the project folder:  python tools/make_assets.py
Outputs go to assets/. Replace any file there with a real NASA / SPHEREx image
of the same name and the app will use yours instead.
"""
import os

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
os.makedirs(OUT, exist_ok=True)


# ---------------------------------------------------------------- helpers
def fbm(h, w, beta, seed):
    """1/f^beta cloud noise, normalised to 0..1."""
    rng = np.random.default_rng(seed)
    f2 = np.fft.fftfreq(h)[:, None] ** 2 + np.fft.fftfreq(w)[None, :] ** 2
    f2[0, 0] = 1
    spec = f2 ** (-beta / 4) * np.exp(2j * np.pi * rng.random((h, w)))
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec))
    lo, hi = np.percentile(n, [1, 99])
    return np.clip((n - lo) / (hi - lo), 0, 1).astype(np.float32)


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def gblur(arr, s):
    """Gaussian blur through the FFT (works on HxW or HxWx3 floats)."""
    if arr.ndim == 3:
        return np.stack([gblur(arr[..., c], s) for c in range(arr.shape[2])], -1)
    pad = int(s * 4) + 2
    a = np.pad(arr, pad, mode="edge")
    h, w = a.shape
    f2 = np.fft.fftfreq(h)[:, None] ** 2 + np.fft.fftfreq(w)[None, :] ** 2
    out = np.real(np.fft.ifft2(np.fft.fft2(a) * np.exp(-2 * np.pi ** 2 * s ** 2 * f2))).astype(np.float32)
    return out[pad:-pad, pad:-pad]


def stars(h, w, n, seed, gain=1.0):
    rng = np.random.default_rng(seed)
    layer = np.zeros((h, w, 3), np.float32)
    ys, xs = rng.integers(0, h, n), rng.integers(0, w, n)
    inten = np.clip(rng.pareto(2.4, n) * 0.1 + 0.04, 0, 1.6) * gain
    cols = np.array([[1, 1, 1], [.78, .88, 1], [1, .9, .74]], np.float32)[rng.integers(0, 3, n)]
    np.add.at(layer, (ys, xs), cols * inten[:, None])
    return layer + gblur(layer, .8) * 2.4


def glow(img, x, y, s, color, gain=1.0, spikes=0.0):
    """Add a soft round glow (optionally with diffraction spikes) in place."""
    h, w, _ = img.shape
    r = int(s * 9)
    x0, x1, y0, y1 = max(0, int(x) - r), min(w, int(x) + r), max(0, int(y) - r), min(h, int(y) + r)
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dx, dy = xx - x, yy - y
    d = np.sqrt(dx * dx + dy * dy) + 1e-3
    g = np.exp(-(d / s) ** 0.8) * gain + 0.35 * gain * np.exp(-(d / (s * .12)) ** 2)
    if spikes:
        g += spikes * gain * (np.exp(-np.abs(dy) / (s * .03)) * np.exp(-np.abs(dx) / (s * 1.5))
                              + np.exp(-np.abs(dx) / (s * .03)) * np.exp(-np.abs(dy) / (s * 1.5)))
    img[y0:y1, x0:x1] += g[..., None] * np.array(color, np.float32)


def vignette(h, w, k=.55):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    return (1 - k * smooth(r, .45, 1.25))[..., None]


def finish(img, path, q=86):
    img = 1 - np.exp(-np.clip(img, 0, None) * 1.35)  # soft highlight roll-off
    Image.fromarray((np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)).save(path, quality=q, optimize=True)
    print("wrote", os.path.basename(path), os.path.getsize(path) // 1024, "KB")


def nebula(h, w, seed, c1, c2, gain=1.0, dust=.6):
    n1, n2, n3 = fbm(h, w, 2.8, seed), fbm(h, w, 3.2, seed + 1), fbm(h, w, 3.4, seed + 2)
    d, e = smooth(n1, .32, .92), smooth(n2, .4, .95)
    rgb = np.array(c1, np.float32) * (d ** 1.4 * gain * .9)[..., None] + np.array(c2, np.float32) * (e ** 1.6 * gain * .6)[..., None]
    rgb *= (1 - dust * smooth(n3, .52, .82))[..., None]
    return rgb + np.array([.008, .011, .03], np.float32)


# --------------------------------------------------------- class thumbnails
W, H = 720, 440


def thumb_star_motion():
    img = nebula(H, W, 11, (.08, .16, .5), (.2, .1, .4), .55) + stars(H, W, 900, 1)
    glow(img, 250, 250, 26, (.5, .6, 1), .25)                       # epoch 1, faint
    glow(img, 470, 175, 40, (.75, .85, 1), 1.0, spikes=.6)           # epoch 2, bright
    for t in np.linspace(0.12, .88, 22):                              # dashed motion track
        if int(t * 22) % 2 == 0:
            glow(img, 250 + 220 * t, 250 - 75 * t, 3.2, (.3, .8, 1), .9)
    return img


def thumb_ice(seed, c1, c2):
    img = nebula(H, W, seed, c1, c2, 1.25, .7) + stars(H, W, 700, seed)
    return img


def thumb_co():
    img = nebula(H, W, 31, (.05, .5, .38), (.05, .2, .45), 1.1, .5)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - 360) / 150) ** 2 + ((yy - 225) / 110) ** 2)
    img *= (1 - .93 * np.exp(-r ** 2 * 1.4))[..., None]               # dense dark core
    img += np.exp(-((r - 1.15) / .28) ** 2)[..., None] * np.array([.1, .75, .55], np.float32) * .55
    return img + stars(H, W, 600, 31)


def thumb_variable():
    img = nebula(H, W, 41, (.5, .24, .05), (.4, .08, .2), .5) + stars(H, W, 700, 4)
    glow(img, 360, 220, 44, (1, .72, .3), 1.3, spikes=.9)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((xx - 360) ** 2 + (yy - 220) ** 2)
    for r0, a in [(95, .5), (150, .32), (205, .2)]:                   # brightening ripples
        img += (np.exp(-((d - r0) / 2.2) ** 2) * a)[..., None] * np.array([1, .65, .25], np.float32)
    return img


def thumb_artifact():
    rng = np.random.default_rng(51)
    img = nebula(H, W, 51, (.35, .02, .1), (.2, .02, .25), .5, .3)
    img += (rng.random((H, W, 1)) ** 9 * .6).astype(np.float32) * np.array([1, .3, .4], np.float32)
    for x in rng.integers(40, W - 40, 7):                              # saturated column streaks
        img[:, x:x + rng.integers(1, 3), :] += np.array([1, .2, .35], np.float32) * rng.uniform(.25, .7)
    for _ in range(6):                                                 # hot blocks
        y, x = rng.integers(20, H - 40), rng.integers(20, W - 80)
        img[y:y + 6, x:x + rng.integers(20, 70), :] += np.array([1, .35, .45], np.float32) * .8
    img[::4, :, :] *= .82                                              # scan lines
    glow(img, 360, 200, 22, (1, .3, .45), 1.1)
    return img


def thumb_galaxy():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ang = np.radians(-28)
    u = (xx - 360) * np.cos(ang) + (yy - 220) * np.sin(ang)
    v = -(xx - 360) * np.sin(ang) + (yy - 220) * np.cos(ang)
    r = np.sqrt((u / 150) ** 2 + (v / 62) ** 2)
    core = np.exp(-r ** 0.9 * 2.6)[..., None] * np.array([1, .82, .58], np.float32)
    halo = np.exp(-r * 1.2)[..., None] * np.array([.35, .42, .8], np.float32) * .55
    img = nebula(H, W, 61, (.04, .06, .22), (.12, .06, .2), .35, .3) + core + halo
    return img + stars(H, W, 800, 6)


def thumb_generic():
    return nebula(H, W, 71, (.25, .2, .7), (.5, .15, .5), .9) + stars(H, W, 800, 7)


THUMBS = {
    "class_star_motion": thumb_star_motion,
    "class_ice_h2o": lambda: thumb_ice(21, (.05, .5, .85), (.06, .25, .6)),
    "class_ice_co2": lambda: thumb_ice(25, (.55, .2, .95), (.7, .12, .55)),
    "class_ice_co": thumb_co,
    "class_variable": thumb_variable,
    "class_artifact": thumb_artifact,
    "class_galaxy": thumb_galaxy,
    "class_generic": thumb_generic,
}


# ------------------------------------------------------------------- hero
def hero(width=1800, height=1000):
    """A dotted celestial sphere with the Milky Way glowing across it."""
    rng = np.random.default_rng(5)
    img = nebula(height, width, 3, (.07, .1, .42), (.28, .08, .38), .5, .55)
    img += stars(height, width, 2600, 9, .9)

    cx, cy, R = .545 * width, .66 * height, .38 * width * .78
    # view direction on the celestial sphere
    a0, d0 = np.radians(250), np.radians(-8)
    f = np.array([np.cos(d0) * np.cos(a0), np.cos(d0) * np.sin(a0), np.sin(d0)])
    r_ax = np.cross([0, 0, 1], f); r_ax /= np.linalg.norm(r_ax)
    u_ax = np.cross(f, r_ax)

    n = 150000
    i = np.arange(n) + .5
    dec = np.arcsin(1 - 2 * i / n)
    ra = np.pi * (1 + 5 ** .5) * i
    p = np.stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)], 1)
    x, y, z = p @ r_ax, p @ u_ax, p @ f
    roll = np.radians(-22)                                             # tilt the whole sphere
    x, y = x * np.cos(roll) - y * np.sin(roll), x * np.sin(roll) + y * np.cos(roll)
    vis = z > 0.02
    p, x, y, z = p[vis], x[vis], y[vis], z[vis]

    # galactic plane: north pole at RA 192.86, Dec 27.13; centre at RA 266.4, Dec -28.94
    gnp = np.array([np.cos(np.radians(27.13)) * np.cos(np.radians(192.86)),
                    np.cos(np.radians(27.13)) * np.sin(np.radians(192.86)), np.sin(np.radians(27.13))])
    gc = np.array([np.cos(np.radians(-28.94)) * np.cos(np.radians(266.4)),
                   np.cos(np.radians(-28.94)) * np.sin(np.radians(266.4)), np.sin(np.radians(-28.94))])
    b = np.degrees(np.arcsin(np.clip(p @ gnp, -1, 1)))
    centre = np.exp(-(np.degrees(np.arccos(np.clip(p @ gc, -1, 1))) / 38) ** 2)
    band = np.exp(-(b / 13) ** 2)
    # lumpy dust and star clouds along the band
    s1, s2 = rng.random(3) * 6, rng.random(3) * 6
    lump = .5 + .5 * np.sin(p @ (s1 * 2.3) + 1.3) * np.sin(p @ (s2 * 2.9) + .4)
    band = band * (.45 + .75 * lump)

    # lighting from the lower-left flare
    nrm = np.stack([x, y, z], 1)
    L = np.array([-.78, -.12, .62]); L /= np.linalg.norm(L)
    lit = np.clip(nrm @ L, 0, 1)
    rim = (1 - z) ** 2.2
    base = (.06 + .5 * lit ** 1.4) * (.5 + .5 * z ** .5)

    cool, warm, white = np.array([.28, .52, 1.0]), np.array([1.0, .72, .42]), np.array([1, .96, .92])
    col = cool[None] * base[:, None] * .5
    col += (white * .5 + warm * .5)[None] * (band * (.45 + 1.1 * centre))[:, None] * (.3 + .9 * lit ** .8)[:, None] * 1.5
    col += np.array([.2, .8, 1.0])[None] * (rim * lit * .9)[:, None]

    X, Y = cx + R * x, cy - R * y
    px, py = np.round(X).astype(int), np.round(Y).astype(int)
    ok = (px >= 0) & (px < width) & (py >= 0) & (py < height)
    # body of the sphere, a deep blue disc so it reads as a solid ball
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / R
    inside = rr < 1
    zz = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
    lit_px = np.clip(((xx - cx) / R * L[0]) * 1 + (-(yy - cy) / R * L[1]) + zz * L[2], 0, 1)
    body = (np.array([.008, .014, .05], np.float32) + np.array([.02, .05, .14], np.float32) * lit_px[..., None] ** 1.8)
    img = np.where(inside[..., None], body * 1.0, img)

    dots = np.zeros((height, width, 3), np.float32)
    np.add.at(dots, (py[ok], px[ok]), col[ok].astype(np.float32) * 1.9)
    img += dots * .9 + gblur(dots, 1.0) * 1.8 + gblur(dots, 8) * 3.0

    # atmosphere rim and outer halo
    rim_lit = np.clip(((xx - cx) * L[0] - (yy - cy) * L[1]) / (R * 1.0) * 1 + .35, 0, 1) ** 1.5
    atm = np.exp(-((rr - 1) / .012) ** 2) * (.25 + .75 * rim_lit)
    halo = np.where(rr > 1, np.exp(-(rr - 1) / .05), 0) * (.15 + .85 * rim_lit)
    img += (atm * .9 + halo * .38)[..., None] * np.array([.35, .78, 1.0], np.float32)
    img += (np.where(inside, (1 - zz) ** 3, 0) * rim_lit * .6)[..., None] * np.array([.3, .7, 1], np.float32)

    # star-light flare at the lower-left limb
    fx, fy = cx - R * .93, cy + R * .22
    glow(img, fx, fy, 60, (1, .85, .62), 1.0, spikes=.7)
    glow(img, fx, fy, 14, (1, 1, 1), 1.6)
    img *= vignette(height, width, .5)
    finish(img, os.path.join(OUT, "hero_globe.jpg"), q=84)


if __name__ == "__main__":
    for name, fn in THUMBS.items():
        out = fn()
        out = out * vignette(H, W, .45)
        finish(out, os.path.join(OUT, name + ".jpg"), q=82)
    hero()
