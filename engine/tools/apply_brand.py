"""Applies the tacticAI branding: assets/brand/source/ -> UI exports (assets/brand/) + engine BMPs (engine/data/).

Run from the repo root: python engine/tools/apply_brand.py [--font PATH]
Deps: numpy, Pillow. Re-runnable; engine BMP headers are reused from the existing files.
"""
import argparse, glob, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SRC = os.path.join(ROOT, "assets", "brand", "source")
OUT = os.path.join(ROOT, "assets", "brand")
ENG = os.path.join(ROOT, "engine", "data")
TEAM = os.path.join(ENG, "databases", "default", "images_teams", "tacticai")
ADS = os.path.join(ENG, "media", "textures", "adboards")
NAVY, LIME, WHITE = (12, 23, 42), (198, 244, 50), (240, 240, 240)
ORANGE, TEAL = (232, 112, 42), (31, 158, 154)
TILE_BOX, LOCKUP_BOX = (222, 134, 527, 412), (222, 134, 1320, 412)
written = []


def src(name):
    return os.path.join(SRC, name)


def save_png(img, name):
    path = os.path.join(OUT, name)
    img.save(path)
    written.append(path)


def write_bmp(img, header_from, path):
    """32-bit BGRA bottom-up BMP; 138-byte header reused from a same-size file. Verified by reading back."""
    img = img.convert("RGBA")
    hdr = open(header_from, "rb").read()[:138]
    w, h = img.size
    assert int.from_bytes(hdr[18:22], "little") == w and int.from_bytes(hdr[22:26], "little") == h, (path, img.size)
    data = hdr + np.asarray(img)[::-1][:, :, [2, 1, 0, 3]].tobytes()
    open(path, "wb").write(data)
    back = np.asarray(Image.open(path).convert("RGBA"))
    assert (back == np.asarray(img)).all(), path
    written.append(path)


def fit(img, size=128, pad=3):
    img = img.convert("RGBA")
    img = img.crop(img.getbbox())
    s = (size - 2 * pad) / max(img.size)
    img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    return canvas


def to_alpha(img, bg):
    """Background colour -> transparent, keeping antialiased edges."""
    x = np.asarray(img.convert("RGB")).astype(float)
    d = np.clip(np.abs(x - bg).sum(2) / 120.0, 0, 1)
    return Image.fromarray(np.dstack([x.astype(np.uint8), (d * 255).astype(np.uint8)]))


def light_lockup_box(a):
    """bbox of non-white pixels in the light half (rows 520..1023); rows 512..519 are skipped so nothing touching the half boundary counts."""
    nonwhite = np.abs(a[520:] - 255).sum(2) > 30
    ys, xs = np.nonzero(nonwhite)
    return (int(xs.min()), int(ys.min()) + 520, int(xs.max()) + 1, int(ys.max()) + 521)


def ui_exports(sheet):
    a = np.asarray(sheet).astype(int)
    tile = sheet.crop(TILE_BOX)
    arr = np.asarray(tile.convert("RGBA")).copy()
    mask = Image.new("L", tile.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((6, 6, tile.width - 7, tile.height - 7), radius=46, fill=255)
    arr[:, :, 3] = np.asarray(mask)
    icon = Image.fromarray(arr)  # rounded tile, transparent corners
    save_png(icon, "tacticai-icon.png")
    dark = to_alpha(sheet.crop(LOCKUP_BOX), NAVY)
    save_png(dark, "tacticai-logo-dark-bg.png")
    box = light_lockup_box(a)
    print("light lockup bbox:", box)
    save_png(to_alpha(sheet.crop(box), (255, 255, 255)), "tacticai-logo-light-bg.png")
    crests = {}
    for k in ("bka", "wxc"):
        c = Image.open(src(f"crest-{k}.png")).convert("RGBA")
        c = c.crop(c.getbbox())
        save_png(c, f"crest-{k}.png")
        crests[k] = c
    return icon, dark, crests


def make_boards(font_path, icon, lockup, crests):
    def board(bg):
        return Image.new("RGBA", (1024, 64), bg + (255,))

    font = ImageFont.truetype(font_path, 40)

    def paste_h(b, img, x, h):
        img = img.crop(img.getbbox())
        img = img.resize((round(img.width * h / img.height), h), Image.LANCZOS)
        b.paste(img, (x if x >= 0 else (1024 - img.width) // 2, (64 - h) // 2), img)

    def text(b, s, color, x=None):
        w = ImageDraw.Draw(b).textlength(s, font=font)
        ImageDraw.Draw(b).text(((1024 - w) / 2 if x is None else x, 32), s, font=font, fill=color, anchor="lm")

    def group(bg, logo, h, s, color, gap=22):
        b = board(bg)
        lg = logo.crop(logo.getbbox())
        lw = round(lg.width * h / lg.height)
        x = round((1024 - (lw + gap + ImageDraw.Draw(b).textlength(s, font=font))) / 2)
        paste_h(b, logo, x, h)
        text(b, s, color, x=x + lw + gap)
        return b

    b0 = board(NAVY)
    paste_h(b0, lockup, -1, 50)
    d = ImageDraw.Draw(b0)
    d.rectangle((0, 0, 60, 63), fill=LIME)
    d.rectangle((963, 0, 1023, 63), fill=LIME)
    b1 = board(LIME)
    text(b1, "AGENTIC MATCH INTELLIGENCE", NAVY)
    return [
        b0,
        b1,
        group(ORANGE, crests["bka"], 56, "BRACKENFORD ATHLETIC", WHITE),
        group(TEAL, crests["wxc"], 56, "WEXMOOR CITY", WHITE),
        group(NAVY, icon, 50, "EVERY PLAY, EXPLAINED", WHITE, gap=24),
    ]


def engine_files(icon, crests, boards):
    league = os.path.join(ENG, "media", "menu", "league.bmp")
    # team_a_logo was 121x128; both crests are now 128x128, so team_b's header serves both (team_a is written first)
    write_bmp(fit(crests["bka"]), os.path.join(TEAM, "team_b_logo.bmp"), os.path.join(TEAM, "team_a_logo.bmp"))
    write_bmp(fit(crests["wxc"]), os.path.join(TEAM, "team_b_logo.bmp"), os.path.join(TEAM, "team_b_logo.bmp"))
    write_bmp(fit(icon, pad=2), league, league)
    mask = np.asarray(Image.open(src("kit-uv-mask.png")).convert("L")) > 127
    for s, name in (("bka", "team_a_kit_02.bmp"), ("wxc", "team_b_kit_02.bmp")):
        k = np.asarray(Image.open(src(f"kit-{s}-uv.png")).convert("RGB").resize((1024, 1024), Image.LANCZOS)).copy()
        k[~mask] = 0
        path = os.path.join(TEAM, name)
        write_bmp(Image.fromarray(k), path, path)
    files = sorted(glob.glob(os.path.join(ADS, "*.bmp")))
    hdr = open(files[0], "rb").read()[:54]  # 24-bit BGR, 40-byte info header
    assert int.from_bytes(hdr[18:22], "little") == 1024 and int.from_bytes(hdr[22:26], "little") == 64
    for i, f in enumerate(files):
        img = boards[i % len(boards)].convert("RGB")
        px = np.asarray(img)[::-1][:, :, [2, 1, 0]]
        open(f, "wb").write(hdr + px.tobytes())
        back = np.asarray(Image.open(f).convert("RGB"))
        assert (back == np.asarray(img)).all(), f
        written.append(f)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--font", default="C:/Windows/Fonts/seguibl.ttf", help="TTF for the adboard text")
    args = ap.parse_args()
    if not os.path.isfile(args.font):
        sys.exit(f"error: board font not found: {args.font} (pass --font PATH)")
    sheet = Image.open(src("tacticai-brand-sheet.png")).convert("RGB")
    icon, dark, crests = ui_exports(sheet)
    boards = make_boards(args.font, to_alpha(sheet.crop(TILE_BOX), NAVY), dark, crests)
    prev = Image.new("RGBA", (1024, 5 * 72), (30, 30, 40, 255))
    for i, b in enumerate(boards):
        prev.paste(b, (0, i * 72))
    save_png(prev, "adboards-preview.png")
    engine_files(icon, crests, boards)
    print(f"{len(written)} files written:")
    for p in written:
        print(" ", os.path.relpath(p, ROOT))


if __name__ == "__main__":
    main()
