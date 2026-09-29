#!/usr/bin/env python3
"""
Generate the opposite-mode variant of every theme: a light version of each
dark theme and a dark version of each light one -- theme.park's official and
community themes included, not just ours.

    python3 tools/make_variants.py              # write themes/<name>-light.css / -dark.css
    python3 tools/make_variants.py --dry-run    # report only
    python3 tools/make_variants.py nord dracula # just these sources
    python3 tools/make_variants.py --check      # exit 1 if a theme has no twin

Every theme ships with its twin: run it for each new theme. The theme picker's
host-side worker runs it for every theme saved in the editor.

The spinner filter comes from css_filter_solver.py (numpy + scipy) when those
import, else from spinner_spsa.py, a standard-library port of the picker
editor's solver; the header of each variant names the one used.

Sources: our themes/*.css (except generated variants), plus theme.park's own
from a theme.park css/ directory holding {theme-options,community-theme-options}
(--upstream, or $THEME_PARK_CSS; a clone of themepark-dev/theme.park works).
Without one, only this repo's themes get variants. A variant is skipped when a
real opposite-mode twin exists (see counterparts()): gruvbox-light exists, so
gruvbox gets no generated one, and github-dark-high-contrast pairs with
github-light-high-contrast.

How colours move, per role (every theme uses the same ~22 variables):
  surfaces  page, panels, headers, menus, the overseerr gradient: lightness
            flipped around the page colour, so what was raised stays raised;
            hue kept, saturation softened. Gradients and translucent layers
            keep their structure -- each stop is moved, alpha untouched.
  text      body, hover, muted: lightness inverted, then moved only as far as
            needed for 7:1 (body) / 4.5:1 (muted) against EVERY new panel and
            page colour.
  accents   buttons, links, queue, poster, accent triples: keep their colour,
            moved only as far as contrast needs (links 4.5:1, UI 3:1).
  labels    button/label text: re-picked for the new button colour.
  spinner   recomputed with css_filter_solver.py for the new button colour.

Generated files carry "Generated variant:" in their header -- the picker
lists them in their own section, and this tool never uses one as a source.
Do not edit them by hand: change this tool or the source theme, regenerate.
"""

import argparse
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MARK = "Generated variant:"
SAFE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

COLOUR = re.compile(
    r"#(?P<hex>[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b"
    r"|(?P<fn>rgba?|hsla?)\((?P<args>[^()]*)\)")
TRIPLE = re.compile(r"^\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$")
NAMED = {"white": (255, 255, 255), "black": (0, 0, 0)}

SURFACE = ("--main-bg-color", "--modal-bg-color", "--modal-header-color", "--modal-footer-color",
           "--drop-down-menu-bg", "--overseerr-gradient")
TEXT = {"--text": 7.0, "--text-hover": 7.0, "--text-muted": 4.5}
LABEL = ("--button-text", "--button-text-hover", "--label-text-color")
ACCENT = {"--button-color": 3.0, "--button-color-hover": 3.0, "--link-color": 4.5,
          "--link-color-hover": 4.5, "--arr-queue-color": 3.0, "--plex-poster-unwatched": 3.0,
          "--accent-color": 3.0, "--gitea-color-primary-dark-4": 3.0}
BARE = ("--accent-color", "--gitea-color-primary-dark-4")


def role(var):
    if var in SURFACE:
        return "surface"
    if var in TEXT:
        return "text"
    if var in LABEL:
        return "label"
    if var in ACCENT:
        return "accent"
    if var == "--petio-spinner":
        return "spinner"
    if re.search(r"bg|background|header|footer|modal|menu", var):
        return "surface"
    if re.search(r"text|label", var):
        return "text"
    return "accent"


# --- colour maths: sRGB <-> OKLab, luminance, contrast ------------------------
def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    c = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return c * 255


def lum(rgb):
    r, g, b = (_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def to_oklab(rgb):
    r, g, b = (_lin(x) for x in rgb)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _raw_rgb(L, a, b):
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return tuple(_gam(x) for x in (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
                                   -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                                   -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))


def from_oklab(L, a, b):
    """sRGB for an OKLab colour, reducing chroma (never lightness or hue) until
    it fits the gamut."""
    L = min(1.0, max(0.0, L))
    lo, hi = 0.0, 1.0
    rgb = _raw_rgb(L, a, b)
    if all(-0.5 <= x <= 255.5 for x in rgb):
        return tuple(min(255.0, max(0.0, x)) for x in rgb)
    for _ in range(24):
        mid = (lo + hi) / 2
        if all(-0.5 <= x <= 255.5 for x in _raw_rgb(L, a * mid, b * mid)):
            lo = mid
        else:
            hi = mid
    return tuple(min(255.0, max(0.0, x)) for x in _raw_rgb(L, a * lo, b * lo))


def with_lightness(rgb, L):
    _, a, b = to_oklab(rgb)
    return from_oklab(L, a, b)


def fix_contrast(rgb, bgs, target, start_L=None):
    """Keep hue and chroma; move lightness away from the backgrounds as little
    as possible until contrast with EVERY bg is >= target. None if impossible."""
    L0, a, b = to_oklab(rgb)
    L0 = L0 if start_L is None else start_L
    worst = lambda c: min(contrast(c, g) for g in bgs)
    cur = from_oklab(L0, a, b)
    if worst(cur) >= target:
        return cur
    mean_bg = sum(lum(g) for g in bgs) / len(bgs)
    for end in ((1.0, 0.0) if lum(cur) >= mean_bg else (0.0, 1.0)):
        if worst(from_oklab(end, a, b)) < target:
            continue
        lo, hi = L0, end
        for _ in range(30):
            mid = (lo + hi) / 2
            if worst(from_oklab(mid, a, b)) >= target:
                hi = mid
            else:
                lo = mid
        return from_oklab(hi, a, b)
    return None


# --- parsing and rewriting colour values ----------------------------------------
def _num(v, scale):
    v = v.strip()
    return float(v[:-1]) * scale / 100 if v.endswith("%") else float(v)


def parse_token(m):
    """((r, g, b), alpha) for one COLOUR match, or None if unparseable."""
    if m.group("hex"):
        h = m.group("hex")
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        return rgb, (int(h[6:8], 16) / 255 if len(h) == 8 else 1.0)
    parts = [p for p in re.split(r"[\s,/]+", m.group("args").strip()) if p]
    if "var(" in m.group(0) or len(parts) < 3:
        return None
    try:
        a = _num(parts[3], 1) if len(parts) > 3 else 1.0
        if m.group("fn").startswith("rgb"):
            return tuple(_num(p, 255) for p in parts[:3]), a
        import colorsys
        h = float(parts[0].replace("deg", "")) % 360 / 360
        r, g, b = colorsys.hls_to_rgb(h, _num(parts[2], 1) / (100 if not parts[2].endswith("%") else 1),
                                      _num(parts[1], 1) / (100 if not parts[1].endswith("%") else 1))
        return (r * 255, g * 255, b * 255), a
    except (ValueError, IndexError):
        return None


def fmt(rgb, a):
    r, g, b = (int(round(x)) for x in rgb)
    if a >= 0.999:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgba({r}, {g}, {b}, {round(a, 3):g})"


def stops(value):
    out = []
    for m in COLOUR.finditer(value):
        p = parse_token(m)
        if p:
            out.append(p)
    word = value.strip().lower()
    if not out and word in NAMED:
        out.append((NAMED[word], 1.0))
    return out


def recolour(value, fn):
    """Apply fn(rgb, alpha) -> rgb to every literal colour in a CSS value,
    keeping everything else (gradient syntax, url(), var()) as it is."""
    word = value.strip().lower()
    if word in NAMED and not COLOUR.search(value):
        return fmt(fn(NAMED[word], 1.0), 1.0)

    def one(m):
        p = parse_token(m)
        if not p:
            return m.group(0)
        rgb, a = p
        return fmt(fn(rgb, a), a)
    return COLOUR.sub(one, value)


def layers(value):
    out, depth, cur = [], 0, ""
    for ch in value:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [l for l in out if COLOUR.search(l)]


def surface(value):
    """The colours a background shows once stacked translucent layers are
    composited bottom-up (the picker's metric does the same)."""
    ls = layers(value)
    if not ls:
        st = stops(value)
        return [rgb for rgb, a in st if a >= 0.5]
    base = [rgb for rgb, a in stops(ls[-1]) if a >= 0.5]
    for layer in reversed(ls[:-1]):
        st = stops(layer)
        w = sum(a for _, a in st)
        if not base or not st or w <= 0:
            continue
        a = w / len(st)
        col = [sum(c[i] * x for c, x in st) / w for i in range(3)]
        base = [tuple(a * col[i] + (1 - a) * b[i] for i in range(3)) for b in base]
    return base


# --- building one variant ----------------------------------------------------------
def declarations(css):
    """(var, value) pairs, each value joined onto one line: several upstream
    themes wrap a gradient over lines, and a wrapped value silently broke
    build_previews.py once (see the picker's CLAUDE.md)."""
    body = css[css.index(":root"):] if ":root" in css else css
    return [(v, " ".join(val.split()))
            for v, val in re.findall(r"^\s*(--[\w-]+)\s*:\s*([^;]+?)\s*;", body, re.M)]


def mode_of(decls):
    d = dict(decls)
    page = surface(d.get("--main-bg-color", ""))
    if not page:
        return None
    return "light" if sum(map(lum, page)) / len(page) > 0.35 else "dark"


def build(src_name, css, target):
    """(text of the variant, new button hex) -- spinner filled in later."""
    decls = declarations(css)
    d = dict(decls)
    page = surface(d["--main-bg-color"])
    L0 = sum(to_oklab(c)[0] for c in page) / len(page)

    def move_surface(rgb, _a):
        L, a, b = to_oklab(rgb)
        if target == "light":
            return from_oklab(min(1.0, max(0.86, 0.965 + 0.5 * (L - L0))), a * 0.6, b * 0.6)
        k = min(1.0, 0.08 / max(1e-6, (a * a + b * b) ** 0.5))
        return from_oklab(min(0.34, max(0.12, 0.21 + 1.2 * (L - L0))), a * 0.8 * k, b * 0.8 * k)

    # A neutral (grey) button is really a raised surface -- catppuccin and
    # rose-pine put their --text on one -- so it flips like a surface rather
    # than keeping its lightness as a coloured accent would.
    btn = next(iter(stops(d.get("--button-color", ""))), None)
    neutral_button = btn is not None and sum(x * x for x in to_oklab(btn[0])[1:]) ** 0.5 < 0.04
    flips = lambda var: role(var) == "surface" or (neutral_button and var in ("--button-color", "--button-color-hover"))

    def move_button(rgb, _a):
        # A button stands out by contrast with the page: darker than it on a
        # light theme, lighter on a dark one. Keep the distance, flip the side.
        L, a, b = to_oklab(rgb)
        gap = max(0.06, abs(L - L0))
        if target == "light":
            return from_oklab(max(0.55, 0.965 - 0.8 * gap), a * 0.6, b * 0.6)
        return from_oklab(min(0.5, 0.21 + 1.2 * gap), a * 0.8, b * 0.8)

    new = {}
    for var, val in decls:
        if role(var) == "surface":
            new[var] = recolour(val, move_surface)
        elif flips(var):
            new[var] = recolour(val, move_button)
    new_page = surface(new.get("--main-bg-color", ""))
    panel_src = new.get("--modal-bg-color") or new.get("--main-bg-color", "")
    bgs = (surface(panel_src) or []) + new_page
    if not bgs:
        raise ValueError("no readable background")

    def as_rgb(val):
        m = TRIPLE.match(val)
        if m:
            return tuple(float(x) for x in m.groups())
        st = stops(val)
        return st[0][0] if st else None

    for var, val in decls:
        r = role(var)
        if r == "text":
            need = TEXT.get(var, 4.5)

            def move_text(rgb, _a, need=need):
                L = to_oklab(rgb)[0]
                return fix_contrast(rgb, bgs, need, start_L=1 - L) or rgb
            new[var] = recolour(val, move_text)
        elif r == "accent" and not flips(var):
            need = ACCENT.get(var, 3.0)
            if var in BARE and TRIPLE.match(val):
                rgb = fix_contrast(as_rgb(val), bgs, need) or as_rgb(val)
                new[var] = ", ".join(str(int(round(x))) for x in rgb)
            else:
                new[var] = recolour(val, lambda rgb, _a, need=need: fix_contrast(rgb, bgs, need) or rgb)

    button = as_rgb(new.get("--button-color", "")) or bgs[0]
    for var, val in decls:
        if role(var) == "label":
            def move_label(rgb, _a):
                if contrast(rgb, button) >= 4.5:
                    return rgb
                inv = with_lightness(rgb, 1 - to_oklab(rgb)[0])
                if contrast(inv, button) >= 4.5:
                    return inv
                return max(((255, 255, 255), (17, 20, 27)), key=lambda c: contrast(c, button))
            new[var] = recolour(val, move_label)
    for var, val in decls:
        new.setdefault(var, val)                         # var() references, spinner placeholder

    # Last guard: every button label must read on the new button, whether it
    # is a literal colour or a var() pointing at a colour that moved. A theme
    # with no --button-text at all gets one.
    def resolve(val, depth=0):
        m = re.fullmatch(r"\s*var\(\s*(--[\w-]+)\s*\)\s*", val)
        if m and depth < 5:
            return resolve(new.get(m.group(1), ""), depth + 1)
        return as_rgb(val)
    best = lambda: max(((255, 255, 255), (17, 20, 27)), key=lambda c: contrast(c, button))
    decls = list(decls)
    for var in ("--button-text", "--button-text-hover"):
        if var not in new:
            decls.append((var, ""))
            new[var] = fmt(best(), 1.0)
    for var, _ in decls:
        if role(var) == "label":
            cur = resolve(new[var])
            if cur is None or contrast(cur, button) < 4.5:
                fixed = fix_contrast(cur, [button], 4.5) if cur is not None else None
                new[var] = fmt(fixed or best(), 1.0)
    return decls, new, fmt(button, 1.0)


def counterparts(name):
    """Names that would be `name`'s opposite-mode twin: "dark"/"light" swapped
    at one position, a trailing one dropped, or one appended. The theme
    picker's themes.mode_counterparts() is the same rule -- keep them alike."""
    toks = name.split("-")
    out = []
    for i, tok in enumerate(toks):
        if tok in ("dark", "light"):
            out.append("-".join(toks[:i] + ["light" if tok == "dark" else "dark"] + toks[i + 1:]))
            if i == len(toks) - 1 and i:
                out.append("-".join(toks[:i]))
    return out + [f"{name}-light", f"{name}-dark"]


def title_of(name, css):
    m = re.search(r"theme\.park custom theme:\s*(.+)", css)
    if m:
        return m.group(1).strip()
    return " ".join(w.capitalize() for w in name.split("-"))


def render(src_name, kind, css, target, decls, new, spinner, button_hex, solver):
    title = title_of(src_name, css)
    lines = [f"  {var}: {new[var] if var != '--petio-spinner' else spinner};" for var, _ in decls]
    origin = {"official": "theme.park's official theme", "community": "theme.park's community theme",
              "custom": "this repo's theme"}[kind]
    return (f"/*\n * theme.park custom theme: {title} ({target})\n *\n"
            f" * {MARK} {target} of '{src_name}', {origin} -- by tools/make_variants.py.\n"
            f" * Do not edit by hand: change the generator or the source, then regenerate.\n"
            f" * Hues and saturation come from '{src_name}'; surfaces and text have their\n"
            f" * lightness flipped, accents keep their colour and move only as far as\n"
            f" * contrast needs (text 7:1, muted and links 4.5:1, UI 3:1 on every panel).\n *\n"
            f" * --accent-color and --gitea-color-primary-dark-4 are bare \"R, G, B\" on\n"
            f" * purpose: theme.park's base CSS wraps them in rgb()/rgba() itself.\n"
            f" * --petio-spinner computed with tools/{solver} '{button_hex}'.\n */\n"
            ":root {\n" + "\n".join(lines) + "\n}\n")


def _solve(hexcol):
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    try:
        from css_filter_solver import format_filter, solve
    except ImportError:                                 # no numpy/scipy: the stdlib port
        from spinner_spsa import solve_filter
        return hexcol, solve_filter(hexcol), "spinner_spsa.py"
    params, _err, _t = solve(hexcol.lstrip("#"))
    return hexcol, format_filter(params), "css_filter_solver.py"


def write_atomic(path, text):
    """Temp file + rename: themes/ can sit in a directory another process can
    write (the theme picker's container), and write_text() would follow a
    symlink planted at the variant's name."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def sources(upstream):
    """{name: (kind, css)} for every theme that can be a source."""
    out = {}
    ours = {p.stem: p.read_text() for p in (REPO / "themes").glob("*.css")}
    for name, css in ours.items():
        if MARK not in css[:1200]:
            out[name] = ("custom", css)
    for sub, kind in (("theme-options", "official"), ("community-theme-options", "community")):
        if upstream is None:
            break
        for p in sorted((Path(upstream) / sub).glob("*.css")):
            if p.stem not in ours:                      # deployed customs also sit in theme-options
                out[p.stem] = (kind, p.read_text())
    return out, set(ours)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("only", nargs="*", help="source theme names (default: all)")
    ap.add_argument("--upstream", type=Path, default=os.environ.get("THEME_PARK_CSS") or None,
                    help="theme.park css/ directory (default: $THEME_PARK_CSS)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="write nothing; exit 1 if a theme has no twin file")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    args = ap.parse_args()

    if args.upstream is None:
        print("No --upstream or $THEME_PARK_CSS: making variants of this repo's themes only.")
    srcs, ours = sources(args.upstream)
    real = {n for n, (k, css) in srcs.items()}
    plan, skipped = [], []
    for name in sorted(args.only or srcs):
        if name not in srcs:
            sys.exit(f"unknown source theme: {name}")
        kind, css = srcs[name]
        decls = declarations(css)
        mode = mode_of(decls)
        if not SAFE.match(name) or not mode or "--main-bg-color" not in dict(decls):
            skipped.append((name, "unreadable"))
            continue
        target = "dark" if mode == "light" else "light"
        vname = f"{name}-{target}"
        twin = next((t for t in counterparts(name)
                     if t in real and mode_of(declarations(srcs[t][1])) == target), None)
        if twin:
            skipped.append((name, f"its real {target} twin '{twin}' exists"))
            continue
        plan.append((name, kind, css, target, vname))

    built = []
    for name, kind, css, target, vname in plan:
        try:
            decls, new, button_hex = build(name, css, target)
        except (ValueError, KeyError) as e:
            skipped.append((name, str(e)))
            continue
        built.append((name, kind, css, target, vname, decls, new, button_hex))
    if args.check:
        missing = [(b[4], b[0]) for b in built if not (REPO / "themes" / f"{b[4]}.css").exists()]
        for vname, name in missing:
            print(f"  missing {vname}  (twin of '{name}')")
        # A generated twin nothing would generate any more: its source gained a
        # real twin, or (with the upstream themes to hand) is gone.
        wanted = {(b[0], b[4]) for b in built}
        stale = []
        for p in sorted((REPO / "themes").glob("*.css")):
            m = re.search(re.escape(MARK) + r" \w+ of '([^']+)'", p.read_text()[:1200])
            if m and (m.group(1), p.stem) not in wanted and (m.group(1) in srcs or args.upstream):
                stale.append(p.stem)
                print(f"  stale {p.stem}  (no longer generated from '{m.group(1)}': delete it)")
        print(f"{len(built) - len(missing)} of {len(built)} twins present, {len(stale)} stale"
              + (". Run: python3 tools/make_variants.py " + " ".join(n for _, n in missing) if missing else "."))
        sys.exit(1 if missing or stale else 0)
    print(f"{len(built)} variant(s) to write, {len(skipped)} skipped:")
    for n, why in skipped:
        print(f"  skip {n}: {why}")
    if args.dry_run:
        for b in built:
            print(f"  {b[4]}  (from {b[1]} '{b[0]}', button {b[7]})")
        return

    colours = sorted({b[7] for b in built})
    print(f"Solving {len(colours)} spinner filter(s) with {args.workers} worker(s)...", flush=True)
    sys.path.insert(0, str(HERE))
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        spinners = {h: (f, tool) for h, f, tool in ex.map(_solve, colours)}
    for name, kind, css, target, vname, decls, new, button_hex in built:
        spinner, tool = spinners[button_hex]
        text = render(name, kind, css, target, decls, new, spinner, button_hex, tool)
        write_atomic(REPO / "themes" / f"{vname}.css", text)
        print(f"  wrote {vname}")
    print(f"Wrote {len(built)} file(s) to themes/. Next: python3 build_previews.py")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main()
