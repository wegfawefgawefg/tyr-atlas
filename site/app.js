// Router and header. Routes live in the hash: #/<page>?tank=<name>&mode=core&see=<panel>
//   page  one of PAGES below ('' = home); unknown pages fall back to home
//   tank  lower-case tank name (the tank id also works); kept on every page and in every nav link
//   mode  'core' for the 31-point core build; absent means base stats
//   see   optional panel to scroll to once drawn: the panel's heading id without 'h-' (see=corr -> #h-corr)
// Selecting a tank or switching mode rewrites the hash with replaceState, so links stay shareable without
// filling the back button; page changes are ordinary link clicks.
(() => {
const TA = window.TA;
if (!TA) return;
const { tanks, sortedTanks, CLASSES, CLS } = TA;
const PAGES = { home: 'Home', stats: 'Stats', compare: 'Compare', talents: 'Talents', components: 'Components', armor: 'Armor',
  combat: 'Combat', maps: 'Maps', tank: 'Tank', data: 'Data', method: 'Method' };
const SITE = 'Tyr Tank Atlas';
const $ = id => document.getElementById(id);
const slug = t => t.name.toLowerCase();
const bySlug = Object.fromEntries(tanks.flatMap(t => [[t.id.toLowerCase(), t], [slug(t), t]]));
const tankById = id => tanks.find(t => t.id === id) || null;

function parse() {
  const h = location.hash.replace(/^#\/?/, ''), i = h.indexOf('?');
  const path = (i < 0 ? h : h.slice(0, i)).replace(/\/+$/, ''), p = new URLSearchParams(i < 0 ? '' : h.slice(i + 1));
  const t = bySlug[(p.get('tank') || '').toLowerCase()];
  return { page: PAGES[path] ? path : 'home', selected: t ? t.id : null, mode: p.get('mode') === 'core' ? 'core' : 'base', see: p.get('see') };
}
function hashFor(page, sel = TA.selected, mode = TA.mode, see = null) {
  const p = new URLSearchParams(), t = tankById(sel);
  if (t) p.set('tank', slug(t));
  if (mode === 'core') p.set('mode', 'core');
  if (see) p.set('see', see);
  const q = p.toString();
  return `#/${page === 'home' ? '' : page}${q ? '?' + q : ''}`;
}
TA.hashFor = hashFor;

// small DOM helpers shared with pages.js
function keyEl(t) {
  const k = document.createElement('i'); k.className = 'key';
  k.style.background = TA.col(t);
  return k;
}
function make(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
// tank renders (tools/site_art.py): art/<id>_35.webp three-quarter, _90 side profile, _s 280 px thumbnails
const artSrc = (t, angle = 35, small = false) => `art/${t.id}_${angle}${small ? '_s' : ''}.webp`;
function thumb(t, lazy = true) {
  const i = make('img', 'thumb'); i.alt = ''; i.decoding = 'async'; if (lazy) i.loading = 'lazy';
  i.addEventListener('error', () => { i.style.visibility = 'hidden'; }); i.src = artSrc(t, 35, true);
  return i;
}
TA.keyEl = keyEl; TA.make = make; TA.artSrc = artSrc; TA.thumb = thumb;

// "data as of" lines (footer, home hero); nothing when the data file has no game info
const G = window.TYR && window.TYR.game;
const asof = G && G.build ? `Data from game build ${G.build}${G.updated ? `, updated ${G.updated}` : ''}` : '';
for (const e of document.querySelectorAll('.asof')) { e.textContent = asof; e.hidden = !asof; }

// class legends at the top of each chart page
for (const lg of document.querySelectorAll('.cls-legend')) {
  for (const c of CLASSES) { const s = make('span'), k = make('i', 'key'); k.style.background = `var(${CLS[c]})`; s.append(k, c); lg.append(s); }
}

// ---------- tank picker: button + searchable listbox grouped by class ----------
const btn = $('pick-btn'), pop = $('pick-pop'), q = $('pick-q'), list = $('pick-list');
let items = [], active = -1;
function renderBtn() {
  const t = tankById(TA.selected); btn.replaceChildren();
  if (t) btn.append(thumb(t, false));
  btn.append(make('span', 'nm' + (t ? '' : ' ph'), t ? t.name : 'Pick a tank'), make('span', 'car', '▼'));
  btn.setAttribute('aria-label', t ? `Tank: ${t.name}. Change tank` : 'Pick a tank');
}
function addOpt(t) {
  const li = make('li'), i = items.length;
  li.setAttribute('role', 'option'); li.id = 'opt-' + (t ? t.id : 'none');
  li.setAttribute('aria-selected', String((t ? t.id : null) === TA.selected));
  if (t) li.append(thumb(t), keyEl(t), make('span', null, t.name));
  else li.append(make('span', 'sub', 'No tank (clear the pick)'));
  li.addEventListener('click', () => choose(t ? t.id : null));
  li.addEventListener('pointermove', () => { if (active !== i) { active = i; highlight(); } });
  list.append(li); items.push({ id: t ? t.id : null, el: li });
}
function renderList() {
  const f = q.value.trim().toLowerCase(); list.replaceChildren(); items = [];
  const match = t => !f || t.name.toLowerCase().includes(f) || t.cls.toLowerCase().startsWith(f);
  if (!f && TA.selected) addOpt(null);
  for (const c of CLASSES) {
    const ts = sortedTanks.filter(t => t.cls === c && match(t)); if (!ts.length) continue;
    const g = make('li', 'grp'); g.setAttribute('role', 'presentation');
    const k = make('i', 'key'); k.style.background = `var(${CLS[c]})`; g.append(k, c); list.append(g);
    for (const t of ts) addOpt(t);
  }
  if (!items.length) { const e = make('li', 'pick-empty', 'No tank matches'); e.setAttribute('role', 'presentation'); list.append(e); }
  active = Math.max(0, items.findIndex(it => it.id === TA.selected && it.id));
  if (f) active = 0;
  highlight();
}
function highlight() {
  items.forEach((it, i) => it.el.classList.toggle('active', i === active));
  const it = items[active];
  if (it) { q.setAttribute('aria-activedescendant', it.el.id); it.el.scrollIntoView({ block: 'nearest' }); } else q.removeAttribute('aria-activedescendant');
}
function place() {
  const r = btn.getBoundingClientRect();
  pop.style.top = `${r.bottom + 6}px`;
  pop.style.left = `${Math.max(8, Math.min(r.left, document.documentElement.clientWidth - pop.offsetWidth - 8))}px`;
}
function openPop() { pop.hidden = false; btn.setAttribute('aria-expanded', 'true'); q.value = ''; renderList(); place(); q.focus(); }
function closePop(refocus) { if (pop.hidden) return; pop.hidden = true; btn.setAttribute('aria-expanded', 'false'); if (refocus) btn.focus(); }
function choose(id) { closePop(true); TA.select(id); }
btn.addEventListener('click', () => (pop.hidden ? openPop() : closePop(false)));
q.addEventListener('input', renderList);
q.addEventListener('keydown', ev => {
  if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') { ev.preventDefault(); if (items.length) { active = (active + (ev.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length; highlight(); } }
  else if (ev.key === 'Enter') { ev.preventDefault(); if (items[active]) choose(items[active].id); }
  else if (ev.key === 'Escape') { ev.preventDefault(); closePop(true); }
  else if (ev.key === 'Tab') closePop(false);
});
document.addEventListener('pointerdown', ev => { if (!pop.hidden && !$('picker').contains(ev.target)) closePop(false); });
addEventListener('resize', () => { if (!pop.hidden) place(); });

// ---------- mode toggle ----------
$('m-base').addEventListener('click', () => TA.set({ mode: 'base' }));
$('m-core').addEventListener('click', () => TA.set({ mode: 'core' }));

// ---------- state -> DOM; runs before every draw ----------
const nav = $('nav'), main = $('main');
let shownPage = null;
TA.onChange.push(() => {
  const page = TA.page, t = tankById(TA.selected);
  for (const p of main.querySelectorAll(':scope > .page[data-page]')) p.hidden = p.dataset.page !== page;
  for (const a of document.querySelectorAll('a[data-page]')) a.href = hashFor(a.dataset.page);
  $('brand').href = hashFor('home');
  for (const a of nav.querySelectorAll('a')) { if (a.dataset.page === page) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); }
  $('m-base').setAttribute('aria-pressed', String(TA.mode === 'base'));
  $('m-core').setAttribute('aria-pressed', String(TA.mode === 'core'));
  const link = $('tank-link'); link.href = hashFor('tank'); link.textContent = t ? `${t.name} page` : 'All tanks';
  if (page === 'tank') link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  renderBtn();
  document.title = page === 'home' ? SITE : `${page === 'tank' && t ? t.name : PAGES[page]} · ${SITE}`;
  const want = hashFor(page);
  if (location.hash !== want) history.replaceState(null, '', want);
  if (page !== shownPage) {
    if (shownPage !== null) scrollTo(0, 0);
    shownPage = page;
    const a = nav.querySelector(`a[data-page="${page}"]`);   // keep the active tab in view on the phone strip
    if (a && (a.offsetLeft < nav.scrollLeft || a.offsetLeft + a.offsetWidth > nav.scrollLeft + nav.clientWidth)) nav.scrollLeft = a.offsetLeft - 16;
  }
});

let pendingSee = null, loaded = false;
function seeNow() {
  if (!pendingSee) return;
  const h = $('h-' + pendingSee), target = h && (h.closest('.panel') || h);
  if (target && target.offsetParent !== null) target.scrollIntoView({ block: 'start' });
}
function route() {
  const s = parse(); pendingSee = s.see;
  TA.set({ page: s.page, selected: s.selected, mode: s.mode });
  seeNow(); if (loaded) pendingSee = null;
}
addEventListener('hashchange', route);
route();
// later scripts (loadouts, armor) draw their charts as they arrive; once all are in, settle text pages and the scroll target
document.addEventListener('DOMContentLoaded', () => {
  if (TA.page === 'home' || TA.page === 'method') TA.redraw();
  seeNow(); pendingSee = null; loaded = true;
});
})();
