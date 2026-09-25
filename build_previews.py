#!/usr/bin/env python3
"""
Generates one mock-UI preview HTML page per theme.park theme-option CSS
file, using the same layout as shades-of-purple-preview.html, plus an
index page linking all of them for quick side-by-side comparison.
"""
import re
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
THEMES_DIR = REPO_DIR / "themes"
PREVIEW_DIR = REPO_DIR / "previews"

# Themes are discovered from themes/*.css -- there is no list to keep in
# sync. The display title comes from the "theme.park custom theme: <Title>"
# line every theme file carries in its header comment; if that line is
# missing, the filename is title-cased instead.
TITLE_RE = re.compile(r"theme\.park custom theme:\s*(.+?)\s*$", re.M)


def discover_themes():
    found = []
    for css_path in sorted(THEMES_DIR.glob("*.css")):
        match = TITLE_RE.search(css_path.read_text())
        title = match.group(1) if match else css_path.stem.replace("-", " ").title()
        found.append((css_path, title))
    if not found:
        raise SystemExit(f"No .css files found in {THEMES_DIR}")
    return found

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} — theme.park preview</title>
<style>
  :root {{
{vars}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--main-bg-color);
    color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    padding: 32px 24px 64px;
  }}
  h1 {{ color: var(--text-hover); font-size: 22px; margin: 0 0 4px; }}
  .sub {{ color: var(--text-muted); margin: 0 0 32px; font-size: 14px; }}
  h2 {{ color: var(--text-hover); font-size: 15px; text-transform: uppercase; letter-spacing: .06em; margin: 40px 0 14px; border-bottom: 1px solid var(--modal-bg-color); padding-bottom: 8px; }}
  .swatches {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }}
  .swatch {{ border-radius: 10px; overflow: hidden; border: 1px solid rgba(255,255,255,.08); }}
  .swatch .chip {{ height: 56px; }}
  .swatch .label {{ background: var(--modal-bg-color); padding: 8px 10px; font-size: 12px; }}
  .swatch .label .name {{ display: block; color: var(--text-hover); font-weight: 600; }}
  .swatch .label .hex {{ display: block; color: var(--text-muted); font-family: monospace; margin-top: 2px; }}
  .row {{ display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }}
  button.pk {{
    background: var(--button-color); color: var(--button-text); border: none;
    padding: 10px 20px; border-radius: 6px; font-size: 14px; font-weight: 600;
    cursor: pointer; transition: background .15s, color .15s;
  }}
  button.pk:hover {{ background: var(--button-color-hover); color: var(--button-text-hover); }}
  a.pk {{ color: var(--link-color); text-decoration: none; font-weight: 600; }}
  a.pk:hover {{ color: var(--link-color-hover); }}
  .card {{ background: var(--modal-bg-color); border-radius: 10px; overflow: hidden; max-width: 420px; }}
  .card .hd {{ background: var(--modal-header-color); padding: 14px 18px; font-weight: 700; color: var(--text-hover); display: flex; justify-content: space-between; align-items: center; }}
  .card .bd {{ padding: 18px; font-size: 14px; line-height: 1.6; }}
  .card .ft {{ background: var(--modal-footer-color); padding: 12px 18px; display: flex; justify-content: flex-end; gap: 10px; }}
  .badge {{ background: var(--arr-queue-color); color: #0a1e00; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }}
  .dropdown {{ background: var(--drop-down-menu-bg); border-radius: 8px; padding: 6px; width: 200px; font-size: 14px; }}
  .dropdown .item {{ padding: 8px 10px; border-radius: 6px; color: var(--text); }}
  .dropdown .item:hover {{ background: rgba(var(--accent-color), .18); color: var(--text-hover); }}
  .poster {{ width: 90px; height: 130px; border-radius: 6px; background: linear-gradient(160deg, var(--plex-poster-unwatched), var(--modal-bg-color)); display: flex; align-items: flex-end; padding: 6px; font-size: 10px; color: var(--text-hover); }}
  .spinner {{ width: 28px; height: 28px; background: #000 url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 4a6 6 0 016 6h-2a4 4 0 00-4-4V6z"/></svg>') center/contain no-repeat; filter: var(--petio-spinner); }}
  .overseerr-band {{ height: 90px; background: var(--overseerr-gradient); border-radius: 10px; display: flex; align-items: flex-end; padding: 12px; color: var(--text-hover); font-size: 13px; max-width: 420px; }}
  .label-chip {{ display: inline-block; background: rgb(var(--accent-color)); color: var(--label-text-color); font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 6px; }}
</style>
</head>
<body>
  <h1>{title}</h1>
  <p class="sub">theme.park custom theme preview — mock UI elements rendered with the CSS variables in {fname}, not a real app.</p>

  <h2>Palette</h2>
  <div class="swatches">
{swatches}
  </div>

  <h2>Buttons &amp; links</h2>
  <div class="row">
    <button class="pk">Save changes</button>
    <a class="pk" href="#">A themed link</a>
    <span class="label-chip">4K</span>
    <div class="spinner" title="petio-spinner filter, applied to a black source icon"></div>
  </div>

  <h2>Modal / card</h2>
  <div class="card">
    <div class="hd">Series Settings <span class="badge">3 queued</span></div>
    <div class="bd">
      This mock card uses <code>--modal-bg-color</code>, <code>--modal-header-color</code> and <code>--modal-footer-color</code>, the same structure theme.park applies to Sonarr/Radarr/Overseerr modals.
    </div>
    <div class="ft">
      <button class="pk" style="background:transparent;color:var(--text-muted)">Cancel</button>
      <button class="pk">Confirm</button>
    </div>
  </div>

  <h2>Dropdown</h2>
  <div class="dropdown">
    <div class="item">Library</div>
    <div class="item">Settings</div>
    <div class="item">Logout</div>
  </div>

  <h2>Plex poster (unwatched) &amp; Overseerr band</h2>
  <div class="row">
    <div class="poster">Unwatched</div>
    <div class="overseerr-band">Requested — arriving soon</div>
  </div>
</body>
</html>
"""

LABELED_VARS = ["main-bg-color", "modal-bg-color", "button-color", "button-color-hover",
                "link-color-hover", "arr-queue-color", "text", "text-muted"]

def parse_vars(css_text):
    body = re.search(r':root\s*{([^}]*)}', css_text, re.S).group(1)
    out = {}
    for line in body.splitlines():
        m = re.match(r'\s*--([a-zA-Z0-9-]+)\s*:\s*(.+?);\s*$', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out

def main():
    PREVIEW_DIR.mkdir(exist_ok=True)
    index_rows = []
    for css_path, title in discover_themes():
        fname = css_path.name
        css_text = css_path.read_text()
        var_lines = "\n".join(f"    --{k}: {v};" for k, v in parse_vars(css_text).items())
        variables = parse_vars(css_text)

        swatches = []
        for name in LABELED_VARS:
            val = variables.get(name, "")
            hexval = val if val.startswith("#") else ""
            chip_style = f"background:{hexval}" if hexval else f"background:rgb({val})" if name == "accent-color" else "background:#444"
            swatches.append(
                f'    <div class="swatch"><div class="chip" style="{chip_style}"></div>'
                f'<div class="label"><span class="name">{name}</span><span class="hex">{val}</span></div></div>'
            )

        html = TEMPLATE.format(title=title, fname=fname, vars=var_lines, swatches="\n".join(swatches))
        out_name = fname.replace(".css", "-preview.html")
        (PREVIEW_DIR / out_name).write_text(html)
        index_rows.append((out_name, title))
        print(f"wrote previews/{out_name}")

    index_items = "\n".join(
        f'      <li><a href="{href}">{title}</a></li>' for href, title in index_rows
    )
    index_html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>theme.park previews</title>
<style>
  body {{ background:#111; color:#eee; font-family: -apple-system, sans-serif; padding: 32px; }}
  a {{ color:#8ec0ff; }}
  li {{ margin-bottom: 8px; font-size: 15px; }}
</style></head>
<body>
  <h1>theme.park theme previews</h1>
  <ul>
{index_items}
  </ul>
</body></html>
"""
    (PREVIEW_DIR / "index.html").write_text(index_html)
    print("wrote previews/index.html")

if __name__ == "__main__":
    main()
