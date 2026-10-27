"""Vertical 9:16 reels of the broadcast goals and shots, one per language: tacticAI logo on top, the video cropped to a static 4:5 window
(on the ball side for far plays) and over its lower part the lower-third of the Feed Frame (face, team stripe, name, data) drawn with Pillow.
<match>/video.mp4 + render/broadcast/rundown.json -> <match>/render/reels/<en|es>/<graphic_id>.mp4 and render/reels/manifest.json."""
import json
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

LANGS = ("en", "es")
BEFORE_S, MIN_LEN_S = 3.0, 1.0
GOAL_BEFORE_S, GOAL_AFTER_S = 6.0, 1.5  # the goal graphic comes after the goal: show the build-up and the net
W, H = 1080, 1920
TOP, VID_H, VID_END, LT_X = 170, 1350, 1520, 40  # logo band, 4:5 video 1080x1350 (ends at y=1520), lower-third left margin; it sits centred in the band below
U = 36  # px per 1 cqw of the Feed Frame: the graphic keeps its proportions, 1.5x for a phone
LIME, NAVY, RAIL, OFF, DIM = (198, 244, 50), (12, 23, 42), (20, 34, 58), (240, 240, 240), (163, 168, 176)
STRIPE = {"home": [((242, 107, 29), 1.0)], "away": [((25, 167, 158), 0.6), ((10, 15, 18), 0.4)]}
DASH = "–" if os.path.isfile(os.environ.get("TAI_FONT", "")) else "-"  # the default font has no en dash
KICKER = {"goal": ("Goal", "Gol"), "shot": ("Shot", "Disparo")}


def select(graphics):
    return [g for g in graphics if g["type"] in KICKER]


def interval(t_in, t_out, video_s, kind="shot"):
    if kind == "goal":
        return max(0.0, t_in - GOAL_BEFORE_S), min(video_s, t_in + GOAL_AFTER_S)
    return max(0.0, t_in - BEFORE_S), min(video_s, t_out)


def crop_center(ball_x):
    """Crop centre as a fraction of the frame width: the engine camera drifts to the right of the ball far from the middle (+x is screen right)."""
    return 0.5 if abs(ball_x) < 30 else 0.5 + 0.22 * (1 if ball_x > 0 else -1)


def pick_ball_x(rows, t_in):
    """Ball x with the largest |x| over the 6 s up to t_in (the play near a goal); None if no rows."""
    xs = [r["ball"]["x"] for r in rows if t_in - GOAL_BEFORE_S <= r["t_s"] <= t_in]
    return max(xs, key=abs) if xs else None


def ball_x(match_dir, t_in):
    try:
        with open(os.path.join(match_dir, "tracking.jsonl"), encoding="utf-8") as f:
            return pick_ball_x([json.loads(line) for line in f if line.strip()], t_in)
    except Exception:
        return None


def _asset(*rel):
    """ui/public/<rel> found walking up from this file (the repo, or /app in the job image)."""
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        p = os.path.join(d, "ui", "public", *rel)
        if os.path.exists(p):
            return p
        if os.path.dirname(d) == d:
            return None
        d = os.path.dirname(d)


def _face(player_id):
    over = os.environ.get("TAI_PLAYERS_DIR")
    p = os.path.join(over, f"{player_id}.png") if over else _asset("players", f"{player_id}.png")
    return p if p and os.path.isfile(p) else None


def _font(size):
    f = os.environ.get("TAI_FONT")
    return ImageFont.truetype(f, size) if f and os.path.isfile(f) else ImageFont.load_default(size=size)


def cells(g, es):
    """-> [(value, unit, label)] of the data rail, in the language (decimal comma in Spanish)."""
    d, i = g["data"], int(es)
    num = lambda v: str(v).replace(".", ",") if es else str(v)
    out = []
    for key, unit, label in (("ball_kmh", "km/h", ("Ball speed", "Velocidad")), ("distance_m", "m", ("Distance", "Distancia")),
                             *((("xg", "", ("xG", "xG")),) if g["type"] == "shot" else ())):
        if d.get(key) is not None:
            out.append((num(d[key]), unit, label[i]))
    return out


def _tracked(d, xy, s, font, fill, track, anchor="la"):
    x, y = xy
    for ch in s:
        d.text((x, y), ch, font=font, fill=fill, anchor=anchor)
        x += font.getlength(ch) + track
    return x


def lower_third(g, es, name, teams, face=None):
    """The Feed Frame lower-third of a goal or a shot as an RGBA image cropped to its content, at most W - 2*LT_X px wide."""
    goal = g["type"] == "goal"
    u = lambda v: round(v * U)
    h = u(5.4 if goal else 4.6)
    left = u(2.6)
    kicker = KICKER[g["type"]][int(es)]
    if goal:
        kicker += f" · {teams[g['team']]['name']}"
    f_k, f_n = _font(u(0.9)), _font(u(2.6 if goal else 1.95))
    f_b, f_s = _font(u(1.15)), _font(u(1.9))
    f_v, f_u, f_l = _font(u(1.65)), _font(u(0.95)), _font(u(0.72))
    track = u(0.9) * 0.16
    kw = sum(f_k.getlength(c) + track for c in kicker.upper())
    plate_w = u(1.3) + max(kw, f_n.getlength(name)) + u(1.6)
    rail_h = u(4.2)
    img = Image.new("RGBA", (2 * W, h + u(0.22) + rail_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([left, 0, left + h - 1, h - 1], fill=(8, 17, 32, 255))
    if face:
        with Image.open(face) as f:
            f = f.convert("RGB")
            f = f.resize((h, round(f.height * h / f.width)))
            img.paste(f.crop((0, 0, h, h)), (left, 0))
    y = 0
    for color, share in STRIPE[g["team"]]:
        d.rectangle([left, y, left + u(0.5) - 1, y + round(h * share) - 1], fill=color)
        y += round(h * share)
    px = left + h
    d.rectangle([px, 0, px + plate_w, h - 1], fill=(*NAVY, 245))
    kfs, nfs = u(0.9), u(2.6 if goal else 1.95)
    tot = (kfs + nfs) * 0.75 + u(0.35)
    _tracked(d, (px + u(1.3), h / 2 - tot / 2 + kfs * 0.37), kicker.upper(), f_k, LIME, track, "lm")
    d.text((px + u(1.3), h / 2 + tot / 2 - nfs * 0.37), name, font=f_n, fill=OFF, anchor="lm")
    rule_y = h
    d.rectangle([left, rule_y, px + plate_w, rule_y + u(0.22) - 1], fill=LIME)
    ry = rule_y + u(0.22)
    x = px
    parts = []  # (width, draw(x))

    def cell(w, draw):
        parts.append((w, draw))

    if goal:
        h_, a_ = g["data"]["score"]["home"], g["data"]["score"]["away"]
        sh, sa, sc = teams["home"]["short"], teams["away"]["short"], f"{h_}{DASH}{a_}"
        w = u(1.0) + f_b.getlength(sh) + u(0.7) + f_s.getlength(sc) + u(0.7) + f_b.getlength(sa) + u(1.05)

        def score(x):
            x += u(1.0)
            d.text((x, ry + rail_h // 2), sh, font=f_b, fill=OFF, anchor="lm")
            x += f_b.getlength(sh) + u(0.7)
            d.text((x, ry + rail_h // 2), sc, font=f_s, fill=LIME, anchor="lm")
            x += f_s.getlength(sc) + u(0.7)
            d.text((x, ry + rail_h // 2), sa, font=f_b, fill=OFF, anchor="lm")
        cell(w, score)
    for v, un, lb in cells(g, es):
        w = u(1.0) + max(f_v.getlength(v) + (u(0.35) + f_u.getlength(un) if un else 0), f_l.getlength(lb.upper()) + u(0.08) * len(lb)) + u(1.05)

        def data(x, v=v, un=un, lb=lb):
            d.text((x + u(1.0), ry + u(0.7)), v, font=f_v, fill=OFF)
            if un:
                d.text((x + u(1.0) + f_v.getlength(v) + u(0.35), ry + u(0.7) + u(1.65)), un, font=f_u, fill=DIM, anchor="ls")
            _tracked(d, (x + u(1.0), ry + u(0.7) + u(1.65) + u(0.3)), lb.upper(), f_l, DIM, u(0.72) * 0.08)
        cell(w, data)
    if g["type"] == "shot":
        on = bool(g["data"].get("on_target"))
        txt = (("On target", "A puerta") if on else ("Off target", "Fuera"))[int(es)].upper()
        col = LIME if on else DIM
        w = u(1.0) + u(0.9) + u(0.5) + f_b.getlength(txt) + u(0.1) * len(txt) + u(1.0)

        def status(x):
            cx, cy, r = x + u(1.0) + u(0.45), ry + rail_h // 2, u(0.45)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=u(0.2), fill=col if on else None)
            _tracked(d, (cx + r + u(0.5), cy - u(0.5)), txt, f_b, col, u(0.1))
        cell(w, status)
    total = sum(w for w, _ in parts)
    d.rectangle([x, ry, x + total, ry + rail_h - 1], fill=(*RAIL, 247))
    for w, draw in parts:
        draw(x)
        x += w
        d.line([x - 1, ry, x - 1, ry + rail_h - 1], fill=(240, 240, 240, 26))
    img = img.crop((left, 0, img.getbbox()[2], img.height))
    room = W - 2 * LT_X
    return img if img.width <= room else img.resize((room, round(img.height * room / img.width)), Image.LANCZOS)


def _ffmpeg(video, out, start, end, lt_png, logo, crop):
    """crop = (width, height, x) of the 4:5 window in the source."""
    cw, ch, cx = crop
    chain = f"[0:v]crop={cw}:{ch}:{cx}:0,scale={W}:{VID_H}[v];color=black:{W}x{H},format=yuv420p[bg];[bg][v]overlay=0:{TOP}[b]"
    last, n = "b", 1
    if logo:
        chain += f";[{n}:v]scale=440:-1[l];[{last}][l]overlay=(W-w)/2:({TOP}-h)/2[c]"
        last, n = "c", n + 1
    chain += f";[{last}][{n}:v]overlay={LT_X}:{VID_END}+({H}-{VID_END}-h)/2[o]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", os.path.abspath(video), *(["-i", logo] if logo else []), "-i", lt_png,
           "-t", f"{end - start:.3f}", "-filter_complex", chain, "-map", "[o]", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", os.path.abspath(out)]
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or "ffmpeg failed").strip().splitlines()[-1][:300])


def run(match_dir, video=None):
    """-> warnings. Failures go to manifest.json `errors`, never raised."""
    video = video or os.path.join(match_dir, "video.mp4")
    out_dir = os.path.join(match_dir, "render", "reels")
    manifest = {"reels": [], "errors": []}
    warnings = []

    def save():
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=1)
        return warnings

    def load(*rel):
        with open(os.path.join(match_dir, *rel), encoding="utf-8") as f:
            return json.load(f)

    try:
        rundown = os.path.join(match_dir, "render", "broadcast", "rundown.json")
        if not os.path.isfile(video):
            manifest["errors"].append({"graphic_id": None, "message": "no video.mp4"})
        elif shutil.which("ffmpeg") is None:
            manifest["errors"].append({"graphic_id": None, "message": "ffmpeg not found"})
        elif not os.path.isfile(rundown):
            manifest["errors"].append({"graphic_id": None, "message": "no broadcast rundown"})
        if manifest["errors"]:
            warnings.append(f"reels: {manifest['errors'][0]['message']}")
            return save()
        meta = load("meta.json")
        v = meta["video"]
        video_s = v["frames"] / v["fps"]
        vw, vh = v.get("width", 1280), v.get("height", 720)
        cw = round(vh * 4 / 5 / 2) * 2
        names = {p["player_id"]: p["name"] for p in load("roster.json")["players"]}
        logo = _asset("tacticai-logo-dark-bg.png")
        for g in select(load("render", "broadcast", "rundown.json")["graphics"]):
            gid = g["id"]
            start, end = interval(g["t_in"], g["t_out"], video_s, g["type"])
            if end - start < MIN_LEN_S:
                manifest["errors"].append({"graphic_id": gid, "message": f"interval too short ({end - start:.2f} s)"})
                warnings.append(f"reel {gid} skipped: interval too short")
                continue
            bx = ball_x(match_dir, g["t_in"])
            cx = max(0, min(vw - cw, round((0.5 if bx is None else crop_center(bx)) * vw - cw / 2)))
            files = {}
            for lang in LANGS:
                dest = os.path.join(out_dir, lang, f"{gid}.mp4")
                try:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with tempfile.TemporaryDirectory() as tmp:
                        png = os.path.join(tmp, "lt.png")
                        lower_third(g, lang == "es", names.get(g["player_id"], g["player_id"] or "").upper(), meta["teams"], _face(g["player_id"])).save(png)
                        _ffmpeg(video, dest, start, end, png, logo, (cw, vh, cx))
                    files[lang] = f"render/reels/{lang}/{gid}.mp4"
                except Exception as err:
                    if os.path.exists(dest):
                        os.remove(dest)
                    manifest["errors"].append({"graphic_id": gid, "message": f"{lang}: {err}"})
                    warnings.append(f"reel {gid} {lang} failed: {err}")
            if files:
                manifest["reels"].append({"graphic_id": gid, "type": g["type"], "t_in": g["t_in"], "player_id": g["player_id"], "files": files})
    except Exception as err:
        manifest["errors"].append({"graphic_id": None, "message": f"{type(err).__name__}: {err}"})
        warnings.append(f"reels failed: {err}")
    return save()
