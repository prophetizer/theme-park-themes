#!/usr/bin/env python3
"""
Computes a CSS filter() chain (invert/sepia/saturate/hue-rotate/brightness/
contrast) that recolors a black (#000000) source icon/image to approximate
a target hex color. Same technique as the well-known "sosuke" CSS filter
generator, reimplemented here so the theme.park --petio-spinner value (a
filter, not a plain color) can be computed for a new theme's accent color
instead of guessed by eye.

Usage:
    ./css_filter_solver.py b362ff
"""
import sys
import numpy as np
from scipy.optimize import minimize

def hex_to_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i+2], 16) for i in (0, 2, 4)], dtype=float)

def clamp(v, lo=0.0, hi=255.0):
    return np.clip(v, lo, hi)

def apply_invert(rgb, amount):
    return clamp(amount * (255 - rgb) + (1 - amount) * rgb)

def apply_sepia(rgb, amount):
    identity = np.eye(3)
    sepia_m = np.array([
        [0.393, 0.769, 0.189],
        [0.349, 0.686, 0.168],
        [0.272, 0.534, 0.131],
    ])
    m = identity + amount * (sepia_m - identity)
    return clamp(m @ rgb)

def apply_saturate(rgb, amount):
    lumR, lumG, lumB = 0.213, 0.715, 0.072
    m = np.array([
        [lumR + amount * (1 - lumR), lumG - amount * lumG, lumB - amount * lumB],
        [lumR - amount * lumR, lumG + amount * (1 - lumG), lumB - amount * lumB],
        [lumR - amount * lumR, lumG - amount * lumG, lumB + amount * (1 - lumB)],
    ])
    return clamp(m @ rgb)

def apply_hue_rotate(rgb, deg):
    rad = np.deg2rad(deg)
    c, s = np.cos(rad), np.sin(rad)
    lumR, lumG, lumB = 0.213, 0.715, 0.072
    m = np.array([
        [lumR + c * (1 - lumR) + s * (-lumR), lumG + c * (-lumG) + s * (-lumG), lumB + c * (-lumB) + s * (1 - lumB)],
        [lumR + c * (-lumR) + s * (0.143), lumG + c * (1 - lumG) + s * (0.140), lumB + c * (-lumB) + s * (-0.283)],
        [lumR + c * (-lumR) + s * (-(1 - lumR)), lumG + c * (-lumG) + s * (lumG), lumB + c * (1 - lumB) + s * (lumB)],
    ])
    return clamp(m @ rgb)

def apply_brightness(rgb, amount):
    return clamp(rgb * amount)

def apply_contrast(rgb, amount):
    return clamp((rgb - 128) * amount + 128)

def run_filters(params, start=None):
    invert, sepia, saturate, hue, brightness, contrast = params
    rgb = np.array([0.0, 0.0, 0.0]) if start is None else start.copy()
    rgb = apply_invert(rgb, invert)
    rgb = apply_sepia(rgb, sepia)
    rgb = apply_saturate(rgb, saturate)
    rgb = apply_hue_rotate(rgb, hue)
    rgb = apply_brightness(rgb, brightness)
    rgb = apply_contrast(rgb, contrast)
    return rgb

def loss(params, target):
    result = run_filters(params)
    return float(np.sum((result - target) ** 2))

def solve(target_hex, restarts=60, seed=0):
    target = hex_to_rgb(target_hex)
    rng = np.random.default_rng(seed)
    best = None
    best_loss = float("inf")
    bounds = [(0, 1), (0, 1), (0, 7), (0, 360), (0, 2), (0, 2)]
    for _ in range(restarts):
        x0 = np.array([
            rng.uniform(0, 1),
            rng.uniform(0, 1),
            rng.uniform(0, 4),
            rng.uniform(0, 360),
            rng.uniform(0.5, 1.5),
            rng.uniform(0.5, 1.5),
        ])
        res = minimize(loss, x0, args=(target,), method="L-BFGS-B", bounds=bounds)
        if res.fun < best_loss:
            best_loss = res.fun
            best = res.x
    return best, best_loss, target

def format_filter(params):
    invert, sepia, saturate, hue, brightness, contrast = params
    return (
        f"invert({invert*100:.0f}%) sepia({sepia*100:.0f}%) "
        f"saturate({saturate*100:.0f}%) hue-rotate({hue:.0f}deg) "
        f"brightness({brightness*100:.0f}%) contrast({contrast*100:.0f}%)"
    )

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: css_filter_solver.py <hex-color, no #>")
    target_hex = sys.argv[1]
    params, err, target = solve(target_hex)
    achieved = run_filters(params)
    print(f"Target:   #{target_hex}  rgb{tuple(target.astype(int))}")
    print(f"Achieved:           rgb{tuple(achieved.astype(int))}  (squared error: {err:.1f})")
    print(f"Filter:   {format_filter(params)}")
