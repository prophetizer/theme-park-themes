#!/usr/bin/env python3
"""
Gradient themes from uiGradients (Ghosh/uiGradients, MIT).

    python3 tools/gradient_theme.py gradients.json cosmic-fusion="Cosmic Fusion" ...

gradients.json is uiGradients' own list (its gradients.json file). Each
argument is <theme name>=<uiGradients name>. uiGradients gives only a
gradient's colours, so every role is derived from them, and every change is
listed in the theme's header:

  page     the gradient at 135deg; a stop is darkened (lightness only) just
           enough for body text to read at 4.5:1 on it
  panels   the same stops at -90deg under the lightest black veil that
           brings body text to 7:1: the page stays vivid, panels readable
  menus    solid: the middle of the gradient under the same veil
  text     near-white tinted toward the gradient; muted the same, dimmer,
           at 4.5:1 on every panel colour
  buttons  the two most saturated stops, brought to one bright lightness;
           labelled with the darkest stop (darkened further if needed)
  links    the same two stops, lightness moved to 4.5:1 on every panel colour

Afterwards: tools/make_variants.py <names> for the twins, then
build_previews.py.
"""

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_variants as mv  # noqa: E402


def rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hx(c):
    return "#%02x%02x%02x" % tuple(int(round(x)) for x in c)


def chroma(c):
    _, a, b = mv.to_oklab(c)
    return (a * a + b * b) ** 0.5


def darken_until(c, fg, need):
    """c with only its lightness lowered until fg reads on it at `need`:1."""
    if mv.contrast(rgb(hx(c)), fg) >= need:
        return c
    L0, a, b = mv.to_oklab(c)
    lo, hi = 0.0, L0
    for _ in range(40):
        mid = (lo + hi) / 2
        if mv.contrast(rgb(hx(mv.from_oklab(mid, a, b))), fg) >= need + 0.02:
            lo = mid
        else:
            hi = mid
    return mv.from_oklab(lo, a, b)


def lift(c, bgs, need):
    """c with only its lightness moved until it reads at `need`:1 on every bg."""
    for margin in (0.02, 0.05, 0.1, 0.2):
        f = mv.fix_contrast(c, bgs, need + margin)
        if f is not None and min(mv.contrast(rgb(hx(f)), g) for g in bgs) >= need:
            return f
    raise ValueError(f"{hx(c)} cannot reach {need}:1")


def veil(stops, fg, need):
    """Smallest black overlay alpha (0.01 steps) for fg at `need`:1 on every stop."""
    for i in range(0, 91):
        a = i / 100
        comp = [tuple((1 - a) * x for x in s) for s in stops]
        if min(mv.contrast(fg, rgb(hx(c))) for c in comp) >= need + 0.02:
            return a, comp
    raise ValueError("no veil is deep enough")


def build(slug, name, colours):
    notes = []
    orig = [rgb(c) for c in colours]
    La = sum(mv.to_oklab(c)[1] for c in orig) / len(orig)
    Lb = sum(mv.to_oklab(c)[2] for c in orig) / len(orig)
    k = min(1.0, 0.03 / max(1e-6, (La * La + Lb * Lb) ** 0.5))    # a whisper of the hue
    text = rgb(hx(mv.from_oklab(0.97, La * k, Lb * k)))
    page = []
    for c in orig:
        d = darken_until(c, text, 4.5)
        if hx(d) != hx(c):
            notes.append(f"Page stop {hx(d)} is uiGradients' {hx(c)} darkened so body text reads at 4.5:1 on it.")
        page.append(rgb(hx(d)))
    alpha, panel = veil(page, text, 7.0)
    panel = [rgb(hx(c)) for c in panel]
    if alpha:
        notes.append(f"Panels lay a black veil at {alpha:g} alpha over the gradient, the least that brings body text to 7:1.")
    mids = [mv.to_oklab(c) for c in page]
    mid = mv.from_oklab(*(sum(m[i] for m in mids) / len(mids) for i in range(3)))
    menu = rgb(hx(tuple((1 - alpha) * x for x in mid)))
    on = panel + [menu]
    muted = rgb(hx(lift(mv.from_oklab(0.80, La * k * 3, Lb * k * 3), on, 4.5)))
    by_chroma = sorted(orig, key=chroma, reverse=True)
    acc, acc2 = by_chroma[0], by_chroma[1] if len(by_chroma) > 1 else by_chroma[0]
    button = rgb(hx(mv.with_lightness(acc, max(0.78, mv.to_oklab(acc)[0]))))
    hover = rgb(hx(mv.with_lightness(acc2, max(0.78, mv.to_oklab(acc2)[0]))))
    for role, new, src in (("--button-color", button, acc), ("--button-color-hover", hover, acc2)):
        if hx(new) != hx(src):
            notes.append(f"{role} {hx(new)} is uiGradients' {hx(src)} lightened so buttons stand out on the gradient.")
    dark = min(page, key=mv.lum)
    label = dark
    for fg in (button, hover):
        label = darken_until(label, fg, 4.5)
    label = rgb(hx(label))
    if hx(label) != hx(dark):
        notes.append(f"--button-text {hx(label)} is the darkest stop, {hx(dark)}, darkened to read at 4.5:1 on both buttons.")
    link = rgb(hx(lift(acc, on, 4.5)))
    link_hover = rgb(hx(lift(acc2, on, 4.5)))
    for role, new, src in (("--link-color", link, acc), ("--link-color-hover", link_hover, acc2)):
        if hx(new) != hx(src):
            notes.append(f"{role} {hx(new)} is uiGradients' {hx(src)} with its lightness moved to read at 4.5:1 on every panel colour.")
    return dict(slug=slug, name=name, colours=colours, page=page, alpha=alpha, menu=menu, text=text,
                muted=muted, button=button, hover=hover, label=label, link=link, link_hover=link_hover,
                notes=notes)


def grad(stops, angle):
    pct = ["0%", "100%"] if len(stops) == 2 else ["0%", "50%", "100%"]
    return f"linear-gradient({angle}, " + ", ".join(f"{hx(s)} {p}" for s, p in zip(stops, pct)) + ")"


def render(d, spinner, tool):
    fixed = " center center/cover no-repeat fixed"
    page = grad(d["page"], "135deg") + fixed
    a = d["alpha"]
    panel = (f"linear-gradient(rgba(0, 0, 0, {a:g}) 0%, rgba(0, 0, 0, {a:g}) 100%), " if a else "") \
        + grad(d["page"], "-90deg") + fixed
    header = [f" * theme.park custom theme: {d['name']}", " *",
              f" * Gradient source: Ghosh/uiGradients gradients.json, '{d['name']}' "
              f"({' -> '.join(c.lower() for c in d['colours'])}), MIT.",
              " * uiGradients gives only the gradient's colours, so every role below is",
              " * one of them (lightness moved where noted), a black veil over them, or a",
              " * near-white tinted toward them: text is not taken from anywhere else.", " *"]
    extra = ["A GRADIENT theme in the shape of theme.park's own: the gradient on the page, "
             "the same stops at -90deg on panels, and a SOLID drop-down menu."] + d["notes"]
    for e in extra:
        line = " *"
        for w in e.split():
            if len(line) + len(w) + 1 > 78:
                header.append(line)
                line = " *"
            line += " " + w
        header.append(line)
    btn = hx(d["button"])
    r, g, b = d["button"]
    pr, pg, pb = d["page"][-1]
    header += [" *", " * --accent-color and --gitea-color-primary-dark-4 are bare \"R, G, B\" on",
               " * purpose: theme.park's base CSS wraps them in rgb()/rgba() itself, and a",
               " * hex here silently kills accents across every app.",
               f" * --petio-spinner computed with tools/{tool} '{btn}'."]
    lines = [
        f"--main-bg-color: {page};", f"--modal-bg-color: {panel};",
        f"--modal-header-color: {panel};", f"--modal-footer-color: {panel};",
        f"--drop-down-menu-bg: {hx(d['menu'])};", f"--button-color: {btn};",
        f"--button-color-hover: {hx(d['hover'])};", f"--button-text: {hx(d['label'])};",
        f"--button-text-hover: {hx(d['label'])};", f"--accent-color: {r}, {g}, {b};",
        "--accent-color-hover: rgb(var(--accent-color),.8);", f"--link-color: {hx(d['link'])};",
        f"--link-color-hover: {hx(d['link_hover'])};", f"--label-text-color: {hx(d['label'])};",
        f"--text: {hx(d['text'])};", "--text-hover: #ffffff;", f"--text-muted: {hx(d['muted'])};",
        f"--arr-queue-color: {hx(d['link'])};", f"--plex-poster-unwatched: {hx(d['hover'])};",
        f"--petio-spinner: {spinner};", f"--gitea-color-primary-dark-4: {r}, {g}, {b};",
        f"--overseerr-gradient: linear-gradient(180deg, rgba({pr}, {pg}, {pb}, 0.17) 0%, rgba({pr}, {pg}, {pb}) 100%);",
    ]
    return "/*\n" + "\n".join(header) + "\n */\n:root {\n" + "\n".join("  " + l for l in lines) + "\n}\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("gradients", type=Path, help="uiGradients' gradients.json")
    ap.add_argument("themes", nargs="+", help='<theme name>=<uiGradients name>')
    ap.add_argument("--out", type=Path, default=HERE.parent / "themes")
    args = ap.parse_args()
    lib = {g["name"]: g["colors"] for g in json.loads(args.gradients.read_text())}
    built = []
    for arg in args.themes:
        slug, _, name = arg.partition("=")
        if name not in lib:
            sys.exit(f"no uiGradients gradient named {name!r}")
        if not mv.SAFE.match(slug) or (args.out / f"{slug}.css").exists():
            sys.exit(f"{slug}: not a plain name, or already exists")
        built.append(build(slug, name, lib[name]))
    with ProcessPoolExecutor() as ex:
        spin = {h: (f, tool) for h, f, tool in ex.map(mv._solve, sorted({hx(d["button"]) for d in built}))}
    for d in built:
        f, tool = spin[hx(d["button"])]
        mv.write_atomic(args.out / f"{d['slug']}.css", render(d, f, tool))
        print("wrote", d["slug"], "|", " ".join(d["notes"]) or "no adjustments")


if __name__ == "__main__":
    main()
