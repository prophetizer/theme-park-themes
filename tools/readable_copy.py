#!/usr/bin/env python3
"""
A readable copy of a theme whose text doesn't reach its contrast targets.

    python3 tools/readable_copy.py hotline space-gray     # themes/<name>-readable.css
    python3 tools/readable_copy.py --dry-run hotline

Sources: this repo's themes/, then theme.park's own (--upstream, or
$THEME_PARK_CSS: a css/ directory holding theme-options/ and
community-theme-options/).

Only lightness moves (OKLab; hue and chroma kept), and only where a target is
missed, measured on the panels and the page as composited (translucent layers
stacked the way the browser draws them):

  body text, hover text   7:1
  muted text, links       4.5:1
  button labels           4.5:1 on the button and its hover colour

When no text colour can reach its target on the theme's own surfaces, the
surfaces themselves move -- darker on a dark theme, lighter on a light one, a
step at a time -- until it can. Every change is listed in the copy's header.
Everything else (gradients, images, the spinner, bare "R, G, B" accents) is
kept exactly. Afterwards: tools/make_variants.py <name>-readable for the
twin, then build_previews.py. The theme picker's "Make a readable copy" does
the same in the browser.
"""

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import make_variants as mv  # noqa: E402  (colour maths shared with the twins)

TEXT = {"--text": 7.0, "--text-hover": 7.0, "--text-muted": 4.5, "--link-color": 4.5, "--link-color-hover": 4.5}
LABELS = ("--button-text", "--button-text-hover", "--label-text-color")
SURFACES = ("--main-bg-color", "--modal-bg-color", "--modal-header-color", "--modal-footer-color",
            "--drop-down-menu-bg")


def find(name, upstream):
    p = REPO / "themes" / f"{name}.css"
    if p.exists():
        return p.read_text(), "this repo's theme"
    for sub, kind in (("theme-options", "theme.park's official theme"),
                      ("community-theme-options", "theme.park's community theme")):
        p = Path(upstream or "") / sub / f"{name}.css"
        if upstream and p.exists():
            return p.read_text(), kind
    sys.exit(f"{name}: not found in themes/ or {upstream or '(no --upstream)'}")


def backgrounds(new):
    panel = new.get("--modal-bg-color") or new.get("--main-bg-color", "")
    bgs = (mv.surface(panel) or []) + mv.surface(new.get("--main-bg-color", ""))
    if not bgs:
        raise ValueError("no readable background")
    return bgs


def solid(val, new, depth=0):
    """The colour a value resolves to (following var()), or None."""
    import re
    m = re.fullmatch(r"\s*var\(\s*(--[\w-]+)\s*\)\s*", val or "")
    if m and depth < 5:
        return solid(new.get(m.group(1), ""), new, depth + 1)
    st = mv.stops(val or "")
    return st[0][0] if st else None


def readable(name, css):
    decls = mv.declarations(css)
    new = dict(decls)
    order = [v for v, _ in decls]
    notes = []
    light = mv.mode_of(decls) == "light"

    # 1. Surfaces: step them away from the text until every text role can
    #    reach its target (most themes never get here).
    def feasible():
        bgs = backgrounds(new)
        return all(mv.fix_contrast(solid(new[v], new), bgs, need + 0.05) is not None
                   for v, need in TEXT.items() if v in new and solid(new[v], new) is not None)

    def step_surface(rgb, _a):
        L = mv.to_oklab(rgb)[0]
        return mv.with_lightness(rgb, L + 0.15 * (1 - L) if light else L * 0.85)
    step = 0
    while not feasible() and step < 12:
        step += 1
        for var in SURFACES:
            if var in new:
                new[var] = mv.recolour(new[var], step_surface)
    if step:
        notes.append(f"Surfaces {'lightened' if light else 'darkened'} in {step} step(s) (lightness only): "
                     "no text colour could reach its target on the theme's own.")
    bgs = backgrounds(new)

    # 2. Text roles, against the (possibly moved) panels and page.
    for var, need in TEXT.items():
        if var not in new:
            continue
        before = new[var]

        def fix(rgb, _a, need=need):
            if min(mv.contrast(rgb, b) for b in bgs) >= need:
                return rgb
            return mv.fix_contrast(rgb, bgs, need + 0.05) or rgb
        after = mv.recolour(before, fix)
        # recolour() rewrites every colour in its own notation; a value whose
        # colours didn't actually move keeps its original spelling.
        same = [tuple(round(x) for x in c) for c, _ in mv.stops(before)] == \
               [tuple(round(x) for x in c) for c, _ in mv.stops(after)]
        if not same:
            new[var] = after
            notes.append(f"{var} {after} (was {before}): lightness moved to reach {need:g}:1 on the panels.")

    # 3. Button labels on the button and its hover colour.
    button = solid(new.get("--button-color"), new)
    if button is not None:
        btns = [button] + ([solid(new["--button-color-hover"], new)] if solid(new.get("--button-color-hover"), new) else [])
        for var in LABELS:
            if var not in new and var != "--button-text":
                continue
            cur = solid(new.get(var, ""), new) if var in new else None
            if cur is not None and min(mv.contrast(cur, b) for b in btns) >= 4.5:
                continue
            fixed = mv.fix_contrast(cur, btns, 4.55) if cur is not None else None
            best = fixed or max(((255, 255, 255), (17, 20, 27)), key=lambda c: min(mv.contrast(c, b) for b in btns))
            was = new.get(var, "(not set)")
            new[var] = mv.fmt(best, 1.0)
            if var not in order:
                order.append(var)
            notes.append(f"{var} {new[var]} (was {was}): reaches 4.5:1 on the button colours.")
    return order, new, notes


def render(name, kind, css, order, new, notes):
    title = mv.title_of(name, css)
    out = [f"/*\n * theme.park custom theme: {title} Readable\n *",
           f" * Readable copy of '{name}', {kind} -- by tools/readable_copy.py.",
           " * Only lightness moved (OKLab; hue and chroma kept), only where a contrast",
           " * target was missed (body 7:1, muted and links 4.5:1, button labels 4.5:1).", " *"]
    for n in notes:
        line = " *"
        for w in n.split():
            if len(line) + len(w) + 1 > 78:
                out.append(line)
                line = " *  "
            line += " " + w
        out.append(line)
    out.append(" */")
    body = "\n".join(f"  {v}: {new[v]};" for v in order)
    return "\n".join(out) + "\n:root {\n" + body + "\n}\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("names", nargs="+")
    ap.add_argument("--upstream", type=Path, default=os.environ.get("THEME_PARK_CSS") or None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for name in args.names:
        css, kind = find(name, args.upstream)
        order, new, notes = readable(name, css)
        dst = REPO / "themes" / f"{name}-readable.css"
        if not notes:
            print(f"{name}: already meets every target; no copy written")
            continue
        text = render(name, kind, css, order, new, notes)
        if args.dry_run:
            print(f"--- {dst.name}\n" + "\n".join(notes))
            continue
        if dst.exists() and "readable_copy.py" not in dst.read_text()[:600]:
            sys.exit(f"{dst.name} exists and wasn't made by this tool; not overwriting")
        mv.write_atomic(dst, text)
        print(f"wrote {dst.name}: {len(notes)} change(s)")


if __name__ == "__main__":
    main()
