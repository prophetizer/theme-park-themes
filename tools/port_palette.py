#!/usr/bin/env python3
"""
Write theme files from published palettes, in this repo's house style.

    python3 tools/port_palette.py ports.json            # write themes/<name>.css
    python3 tools/port_palette.py ports.json --out DIR  # somewhere else

ports.json is a list of themes:

    {"name": "tokyo-night-moon", "title": "Tokyo Night Moon",
     "source": "folke/tokyonight.nvim lua/tokyonight/colors/moon.lua (...)",
     "palette": {"is_light": false, "bg": "#222436", "bg_dark": "#1e2030",
                 "bg_alt": "#2f334d", "fg": "#c8d3f5", "fg_bright": null,
                 "fg_muted": "#828bb8", "blue": "...", "cyan": "...",
                 "green": "...", "yellow": "...", "orange": "...", "red": "...",
                 "magenta": "...", "<any extra key>": "#rrggbb"},
     ...options}

Options (each names a palette key unless noted):
  button, button_hover   default blue / cyan
  link, link_hover       default cyan / magenta
  label                  button text; default: whichever of page, brightest
                         text, panel, text reads best on the button
  nudge_button  (bool)   keep the label, move the buttons' lightness instead
  gradient      (keys)   2 or 3 background keys: a theme.park-style gradient
  high_contrast (bool)   every text role at 7:1
  text_need     (number) body-text target when 7:1 is impossible, with
  text_need_note (str)   the reason, which goes into the header

Nothing is invented: every value is a palette colour, or one with only its
lightness moved to reach its contrast target (body 7:1, muted, links and
button labels 4.5:1, on the page and panels). Each move is listed in the
header. Afterwards: tools/make_variants.py <names> for the twins, then
build_previews.py.
"""

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_variants as mv  # noqa: E402  (colour maths and the spinner solver)


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hx(c):
    return "#%02x%02x%02x" % tuple(int(round(x)) for x in c)


def build(t):
    p = {k: (v.lower() if isinstance(v, str) else v) for k, v in t["palette"].items()}
    notes = []
    bg, dark, alt = p["bg"], p.get("bg_dark"), p.get("bg_alt")
    # Panels are the lighter of the two surfaces; on light themes that keeps
    # cards brighter than the page, on dark ones it raises them.
    page, panel = (dark, bg) if dark else (bg, alt or bg)
    if mv.lum(rgb(panel)) < mv.lum(rgb(page)):
        page, panel = panel, page
    surfaces = [rgb(page), rgb(panel)]
    hc = t.get("high_contrast", False)
    need_text, need_muted, need_link, need_btn = (7, 7, 7, 7) if hc else (7, 4.5, 4.5, 4.5)
    need_text = t.get("text_need", need_text)

    def ensure(name, h, need, bgs=surfaces, where="on the panels"):
        c = rgb(h)
        if min(mv.contrast(c, b) for b in bgs) >= need:
            return h
        # A small margin so the value still passes once rounded to #rrggbb.
        for margin in (0.01, 0.03, 0.06, 0.1, 0.2):
            fixed = mv.fix_contrast(c, bgs, need + margin)
            if fixed is None:
                break
            new = hx(fixed)
            if new != h and min(mv.contrast(rgb(new), b) for b in bgs) >= need:
                notes.append(f"{name} {new} is the palette's {h} with its lightness nudged to reach {need:g}:1 {where}.")
                return new
        raise ValueError(f"{t['name']}: {name} {h} cannot reach {need}:1")

    text = ensure("--text", p["fg"], need_text)
    text_hover = ensure("--text-hover", p.get("fg_bright") or p["fg"], need_text)
    muted = ensure("--text-muted", p["fg_muted"], need_muted)
    button = p[t.get("button", "blue")]
    hover = p[t.get("button_hover", "cyan")] or button
    link = ensure("--link-color", p[t.get("link", "cyan")] or p["blue"], need_link)
    link_hover = ensure("--link-color-hover", p[t.get("link_hover", "magenta")] or link, need_link)
    if t.get("nudge_button"):
        fixed_label = [rgb(p[t["label"]])]
        button = ensure("--button-color", button, need_btn, fixed_label, "under its label")
        hover = ensure("--button-color-hover", hover, need_btn, fixed_label, "under its label")
    cands = [page, p.get("fg_bright") or p["fg"], panel, p["fg"]]
    label = p[t["label"]] if t.get("label") else max(cands, key=lambda c: mv.contrast(rgb(c), rgb(button)))
    label = ensure("--button-text", label, need_btn, [rgb(button), rgb(hover)], "on the button colours")
    queue = p.get("green") or p.get("cyan") or button
    poster = p.get("orange") or p.get("yellow") or button
    if t.get("gradient"):
        stops = [p[k] for k in t["gradient"]]
        pct = ["0%", "100%"] if len(stops) == 2 else ["0%", "55%", "100%"]
        main = (f"linear-gradient(165deg, {', '.join(f'{s} {q}' for s, q in zip(stops, pct))}) "
                "center center/cover no-repeat fixed")
        panel_bg = (f"linear-gradient(-90deg, {panel} 0%, {page} 100%) center center/cover no-repeat fixed")
    else:
        main, panel_bg = page, panel
    r, g, b = rgb(button)
    return dict(t=t, page=page, main=main, panel_bg=panel_bg, menu=panel, button=button, hover=hover,
                label=label, link=link, link_hover=link_hover, text=text, text_hover=text_hover,
                muted=muted, queue=queue, poster=poster, acc=f"{r}, {g}, {b}", og=rgb(page), notes=notes)


def wrap(text, out):
    line = " *"
    for w in text.split():
        if len(line) + len(w) + 1 > 78:
            out.append(line)
            line = " *"
        line += " " + w
    out.append(line)


def render(d, spinner, tool):
    t = d["t"]
    header = [f" * theme.park custom theme: {t['title']}", " *", f" * Palette source: {t['source']}",
              " * Values are the upstream palette's own hexes; roles below map them onto",
              " * theme.park's variables.", " *"]
    extra = []
    if t.get("gradient"):
        extra.append("A GRADIENT theme in the shape of theme.park's own: a hero gradient built from the "
                     "palette's own background tones on the page, a matching -90deg gradient on panels, "
                     "and a SOLID drop-down menu.")
    if t.get("text_need_note"):
        extra.append(t["text_need_note"])
    if t.get("high_contrast"):
        extra.append("HIGH CONTRAST: every text role (body, muted, links, button label) is meant to "
                     "reach WCAG AAA 7:1 on the panels.")
    extra += d["notes"] or ["No contrast adjustments were needed: every text role meets its target as published."]
    for e in extra:
        wrap(e, header)
    header += [" *", " * --accent-color and --gitea-color-primary-dark-4 are bare \"R, G, B\" on",
               " * purpose: theme.park's base CSS wraps them in rgb()/rgba() itself, and a",
               " * hex here silently kills accents across every app.",
               f" * --petio-spinner computed with tools/{tool} '{d['button']}'."]
    pr, pg, pb = d["og"]
    lines = [
        f"--main-bg-color: {d['main']};", f"--modal-bg-color: {d['panel_bg']};",
        f"--modal-header-color: {d['panel_bg']};", f"--modal-footer-color: {d['panel_bg']};",
        f"--drop-down-menu-bg: {d['menu']};", f"--button-color: {d['button']};",
        f"--button-color-hover: {d['hover']};", f"--button-text: {d['label']};",
        f"--button-text-hover: {d['label']};", f"--accent-color: {d['acc']};",
        "--accent-color-hover: rgb(var(--accent-color),.8);", f"--link-color: {d['link']};",
        f"--link-color-hover: {d['link_hover']};", f"--label-text-color: {d['label']};",
        f"--text: {d['text']};", f"--text-hover: {d['text_hover']};", f"--text-muted: {d['muted']};",
        f"--arr-queue-color: {d['queue']};", f"--plex-poster-unwatched: {d['poster']};",
        f"--petio-spinner: {spinner};", f"--gitea-color-primary-dark-4: {d['acc']};",
        f"--overseerr-gradient: linear-gradient(180deg, rgba({pr}, {pg}, {pb}, 0.17) 0%, rgba({pr}, {pg}, {pb}) 100%);",
    ]
    return "/*\n" + "\n".join(header) + "\n */\n:root {\n" + "\n".join("  " + l for l in lines) + "\n}\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("ports", type=Path)
    ap.add_argument("--out", type=Path, default=HERE.parent / "themes")
    args = ap.parse_args()
    ports = json.loads(args.ports.read_text())
    built = [build(t) for t in ports]
    for d in built:
        if (args.out / f"{d['t']['name']}.css").exists():
            sys.exit(f"{d['t']['name']}.css already exists in {args.out}: pick another name")
    with ProcessPoolExecutor() as ex:
        spin = {h: (f, tool) for h, f, tool in ex.map(mv._solve, sorted({d["button"] for d in built}))}
    for d in built:
        f, tool = spin[d["button"]]
        mv.write_atomic(args.out / f"{d['t']['name']}.css", render(d, f, tool))
        print("wrote", d["t"]["name"], "|", " ".join(d["notes"]) or "no adjustments")


if __name__ == "__main__":
    main()
