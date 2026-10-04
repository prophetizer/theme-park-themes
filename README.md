# Theme Park Themes

344 custom themes for [theme.park](https://theme-park.dev), plus 277
generated light/dark twins (theme.park's own themes included): every theme
comes in both a light and a dark form. Each
hand-made theme is a faithful port of a published colour scheme, such as
Tokyo Night, Gruvbox, Kanagawa, Everforest, Solarized, Night Owl, Monokai,
GitHub or Ayu, onto theme.park's variables, with contrast checked rather
than guessed.

Made for [Theme Picker](https://github.com/prophetizer/theme-picker), which
lists every file in `themes/` as a custom theme. The themes work with any
self-hosted theme.park.

## What a theme is

A theme.park theme is one standalone CSS file that sets `:root` variables.
It patches nothing, forks nothing, and is not app-specific. theme.park's
`themes.py` combines each theme file with every app's base CSS to build
`css/base/<app>/<theme>.css`. That's the file the
[traefik-themepark](https://github.com/packruler/traefik-themepark) plugin
(or any other theme.park integration) injects into the app.

So using these themes is a file drop, not a fork.

## Using them

1. Self-host theme.park (e.g. `ghcr.io/themepark-dev/theme.park`).
2. Copy the `themes/*.css` you want into its `css/theme-options/`.
3. Re-run theme.park's `themes.py` inside the container so it generates the
   per-app CSS. Its container init does this on every start, so a restart
   works too.
4. Select the theme by name: in your theme.park integration, or in Theme
   Picker, which lists `themes/` automatically.

To browse before installing, open `previews/index.html`: a mock app UI for
every theme.

## Layout

| Path | What it is |
|---|---|
| `themes/*.css` | The themes, one file per theme. Hand-written ones credit their source palette in the header; generated twins say "Generated variant". |
| `previews/` | Generated mock-UI preview pages (`python3 build_previews.py`). |
| `build_previews.py` | Regenerates `previews/`. Discovers `themes/*.css`; there's no list to maintain. |
| `tools/css_filter_solver.py` | Computes the `--petio-spinner` CSS filter for a hex colour (numpy + scipy). |
| `tools/make_variants.py` | Generates the opposite-mode twin of every theme (`<name>-light.css` / `-dark.css`); `--check` exits 1 if any theme lacks one. Point it at a theme.park `css/` directory with `--upstream` or `$THEME_PARK_CSS` to include theme.park's own themes. |
| `tools/port_palette.py` | Writes themes from published palettes (a JSON list of palettes and role choices), moving only lightness where contrast needs it and listing each move in the header. |
| `tools/gradient_theme.py` | Writes gradient themes from [uiGradients](https://github.com/Ghosh/uiGradients) (MIT): the gradient on the page, a veil on panels for 7:1 text. |
| `tools/spinner_spsa.py` | Standard-library spinner solver, used by `make_variants.py` when numpy and scipy aren't installed. |

## Adding a theme

1. Write `themes/<name>.css`, starting from an existing one. The header's
   second line must be `theme.park custom theme: <Display Title>`;
   `build_previews.py` reads it.
2. Keep `--accent-color` and `--gitea-color-primary-dark-4` as bare
   `R, G, B`, with no `#` and no `rgb()`. theme.park's base CSS wraps them
   itself, and a hex there silently removes accents across every app.
3. Don't guess `--petio-spinner`: run
   `python3 tools/css_filter_solver.py '#rrggbb'` with your button colour.
4. Keep every declaration on one line.
5. Generate its twin: `python3 tools/make_variants.py <name>`. Every theme
   ships in both modes; `python3 tools/make_variants.py --check` confirms
   none is missing.
6. `python3 build_previews.py`, then open `previews/index.html`.

## Credits

Every palette belongs to its authors. Each theme's header names the
original scheme, its author and the file the colours came from. Where a
colour had to change to stay readable, only its lightness moved, and the
header lists the original next to the adjusted value. The repository itself
is [MIT](LICENSE).
