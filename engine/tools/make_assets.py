# Generates the remaining placeholder assets: goalie kit and ball.
# Team kits, team logos, the league (scoreboard) logo and the ad boards now come from engine/tools/apply_brand.py (repo root: python engine/tools/apply_brand.py).
# Run from the engine dir: python tools/make_assets.py
import os
import numpy as np
import cv2

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
checks = []  # (path, shape, alpha_before or None)


def p(*a):
    return os.path.normpath(os.path.join(D, *a))


def rd(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    assert im is not None, path
    return im


def bgr(rgb):
    return (rgb[2], rgb[1], rgb[0])


def save(path, im, orig, keep_alpha=False):
    assert im.shape == orig.shape and im.dtype == np.uint8, (path, im.shape, orig.shape)
    assert cv2.imwrite(path, im), "imwrite failed " + path
    checks.append((path, orig.shape, orig[..., 3].copy() if keep_alpha else None))


def recolor_kit(src, dst, c1, c2):
    im = rd(src)
    a = im[..., 3]
    rgb = im[..., :3][..., ::-1].astype(np.int32)  # RGB
    mask = (a > 0) & (rgb.sum(-1) > 60)
    q = (rgb // 16) * 16
    key = (q[..., 0] << 16) | (q[..., 1] << 8) | q[..., 2]
    vals, counts = np.unique(key[mask], return_counts=True)
    top = vals[np.argsort(-counts)[:2]]
    cols = np.array([[(v >> 16) & 255, (v >> 8) & 255, v & 255] for v in top], np.int32)
    d = np.stack([((rgb - c) ** 2).sum(-1) for c in cols], -1)
    labels = np.where(mask, d.argmin(-1), 0).astype(np.uint8) * 255
    # median filter removes thin strokes (text, squiggles, badge), keeps large bands
    labels = cv2.medianBlur(labels, 41) > 127
    new = np.array([c1, c2], np.uint8)[labels.astype(np.int32)]
    out = im.copy()
    out[..., :3] = np.where(mask[..., None], new[..., ::-1], im[..., :3])
    save(dst, out, im, keep_alpha=True)


def ball(path):
    im = rd(path)
    h, w, ch = im.shape
    out = np.zeros_like(im)
    out[..., :3] = 235
    if ch == 4:
        out[..., 3] = 255
    g = bgr((190, 190, 190)) + ((255,) if ch == 4 else ())
    for i in range(1, 4):  # straight vertical/horizontal panel seams
        x, y = i * w // 4, i * h // 4
        cv2.line(out, (x, 0), (x, h), g, 1, cv2.LINE_AA)
        cv2.line(out, (0, y), (w, y), g, 1, cv2.LINE_AA)
    for cx, cy in ((0, 0), (w, 0), (0, h), (w, h), (w // 2, h // 2)):  # curved seams
        cv2.ellipse(out, (cx, cy), (w // 4, h // 4), 0, 0, 360, g, 1, cv2.LINE_AA)
    save(path, out, im)


recolor_kit(p("media", "objects", "players", "textures", "goalie_kit.bmp"), p("media", "objects", "players", "textures", "goalie_kit.bmp"), (120, 50, 160), (25, 25, 25))
ball(p("media", "objects", "balls", "ball.bmp"))

# verification: read back, same shape/channels, kit alpha unchanged
for path, shape, alpha in checks:
    im = rd(path)
    assert im.shape == shape, (path, im.shape, shape)
    if alpha is not None:
        assert np.array_equal(im[..., 3], alpha), "alpha changed: " + path
    print("OK", os.path.relpath(path, D), im.shape, "alpha-unchanged" if alpha is not None else "")
print(len(checks), "files verified")
