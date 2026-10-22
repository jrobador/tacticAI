"""Pitch scales. *_eng (engine metres) is canonical for calculations; *_m (105x68) is for drawing only."""
import math

ENG_X, ENG_Y = 54.4, 83.6
DRAW_X, DRAW_Y = 52.5, 34 / 0.42


def scale(pts, kx, ky):
    return [[round(x * kx, 3), round(y * ky, 3)] for x, y in pts]


def to_eng(pts):
    return scale(pts, ENG_X, ENG_Y)


def to_draw(pts):
    return scale(pts, DRAW_X, DRAW_Y)


def speed_m_s(dx, dy):
    """dx, dy: displacement per step (0.1 s) in observation units."""
    return math.hypot(dx * ENG_X, dy * ENG_Y) * 10
