# Tyr Tank Atlas site

Plain static site: HTML, SVG and vanilla JS, no build step. Serve the folder from any static host;
all paths are relative. Locally: `../serve.sh` -> http://127.0.0.1:8740/.

## Files

- `index.html`: header, every page's markup, script tags. Each page is a `<div class="page" data-page="...">`
  directly under `<main>`; only the current one is shown.
- `style.css`: colour tokens (light, dark, `data-theme` override), type, controls, panels, header and tank picker, tables,
  findings blocks, maps zoom buttons, phone rules. `art.css`: everything built around the tank renders: home hero and roster,
  home finding cards, tank page header, stat tiles, tank index cards, `.thumb` images. Keep each under about 600 lines.
- `art/`: Blender renders of the game's tank models, by tank id (`TA.tanks[i].id`, not the display name), built by `tools/site_art.py`.
  `<id>_35.webp` three-quarter hero (transparent, about 1300 px wide), `<id>_90.webp` side profile, `_s` versions are 280 px thumbnails,
  `index.json` holds the sizes. In code use `TA.artSrc(t, angle, small)` for a path and `TA.thumb(t, lazy = true)` for a thumbnail `<img>`.
  Used by: home hero and roster (pages.js), tank page header and tank index (pages.js), tank picker (app.js), notable-build cards (build.js).
  The home hero image gets its `src` from pages.js, so other pages never download it.
- `data.js` (`window.TYR`), `loadouts.js` (`window.TYR_LOAD`), `armor_data.js` (`window.TYR_ARMOR`): built by `tools/site_data.py` and friends.
- `atlas.js`: shared helpers and state (`window.TA`), strips, scatter, PCA map, similarity heatmap, talent uplift, table.
- `dist.js`: distributions, z-score profile, correlation matrix.
- `app.js`: hash router and header (tank picker, stat mode, nav, page titles).
- `pages.js`: home findings, tank page header, stat tiles and index, method page details.
- `build.js`: component charts. `armor.js`: armor roses, hemisphere map, x-ray, face-off matrix.
- `findings.js`, `findings_fight.js`: the numbered "What this shows" takeaways on every page and under chart panels, computed
  from the data at draw time. `TA.F.add(page, fn)` registers a function that fills a `.findings` block with `TA.F.show(anchor, key, items)`;
  they run after the page's charts and again when a chart-local control changes. Load last.

## Look

Late-90s game UI: cut corners (`clip-path`, shapes in the `--cut-*` tokens), slanted page-head bands with a faint grid, chrome
buttons (`--chrome`, pressed state), and a thin iridescent edge (`--iris`) on the header and each panel's top-left. Panels draw their
1 px outline with two clipped pseudo-elements, so their content is never clipped. Fonts from Google Fonts: Oxanium (600, 700) for
headings, nav, labels and big numbers; IBM Plex Sans for text; IBM Plex Mono for tables and small data. Loud: tank art, headline
numbers, charts. Quiet: page, outlines, grid texture. Charts keep their own colours; they read `--ink`, `--ink-2`, `--muted`, `--grid`,
`--axis`, `--accent` and the class, sequential and diverging tokens, so restyling goes through the tokens.

Phones: the header stays sticky with the picker on the first row, the nav strip scrolls sideways, controls and segmented groups wrap,
buttons are at least 40 px tall, wide charts scroll inside their `.scroll` box. On touch a tap shows a chart's tooltip (atlas.js replays
the chart's own `pointermove` handler) and it stays until the next tap or a scroll; `TA.hideTip(true)` always hides it. The Maps canvas
pans with one finger once zoomed, pinches to zoom, and has +, - and Reset buttons; at full view a finger on it scrolls the page.
The footer and the home hero show "Data from game build ..." from `TYR.game` (any `.asof` element; hidden when the field is missing).

All scripts load with `defer` in that order, so the page paints before the large data files arrive.
`build.js` and `armor.js` load after the first draw and draw their charts when they arrive.

## Routes

`#/<page>?tank=<name>&mode=core&see=<panel>`

- pages: home (`#/`), stats, compare, talents, components, armor, combat, tank, data, method
- `tank`: lower-case tank name, kept across pages; `mode=core` for the 31-point core build
- `see`: scroll to a panel once drawn, by its heading id without `h-` (`see=corr` scrolls to `#h-corr`)

## Adding a chart

1. Add a `<section class="panel">` with a heading id and a chart container id inside the right page in `index.html`.
   The Combat page has a marked spot for new combat panels.
2. In the chart's script, register the draw function for its page: `TA.chart('combat', drawThing)`.
   Only the visible page draws (hidden containers measure 0 wide); the router redraws it on page change,
   tank pick, mode change and resize. Do not call the draw function at load; if the script loads late,
   end with `if (TA.page === 'combat') TA.redraw();`.
3. Read state from `TA.selected` (tank id or null) and `TA.mode`; change it with `TA.select(id)` or `TA.set({ mode })`.
   Chart-local controls call `TA.redraw()` or their own draw function.

`TA.onDraw` still works for older code: functions pushed there draw with the Combat page.
