# Generates the original tacticAI assets (kits, logos, ball, scoreboard logo, ad boards).
# Run once from the engine dir: python tools/make_assets.py
import glob, os
import numpy as np
import cv2

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
FONT = cv2.FONT_HERSHEY_DUPLEX
NAVY = (16, 32, 64)  # RGB
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


def centered_text(im, text, color_rgb, max_w, max_h, thick_ratio=0.1):
    (w, h), base = cv2.getTextSize(text, FONT, 1.0, 1)
    scale = min(max_w / w, max_h / (h + base))
    th = max(1, int(round(scale * 2)))
    (w, h), base = cv2.getTextSize(text, FONT, scale, th)
    x = (im.shape[1] - w) // 2
    y = (im.shape[0] + h) // 2
    cv2.putText(im, text, (x, y), FONT, scale, bgr(color_rgb), th, cv2.LINE_AA)


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


def logo(path, short, c1, c2):
    im = rd(path)
    h, w, ch = im.shape
    out = np.zeros_like(im)
    if ch == 3:
        out[:] = NAVY[::-1]
    c, r = (w // 2, h // 2), min(w, h) // 2 - 2
    col = lambda rgb: bgr(rgb) + ((255,) if ch == 4 else ())
    cv2.circle(out, c, r, col(c1), -1, cv2.LINE_AA)
    cv2.circle(out, c, r, col(c2), 3, cv2.LINE_AA)
    # draw text with a thin outline in the secondary color, fill white
    t = out.copy() if ch == 3 else out
    box = np.zeros((h, w, 3), np.uint8)
    centered_text(box, short, (255, 255, 255), r * 1.3, r * 0.6)
    m = box.sum(-1) > 0
    out[m, :3] = 255
    if ch == 4:
        out[m, 3] = 255
    save(path, out, im)


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


def banner(path, text, w_frac, h_frac, bg=NAVY):
    im = rd(path)
    out = np.zeros_like(im)
    out[..., :3] = bgr(bg)
    if im.shape[2] == 4:
        out[..., 3] = 255
    centered_text(out, text, (255, 255, 255), im.shape[1] * w_frac, im.shape[0] * h_frac)
    save(path, out, im)


ORIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')  # kits are re-derived in place (recolor is idempotent)
KITS_ONLY = "--kits-only" in __import__("sys").argv
teams = p("databases", "default", "images_teams", "tacticai")
recolor_kit(os.path.join(ORIG, "databases", "default", "images_teams", "tacticai", "team_a_kit_02.bmp"), os.path.join(teams, "team_a_kit_02.bmp"), (230, 110, 40), (240, 240, 240))
recolor_kit(os.path.join(ORIG, "databases", "default", "images_teams", "tacticai", "team_b_kit_02.bmp"), os.path.join(teams, "team_b_kit_02.bmp"), (30, 140, 140), (20, 30, 60))
recolor_kit(os.path.join(ORIG, "media", "objects", "players", "textures", "goalie_kit.bmp"), p("media", "objects", "players", "textures", "goalie_kit.bmp"), (120, 50, 160), (25, 25, 25))
if not KITS_ONLY:
  logo(os.path.join(teams, "team_a_logo.bmp"), "BKA", (230, 110, 40), (240, 240, 240))
  logo(os.path.join(teams, "team_b_logo.bmp"), "WXC", (30, 140, 140), (20, 30, 60))
  ball(p("media", "objects", "balls", "ball.bmp"))
  banner(p("media", "menu", "league.bmp"), "tAI", 0.8, 0.5)
  for f in sorted(glob.glob(p("media", "textures", "adboards", "*.bmp"))):
      banner(f, "TACTICAI  SYNTHETIC MATCH", 0.8, 0.6)

# verification: read back, same shape/channels, kit alpha unchanged
for path, shape, alpha in checks:
    im = rd(path)
    assert im.shape == shape, (path, im.shape, shape)
    if alpha is not None:
        assert np.array_equal(im[..., 3], alpha), "alpha changed: " + path
    print("OK", os.path.relpath(path, D), im.shape, "alpha-unchanged" if alpha is not None else "")
print(len(checks), "files verified")
