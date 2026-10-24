// Network Replay: two saved runs of the 2x2 grid, drawn side by side on canvases, one clock.
//
// What may be drawn (views/replay.py): vehicle positions CityFlow logged at the end of each second,
// and between two logged seconds a straight-line interpolation of one vehicle's two positions.
// Signals, queues and decisions change only at logged seconds. Nothing else is invented.
//
// Time: second t holds positions at the end of t, the phase shown during (t-1, t] and the queue at
// the end of t. A decision logged at step s is taken at s and shapes the phase from s + 1 on.
const POS = 20, ANG = 1000;
const LAND = '#080b10', ASPHALT = '#1b2129', BOX = '#20272f';
const SIG = { green: '#22c55e', amber: '#f5a524', red: '#f43f5e', free: 'rgba(34,197,94,.55)' };
const AMB = '#ff3b3b';
const I = {
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 5v14l12-7z"/></svg>',
  pause: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>',
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 12a8 8 0 1 0 2.4-5.7M4 4v4h4"/></svg>',
  info: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/></svg>',
};

function b64(s, T) {
  const bin = atob(s), u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  return new T(u8.buffer);
}
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

export default function (component) {
  const { data, parentElement } = component;
  const host = parentElement.querySelector('.rp-host') || parentElement.appendChild(el('div', 'rp-host'));
  host.innerHTML = '';
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const T0 = data.t0, T1 = data.t1, NS = T1 - T0 + 1;
  const types = data.types, EM = types.indexOf(data.emergency);
  const dims = types.map((t) => data.dims[t]), tcol = types.map((t) => data.colours[t]);

  // ---- geometry ---------------------------------------------------------------------------------
  const roads = {};
  for (const r of data.geom.roads) {
    const dx = r.b[0] - r.a[0], dy = r.b[1] - r.a[1], len = Math.hypot(dx, dy);
    roads[r.id] = { ...r, ux: dx / len, uy: dy / len, nx: dy / len, ny: -dx / len, len };  // n: right-hand normal
  }
  const J = data.geom.junctions.map((j) => {
    const inRoad = {}, laneMoves = {};
    j.moves.forEach((m, mi) => { inRoad[m.approach] = m.road; ((laneMoves[m.road] ??= {})[m.lane] ??= []).push(mi); });
    const sets = {}; for (const [p, ms] of Object.entries(j.phases)) sets[p] = new Set(ms);
    return { ...j, inRoad, laneMoves, sets };
  });
  const jx = J.map((j) => j.x), jy = J.map((j) => j.y);
  const C = { x: (Math.min(...jx) + Math.max(...jx)) / 2, y: (Math.min(...jy) + Math.max(...jy)) / 2 };
  const SPAN = Math.max(Math.max(...jx) - Math.min(...jx), Math.max(...jy) - Math.min(...jy)) + 2 * 64;
  const HUD = 54;   // px at the top of each panel kept free for the run label and the timer
  const pt = (R, along, off) => [R.a[0] + R.ux * along + R.nx * off, R.a[1] + R.uy * along + R.ny * off];  // point on a road

  // ---- runs -------------------------------------------------------------------------------------
  const runs = data.runs.map((r) => {
    const idx = b64(r.veh.idx, Uint16Array), x = b64(r.veh.x, Int16Array), y = b64(r.veh.y, Int16Array), ang = b64(r.veh.ang, Int16Array);
    const off = new Int32Array(NS + 1);
    for (let k = 0; k < NS; k++) off[k + 1] = off[k] + r.veh.n[k];
    const nv = r.veh.flow.length, fi = r.veh.flow.indexOf(r.amb.flow);
    const fpos = new Array(NS).fill(null);
    for (let k = 0; k < NS; k++) for (let i = off[k]; i < off[k + 1]; i++) if (idx[i] === fi) { fpos[k] = [x[i] / POS, y[i] / POS]; break; }
    const ji = {}; r.intersections.forEach((id, i) => { ji[id] = i; });
    const amb = r.decisions.map((d) => d.amb.length > 0);
    return { ...r, idx, x, y, ang, off, nv, fi, fpos, ji, ambDec: amb, slot: new Int32Array(nv).fill(-1), slotK: -1, seen: new Uint8Array(nv) };
  });
  let qmax = 1;
  for (const r of runs) for (const s of r.queue) for (const j of s) for (const q of j) qmax = Math.max(qmax, q);
  const QM = Math.min(4.5, 150 / qmax);   // metres of queue bar per waiting vehicle, the same in both panels

  // ---- DOM --------------------------------------------------------------------------------------
  const root = host.appendChild(el('div', 'rp'));
  root.tabIndex = 0;
  const tool = root.appendChild(el('div', 'rp-tool'));
  const playBtn = tool.appendChild(el('button', 'rp-play')); playBtn.setAttribute('aria-label', 'Play'); playBtn.innerHTML = I.play;
  const backBtn = tool.appendChild(el('button', 'rp-ghost')); backBtn.innerHTML = I.back; backBtn.setAttribute('aria-label', 'Back to the start'); backBtn.title = 'Back to the start';
  const clock = tool.appendChild(el('span', 'rp-clock'));
  const seg = (label, opts, init, cls, on) => {
    tool.appendChild(el('span', 'rp-lab', label));
    const g = tool.appendChild(el('div', `rp-seg ${cls || ''}`)); g.setAttribute('role', 'group'); g.setAttribute('aria-label', label);
    for (const [v, t] of opts) {
      const b = g.appendChild(el('button', '', t)); b.setAttribute('aria-pressed', String(v === init));
      b.onclick = () => { g.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); on(v); };
    }
  };
  let speed = 5, mode = 'fit', side = 'left', zoom = 1;
  seg('Speed', [[1, '1×'], [2, '2×'], [5, '5×'], [10, '10×']], speed, 'mono', (v) => { speed = v; });
  seg('View', [['fit', 'Grid'], ['follow', 'Follow ambulance']], mode, '', (v) => { mode = v; pan = [0, 0]; dirty = true; });
  seg('Drive', [['left', 'Keep left'], ['sim', 'As simulated']], side, '', (v) => { side = v; dirty = true; });
  tool.appendChild(el('span', 'rp-sp'));
  const info = tool.appendChild(el('details', 'rp-info'));
  info.innerHTML = `<summary>${I.info}How it is drawn</summary><div class="pop">
    <p><b>Logged, then interpolated.</b> CityFlow logged every vehicle's position and heading at the end of each second while the run was replayed. Between two logged seconds a vehicle moves on the straight line between its two logged positions; vehicles that appear or leave fade in or out. No vehicle, position or second is invented.</p>
    <p><b>Signals and queues</b> change only at logged seconds: the phase shown during each second, and the waiting vehicles (speed below 0.1 m/s) per approach at its end. Queue bars run back from the stop line, ${QM.toFixed(1)} m per waiting vehicle in both panels.</p>
    <p><b>Keep left</b> draws the mirror image of CityFlow's right-hand network, which is how this project models India's left-hand traffic (docs/indian_scenario.md). Road names stay the simulator's (as in the LLM's prompts), so north is at the bottom; <b>As simulated</b> shows CityFlow's own layout.</p>
    <p><b>Sizes.</b> Vehicles are drawn to their length and width, never smaller than a few pixels; the selected ambulance is enlarged so it can be found.</p></div>`;

  const panels = root.appendChild(el('div', 'rp-panels'));
  const P = runs.map((r) => {
    const pn = panels.appendChild(el('div', 'rp-panel'));
    const cv = pn.appendChild(el('div', 'rp-canvas'));
    const canvas = cv.appendChild(el('canvas'));
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', `${r.label}: replay of the 2x2 grid`);
    const hud = cv.appendChild(el('div', 'rp-hud'));
    const who = hud.appendChild(el('div', 'rp-who'));
    const d = who.appendChild(el('span', 'd')); d.style.background = r.colour;
    who.appendChild(el('span', 'nm', r.short));
    if (r.exploratory) who.appendChild(el('span', 'ex', 'exploratory'));
    const timer = hud.appendChild(el('div', 'rp-timer wait'));
    const tk = timer.appendChild(el('span', 'k')); tk.appendChild(el('i')); const tkt = tk.appendChild(el('span', '', ''));
    const tv = timer.appendChild(el('span', 'v'));
    const zoomBox = cv.appendChild(el('div', 'rp-zoom'));
    const zin = zoomBox.appendChild(el('button', '', '+')), zout = zoomBox.appendChild(el('button', '', '−'));
    zin.setAttribute('aria-label', 'Zoom in'); zout.setAttribute('aria-label', 'Zoom out');
    zin.onclick = () => { zoom = clamp(zoom * 1.4, 0.6, 8); dirty = true; };
    zout.onclick = () => { zoom = clamp(zoom / 1.4, 0.6, 8); dirty = true; };
    const tip = cv.appendChild(el('div', 'rp-tip'));
    return { r, cv, canvas, ctx: canvas.getContext('2d'), timer, tkt, tv, tip, cam: null, w: 0, h: 0, drawn: [] };
  });

  // scrubber
  const scrub = root.appendChild(el('div', 'rp-scrub'));
  const track = scrub.appendChild(el('div', 'rp-track'));
  const fill = track.appendChild(el('div', 'rp-fill'));
  const pct = (t) => `${(100 * (t - T0)) / Math.max(1, T1 - T0)}%`;
  const mark = (t, cls, colour, label, flip) => {
    if (t == null || t < T0 || t > T1) return;
    const m = scrub.appendChild(el('div', `rp-mark ${cls}`)); m.style.left = pct(t); if (colour) m.style.background = colour;
    if (label) {
      const l = scrub.appendChild(el('div', `rp-mlab${flip ? ' flip' : ''}`, label)); l.style.left = pct(t);
      const u = (t - T0) / Math.max(1, T1 - T0);
      if (u > 0.85) l.classList.add('end'); else if (u < 0.15) l.classList.add('start');
    }
  };
  mark(runs[0].amb.start, 'amb', null, `ambulance starts ${runs[0].amb.start}`, false);
  runs.forEach((r, i) => mark(r.amb.finished, '', r.colour, `${r.short} arrives ${r.amb.finished}`, i === 1));
  runs.forEach((r, i) => r.decisions.forEach((d, k) => {
    if (!r.ambDec[k] || d.t < T0) return;
    const t = scrub.appendChild(el('div', 'rp-tick')); t.style.left = pct(d.t); t.style.background = r.colour; t.style.top = i ? '27px' : '12px';
  }));
  const range = scrub.appendChild(el('input', 'rp-range'));
  Object.assign(range, { type: 'range', min: T0, max: T1, step: 0.1, value: T0 }); range.setAttribute('aria-label', 'Time');

  // legend
  const legend = root.appendChild(el('div', 'rp-legend'));
  const chip = (html, text) => { const c = legend.appendChild(el('span', 'rp-chip')); c.innerHTML = html; c.appendChild(document.createTextNode(text)); };
  const nice = { motorcycle: 'two-wheeler', auto_rickshaw: 'auto', car: 'car', bus: 'bus', truck: 'truck', ambulance: 'ambulance' };
  types.forEach((t, i) => {
    const [L, W] = dims[i];
    const st = i === EM ? 'background:#fff;box-shadow:0 0 0 1.5px #ff3b3b,0 0 10px #ff3b3b' : `background:${tcol[i]}`;
    chip(`<span class="g" style="width:${Math.max(5, L * 2.2)}px;height:${Math.max(3, W * 2.6)}px;${st}"></span>`, nice[t] || t);
  });
  legend.appendChild(el('span', 'rp-sep'));
  chip(`<span class="sig" style="background:${SIG.green};box-shadow:0 0 6px ${SIG.green}"></span>`, 'green');
  chip(`<span class="sig" style="background:${SIG.amber};box-shadow:0 0 6px ${SIG.amber}"></span>`, 'yellow');
  chip(`<span class="sig" style="background:${SIG.red}"></span>`, 'red');
  chip(`<span class="sig" style="background:${SIG.free}"></span>`, 'free turn');
  legend.appendChild(el('span', 'rp-sep'));
  chip('<span class="q"></span>', 'queue');
  chip('<span class="tr"></span>', 'trail');

  // decision feeds
  const fbar = root.appendChild(el('div', 'rp-feedbar'));
  fbar.appendChild(el('span', 'rp-h2', 'Decisions'));
  const chk = (text, on) => {
    const l = fbar.appendChild(el('label', 'rp-check')); const c = l.appendChild(el('input')); c.type = 'checkbox';
    l.appendChild(document.createTextNode(text)); c.onchange = () => on(c.checked);
  };
  let ambOnly = false, raw = false;
  chk('Only decisions with an ambulance in view', (v) => { ambOnly = v; renderFeeds(); });
  chk('Show raw decision data', (v) => { raw = v; renderFeeds(); });
  const feeds = root.appendChild(el('div', 'rp-feeds'));
  const F = runs.map((r) => {
    const f = feeds.appendChild(el('div', 'rp-feed'));
    const h = f.appendChild(el('div', 'rp-feed-h'));
    const t = h.appendChild(el('div', 't')); const d = t.appendChild(el('span', 'd')); d.style.background = r.colour; t.appendChild(el('span', '', r.label));
    const c = h.appendChild(el('div', 'c'));
    const list = f.appendChild(el('div', 'rp-list'));
    let userScroll = 0;
    list.addEventListener('wheel', () => { userScroll = performance.now(); }, { passive: true });
    list.addEventListener('pointerdown', () => { userScroll = performance.now(); });
    return { r, list, c, cards: [], cur: -2, get userScroll() { return userScroll; } };
  });
  const jByLabel = {}; J.forEach((j) => { jByLabel[j.label] = j; });
  const fmtP = (v) => (v > 0 ? `+${v}` : `${v}`);

  function card(r, d) {
    const c = el('div', 'rp-card' + (d.amb.length ? ' amb' : ''));
    const top = c.appendChild(el('div', 'top'));
    top.appendChild(el('span', 'j', d.j));
    top.appendChild(el('span', 'tm', `t ${d.t}`));
    const act = top.appendChild(el('span', 'act', d.action === 'switch' ? 'switched to ' : d.action === 'keep' ? 'kept ' : ''));
    act.appendChild(el('b', '', d.label));
    for (const a of d.amb) top.appendChild(el('span', 'ab', `${a.movement} · ${a.distance_m.toFixed(0)} m`));
    const j = jByLabel[d.j];
    if (r.llm) {
      if (!d.ok) c.appendChild(el('div', 'why fail', `LLM call failed (${d.failure}); MaxPressure's choice applied`));
      else if (d.reason) c.appendChild(el('div', 'why q', d.reason));
      if (d.ok && d.llm_phase != null && d.llm_phase !== d.phase)
        c.appendChild(el('div', 'note', `The LLM picked ${j.labels[String(d.llm_phase)]}; the guard applied MaxPressure's ${d.label}.`));
    } else {
      const pr = d.pressures, keys = Object.keys(pr);
      if (keys.length) {
        const best = keys.reduce((a, b) => (pr[b] > pr[a] ? b : a));
        c.appendChild(el('div', 'note', `Pressure ${fmtP(pr[String(d.phase)])} for ${d.label}; highest ${fmtP(pr[best])} (${j.labels[best]}).`));
      }
    }
    if (raw) {
      const p = Object.entries(d.pressures).map(([k, v]) => `P${k} ${fmtP(v)}`).join(' · ');
      const lines = [`from P${d.from} after ${d.in_phase} s · applied P${d.phase}` + (d.allowed ? ` · allowed ${d.allowed.join(', ')}` : '')
        + (d.mp != null ? ` · MaxPressure P${d.mp}` : '') + (d.llm_phase != null ? ` · LLM P${d.llm_phase}` : '')
        + (d.latency_s != null ? ` · ${d.latency_s.toFixed(2)} s` : ''), p ? `pressures ${p}` : ''];
      c.appendChild(el('div', 'raw', lines.filter(Boolean).join('\n')));
    }
    return c;
  }
  function renderFeeds() {
    F.forEach((f) => {
      f.list.innerHTML = '';
      f.cards = [];
      f.r.decisions.forEach((d, k) => {
        if (ambOnly && !d.amb.length) return;
        const c = card(f.r, d);
        f.list.appendChild(c);
        f.cards.push([d.t, c]);
      });
      if (!f.cards.length) f.list.appendChild(el('div', 'rp-empty', 'No decision in this window.'));
      f.c.textContent = `${f.cards.length} shown`;
      f.cur = -2;
    });
    syncFeeds(true);
  }
  function syncFeeds(force) {
    F.forEach((f) => {
      let cur = -1;
      for (let i = 0; i < f.cards.length; i++) if (f.cards[i][0] <= tau) cur = i; else break;
      if (cur === f.cur && !force) return;
      f.cards.forEach(([t, c], i) => { c.classList.toggle('now', i === cur); c.classList.toggle('fut', t > tau); });
      f.cur = cur;
      if (cur >= 0 && (playing || force) && performance.now() - f.userScroll > 4000) {
        const c = f.cards[cur][1];
        f.list.scrollTop = Math.max(0, c.offsetTop - f.list.clientHeight * 0.45);
      }
    });
  }

  // ---- drawing ----------------------------------------------------------------------------------
  let tau = T0, playing = false, dirty = true, pan = [0, 0];
  const dpr = () => window.devicePixelRatio || 1;
  function resize() {
    for (const p of P) {
      const r = p.cv.getBoundingClientRect();
      p.w = r.width; p.h = r.height;
      p.canvas.width = Math.round(r.width * dpr()); p.canvas.height = Math.round(r.height * dpr());
    }
    dirty = true;
  }
  const fy = () => (side === 'left' ? 1 : -1);       // keep left = mirror image: screen y follows world y
  const toS = (p, x, y) => [p.w / 2 + (x - p.cam.x) * p.cam.s, p.h / 2 + fy() * (y - p.cam.y) * p.cam.s];
  const world = (p) => { const s = p.cam.s, k = dpr(); p.ctx.setTransform(k * s, 0, 0, k * fy() * s, k * (p.w / 2 - p.cam.x * s), k * (p.h / 2 - fy() * p.cam.y * s)); };
  const screen = (p) => p.ctx.setTransform(dpr(), 0, 0, dpr(), 0, 0);
  const lerpA = (a, b, f) => { const d = ((b - a + 3 * Math.PI) % (2 * Math.PI)) - Math.PI; return a + d * f; };

  function focusAt(r, t) {   // the selected ambulance's interpolated position at time t, or its nearest logged one
    const k = clamp(Math.floor(t - T0), 0, NS - 1), f = clamp(t - T0 - k, 0, 1), k2 = Math.min(NS - 1, k + 1);
    const a = r.fpos[k], b = r.fpos[k2];
    if (a && b) return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
    if (a) return a;
    if (b) return b;
    for (let d = 1; d < NS; d++) { if (k - d >= 0 && r.fpos[k - d]) return r.fpos[k - d]; if (k + d < NS && r.fpos[k + d]) return r.fpos[k + d]; }
    return null;
  }
  function camera(p, dt) {
    const fit = Math.min(p.w, p.h - HUD) / SPAN;
    let tx = C.x - pan[0], ty = C.y - pan[1], ts = fit * zoom;
    if (mode === 'follow') { const f = focusAt(p.r, tau); if (f) { tx = f[0]; ty = f[1]; } ts = Math.max(fit * zoom, 3.6 * zoom); }
    ty -= fy() * HUD / (2 * ts);   // content centred in the area below the HUD
    if (!p.cam) p.cam = { x: tx, y: ty, s: ts };
    const k = dt == null ? 1 : 1 - Math.exp(-dt * 7);
    p.cam.x += (tx - p.cam.x) * k; p.cam.y += (ty - p.cam.y) * k; p.cam.s += (ts - p.cam.s) * k;
    return Math.abs(tx - p.cam.x) + Math.abs(ty - p.cam.y) > 0.05 || Math.abs(ts - p.cam.s) > 0.001;
  }

  function sigState(j, r, kph, mi) {
    const m = j.moves[mi];
    if (m.turn === 'free') return 'free';
    const ji = r.ji[j.id], p = r.phase[kph][ji], g = r.green[kph][ji];
    if (p === j.transition) return j.sets[String(g)].has(mi) ? 'amber' : 'red';
    return j.sets[String(p)].has(mi) ? 'green' : 'red';
  }

  function drawStatic(p, px) {
    const c = p.ctx;
    // asphalt
    c.fillStyle = ASPHALT;
    for (const R of Object.values(roads)) {
      const w = R.lanes * R.lw, s0 = R.wa, s1 = R.len - R.wb;
      const a = pt(R, s0, 0), b = pt(R, s1, 0), b2 = pt(R, s1, w), a2 = pt(R, s0, w);
      c.beginPath(); c.moveTo(...a); c.lineTo(...b); c.lineTo(...b2); c.lineTo(...a2); c.closePath(); c.fill();
    }
    for (const j of J) { c.fillStyle = BOX; c.fillRect(j.x - j.w, j.y - j.w, 2 * j.w, 2 * j.w); }
    // markings
    c.lineCap = 'butt';
    for (const R of Object.values(roads)) {
      const s0 = R.wa, s1 = R.len - R.wb;
      c.lineWidth = Math.max(0.16, 1 * px);
      if (px < 0.45) {   // lane dashes only when zoomed in enough to read them
        c.strokeStyle = 'rgba(230,237,243,.32)';
        c.setLineDash([3, 4.5]);
        for (let l = 1; l < R.lanes; l++) { c.beginPath(); c.moveTo(...pt(R, s0, l * R.lw)); c.lineTo(...pt(R, s1, l * R.lw)); c.stroke(); }
        c.setLineDash([]);
      }
      c.strokeStyle = 'rgba(230,237,243,.22)';
      c.beginPath(); c.moveTo(...pt(R, s0, R.lanes * R.lw)); c.lineTo(...pt(R, s1, R.lanes * R.lw)); c.stroke();
      c.strokeStyle = 'rgba(245,165,36,.45)';
      c.lineWidth = Math.max(0.2, 1.2 * px);
      c.beginPath(); c.moveTo(...pt(R, s0, 0.15)); c.lineTo(...pt(R, s1, 0.15)); c.stroke();
    }
    // zebra crossings just outside each junction box
    c.fillStyle = 'rgba(230,237,243,.13)';
    for (const j of J) for (const rid of Object.values(j.inRoad)) {
      const R = roads[rid], w = R.lanes * R.lw;
      for (let o = -w + 0.5; o < w; o += 1.6) {
        const q0 = pt(R, R.len - R.wb - 3.2, o), q1 = pt(R, R.len - R.wb - 3.2, o + 0.8), q2 = pt(R, R.len - R.wb - 0.8, o + 0.8), q3 = pt(R, R.len - R.wb - 0.8, o);
        c.beginPath(); c.moveTo(...q0); c.lineTo(...q1); c.lineTo(...q2); c.lineTo(...q3); c.closePath(); c.fill();
      }
    }
  }

  function drawRoute(p, px) {
    const c = p.ctx, rt = p.r.amb.route;
    c.save();
    c.strokeStyle = 'rgba(255,170,170,.22)'; c.lineWidth = Math.max(0.5, 1.4 * px); c.setLineDash([6 * Math.max(px, 0.25), 6 * Math.max(px, 0.25)]); c.lineJoin = 'round';
    c.beginPath();
    rt.forEach((id, i) => {
      const R = roads[id]; if (!R) return;
      const o = R.lw * Math.min(1.5, R.lanes / 2), a = pt(R, R.wa, o), b = pt(R, R.len - R.wb, o);
      if (i === 0) c.moveTo(...a); else c.lineTo(...a);
      c.lineTo(...b);
    });
    c.stroke(); c.restore();
  }

  function drawSignals(p, px, kph, kq) {
    const c = p.ctx, r = p.r;
    for (const j of J) {
      const ji = r.ji[j.id];
      // movement paths of the green (or yellow) phase
      for (let mi = 0; mi < j.moves.length; mi++) {
        const st = sigState(j, r, kph, mi);
        if (st !== 'green' && st !== 'amber') continue;
        const pts = j.moves[mi].pts;
        c.save();
        c.strokeStyle = st === 'green' ? 'rgba(34,197,94,.6)' : 'rgba(245,165,36,.6)';
        c.lineWidth = Math.max(0.5, 1.6 * px); c.lineCap = 'round'; c.lineJoin = 'round';
        c.beginPath(); c.moveTo(...pts[0]); for (const q of pts.slice(1)) c.lineTo(...q); c.stroke();
        const [x2, y2] = pts[pts.length - 1], [x1, y1] = pts[pts.length - 2], a = Math.atan2(y2 - y1, x2 - x1), h = Math.max(1.4, 5 * px);
        c.fillStyle = c.strokeStyle; c.beginPath(); c.moveTo(x2, y2);
        c.lineTo(x2 - h * Math.cos(a - 0.5), y2 - h * Math.sin(a - 0.5)); c.lineTo(x2 - h * Math.cos(a + 0.5), y2 - h * Math.sin(a + 0.5)); c.closePath(); c.fill();
        c.restore();
      }
      // queue bars, outside the kerb of each incoming road
      r.approaches.forEach((app, ai) => {
        const rid = j.inRoad[app]; if (!rid) return;
        const R = roads[rid], q = r.queue[kq][ji][ai]; if (!q) return;
        const end = R.len - R.wb - 1, L = Math.min(q * QM, R.len - R.wb - R.wa - 4), o = R.lanes * R.lw + 1.7;
        c.save(); c.strokeStyle = 'rgba(244,63,94,.9)'; c.lineCap = 'round'; c.lineWidth = Math.max(1.6, 3.2 * px);
        c.shadowColor = 'rgba(244,63,94,.7)'; c.shadowBlur = 8;
        c.beginPath(); c.moveTo(...pt(R, end, o)); c.lineTo(...pt(R, end - L, o)); c.stroke(); c.restore();
      });
      // stop lines, one per incoming lane, coloured by its movement's signal
      for (const [rid, lanes] of Object.entries(j.laneMoves)) {
        const R = roads[rid], s = R.len - R.wb - 0.6;
        for (const [lane, mis] of Object.entries(lanes)) {
          const st = sigState(j, r, kph, mis[0]);
          c.save(); c.strokeStyle = SIG[st]; c.lineWidth = Math.max(0.9, 3 * px); c.lineCap = 'round';
          if (st === 'green' || st === 'amber') { c.shadowColor = SIG[st]; c.shadowBlur = 12; }
          c.beginPath(); c.moveTo(...pt(R, s, +lane * R.lw + 0.35)); c.lineTo(...pt(R, s, (+lane + 1) * R.lw - 0.35)); c.stroke(); c.restore();
        }
      }
    }
  }

  function rrect(c, x, y, w, h, r) { c.beginPath(); if (c.roundRect) c.roundRect(x, y, w, h, r); else c.rect(x, y, w, h); }

  function drawVehicles(p, px, now) {
    const c = p.ctx, r = p.r;
    const u = clamp(tau - T0, 0, NS - 1), ka = Math.floor(u), kb = Math.min(NS - 1, ka + 1), f = kb === ka ? 0 : u - ka;
    if (r.slotK !== kb) { r.slot.fill(-1); for (let i = r.off[kb]; i < r.off[kb + 1]; i++) r.slot[r.idx[i]] = i; r.slotK = kb; }
    r.seen.fill(0);
    const drawn = [];
    let focus = null;
    const one = (vi, x, y, a, alpha) => {
      const ty = r.veh.type[vi];
      if (vi === r.fi) { focus = [x, y, a, alpha]; return; }
      let [L, W] = dims[ty];
      if (ty === EM) { L *= 1.2; W *= 1.2; }
      L = Math.max(L, 4.2 * px); W = Math.max(W * 1.15, 2.2 * px);
      c.save(); c.translate(x, y); c.rotate(a); c.globalAlpha = alpha;
      c.fillStyle = tcol[ty]; rrect(c, -L, -W / 2, L, W, Math.min(W / 2, 0.55)); c.fill();
      if (ty === EM) { c.fillStyle = AMB; c.fillRect(-L * 0.62, -W / 2, L * 0.12, W); }
      c.restore();
      drawn.push([x, y, vi]);
    };
    for (let i = r.off[ka]; i < r.off[ka + 1]; i++) {
      const vi = r.idx[i], j = r.slot[vi];
      const x0 = r.x[i] / POS, y0 = r.y[i] / POS, a0 = r.ang[i] / ANG;
      r.seen[vi] = 1;
      if (j >= 0 && kb !== ka) one(vi, x0 + (r.x[j] / POS - x0) * f, y0 + (r.y[j] / POS - y0) * f, lerpA(a0, r.ang[j] / ANG, f), 1);
      else one(vi, x0, y0, a0, kb === ka ? 1 : 1 - f);
    }
    if (kb !== ka) for (let i = r.off[kb]; i < r.off[kb + 1]; i++) if (!r.seen[r.idx[i]]) one(r.idx[i], r.x[i] / POS, r.y[i] / POS, r.ang[i] / ANG, f);
    p.drawn = drawn;
    // the selected ambulance: trail of its logged positions, then the vehicle itself
    const hist = [];
    for (let k = 0; k <= ka; k++) if (r.fpos[k]) hist.push(r.fpos[k]);
    if (focus) hist.push([focus[0], focus[1]]);
    if (hist.length > 1) {
      c.save(); c.lineCap = 'round'; c.lineJoin = 'round';
      const n = hist.length;
      for (let i = 1; i < n; i++) {
        c.strokeStyle = `rgba(255,59,59,${(0.08 + 0.75 * (i / n) ** 1.5).toFixed(3)})`;
        c.lineWidth = Math.max(0.8, 3.2 * px);
        c.beginPath(); c.moveTo(...hist[i - 1]); c.lineTo(...hist[i]); c.stroke();
      }
      c.restore();
    }
    if (focus) {
      const [x, y, a, alpha] = focus, [L0, W0] = dims[EM];
      const L = Math.max(L0 * 1.6, 11 * px), W = Math.max(W0 * 1.5, 5.5 * px);
      const pulse = reduce ? 0.5 : 0.5 + 0.5 * Math.sin(now / 160);
      c.save(); c.translate(x, y); c.globalAlpha = alpha;
      const g = c.createRadialGradient(-L / 2 * Math.cos(a), -L / 2 * Math.sin(a), 0, -L / 2 * Math.cos(a), -L / 2 * Math.sin(a), L * (1.3 + 0.5 * pulse));
      g.addColorStop(0, 'rgba(255,59,59,.55)'); g.addColorStop(1, 'rgba(255,59,59,0)');
      c.fillStyle = g; c.beginPath(); c.arc(-L / 2 * Math.cos(a), -L / 2 * Math.sin(a), L * (1.3 + 0.5 * pulse), 0, 2 * Math.PI); c.fill();
      c.rotate(a);
      c.shadowColor = 'rgba(255,255,255,.9)'; c.shadowBlur = 10;
      c.fillStyle = '#ffffff'; rrect(c, -L, -W / 2, L, W, Math.min(W / 3, 0.9)); c.fill();
      c.shadowBlur = 0;
      c.fillStyle = AMB; c.fillRect(-L * 0.78, -W / 2, L * 0.1, W); c.fillRect(-L * 0.4, -W / 2, L * 0.1, W);
      const on = reduce ? true : Math.floor(now / 230) % 2 === 0;
      c.fillStyle = on ? '#ff2d2d' : '#3b82f6'; c.shadowColor = c.fillStyle; c.shadowBlur = 16;
      c.fillRect(-L * 0.62, -W * 0.36, L * 0.14, W * 0.72);
      c.restore();
    }
    return focus;
  }

  function drawLabels(p, kph, kq) {
    const c = p.ctx, r = p.r;
    screen(p);
    c.textBaseline = 'middle';
    const cs = toS(p, C.x, C.y);
    for (const j of J) {
      const ji = r.ji[j.id], ph = r.phase[kph][ji], tr = ph === j.transition;
      // label in the land quadrant between this junction and the grid's centre (never off the panel's edge)
      const js = toS(p, j.x, j.y), sx = Math.sign(cs[0] - js[0]) || 1, sy = Math.sign(cs[1] - js[1]) || 1;
      const corner = toS(p, j.x + Math.sign(C.x - j.x || 1) * j.w, j.y + Math.sign(C.y - j.y || 1) * j.w);
      const lab = tr ? 'yellow' : j.labels[String(ph)];
      c.font = '600 11px "Geist Mono", ui-monospace, monospace';
      const w1 = c.measureText(j.label).width;
      c.font = '500 11px Geist, system-ui, sans-serif';
      const w2 = c.measureText(lab).width, W = w1 + w2 + 22;
      // labels that extend leftwards sit one row further in, so two labels meeting in the middle never overlap
      const dy = 16 + (sx < 0 ? 24 : 0);
      const x = sx > 0 ? corner[0] + 6 : corner[0] - 6 - W, y = sy > 0 ? corner[1] + dy : corner[1] - dy;
      if (y >= HUD + 6) {   // not under the run label and the timer
        c.fillStyle = 'rgba(7,9,13,.8)'; rrect(c, x, y - 10, W, 20, 6); c.fill();
        c.strokeStyle = tr ? 'rgba(245,165,36,.55)' : 'rgba(34,197,94,.45)'; c.lineWidth = 1; c.stroke();
        c.fillStyle = '#e6edf3'; c.font = '600 11px "Geist Mono", ui-monospace, monospace'; c.fillText(j.label, x + 7, y);
        c.fillStyle = tr ? SIG.amber : '#86efac'; c.font = '500 11px Geist, system-ui, sans-serif'; c.fillText(lab, x + 14 + w1, y);
      }
      // queue counts at the far end of each bar
      r.approaches.forEach((app, ai) => {
        const rid = j.inRoad[app]; if (!rid) return;
        const R = roads[rid], q = r.queue[kq][ji][ai]; if (!q) return;
        const L = Math.min(q * QM, R.len - R.wb - R.wa - 4), o = R.lanes * R.lw + 1.7;
        const [qx, qy] = toS(p, ...pt(R, R.len - R.wb - 1 - L - 3.5, o));
        c.font = '600 10.5px "Geist Mono", ui-monospace, monospace';
        const t = String(q), tw = c.measureText(t).width;
        c.fillStyle = 'rgba(244,63,94,.92)'; rrect(c, qx - tw / 2 - 4, qy - 8, tw + 8, 16, 5); c.fill();
        c.fillStyle = '#fff'; c.fillText(t, qx - tw / 2, qy + 0.5);
      });
    }
    // compass: the simulator's north, which points down in the mirrored (keep-left) view
    const up = side === 'left' ? 1 : -1, cx = 26, cy = p.h - (up > 0 ? 44 : 28);
    c.fillStyle = 'rgba(7,9,13,.8)'; c.beginPath(); c.arc(cx, cy, 13, 0, 2 * Math.PI); c.fill();
    c.strokeStyle = 'rgba(255,255,255,.14)'; c.lineWidth = 1; c.stroke();
    c.fillStyle = '#19e6d2'; c.beginPath(); c.moveTo(cx, cy + up * 10); c.lineTo(cx - 3.5, cy); c.lineTo(cx + 3.5, cy); c.closePath(); c.fill();
    c.fillStyle = '#3a475a'; c.beginPath(); c.moveTo(cx, cy - up * 10); c.lineTo(cx - 3.5, cy); c.lineTo(cx + 3.5, cy); c.closePath(); c.fill();
    c.textAlign = 'center'; c.font = '700 10px Geist, system-ui, sans-serif';
    c.fillStyle = '#19e6d2'; c.fillText('N', cx, cy + up * 20);
    c.fillStyle = '#a3afbd'; c.fillText('E', cx + 21, cy + 0.5);
    c.textAlign = 'left';
    if (side === 'left') { c.font = '500 10px Geist, system-ui, sans-serif'; c.fillStyle = '#7d8896'; c.fillText('mirrored', cx + 30, cy + 0.5); }
  }

  function drawGrid(p) {
    const c = p.ctx;
    screen(p);
    c.fillStyle = LAND; c.fillRect(0, 0, p.w, p.h);
    const step = 25 * p.cam.s;
    if (step < 8) return;
    c.strokeStyle = 'rgba(148,163,184,.045)'; c.lineWidth = 1;
    const [ox, oy] = toS(p, 0, 0);
    c.beginPath();
    for (let x = ((ox % step) + step) % step; x < p.w; x += step) { c.moveTo(Math.round(x) + 0.5, 0); c.lineTo(Math.round(x) + 0.5, p.h); }
    for (let y = ((oy % step) + step) % step; y < p.h; y += step) { c.moveTo(0, Math.round(y) + 0.5); c.lineTo(p.w, Math.round(y) + 0.5); }
    c.stroke();
  }

  function drawPanel(p, now) {
    const px = 1 / p.cam.s, u = clamp(tau - T0, 0, NS - 1);
    const kph = clamp(Math.ceil(u), 0, NS - 1), kq = Math.floor(u);
    drawGrid(p);
    world(p);
    drawStatic(p, px);
    drawRoute(p, px);
    drawSignals(p, px, kph, kq);
    drawVehicles(p, px, now);
    drawLabels(p, kph, kq);
    // ambulance timer
    const a = p.r.amb, T = p.timer;
    if (tau < a.start) { T.className = 'rp-timer wait'; p.tkt.textContent = 'ambulance starts in'; p.tv.innerHTML = `${Math.ceil(a.start - tau)}<small>s</small>`; }
    else if (a.finished == null || tau < a.finished) { T.className = 'rp-timer run'; p.tkt.textContent = 'ambulance en route'; p.tv.innerHTML = `${Math.floor(tau - a.start)}<small>s</small>`; }
    else { T.className = 'rp-timer done'; p.tkt.textContent = 'arrived · travel time'; p.tv.innerHTML = `${a.travel}<small>s</small>`; }
  }

  // ---- loop -------------------------------------------------------------------------------------
  let raf = 0, last = performance.now(), lastFlash = 0;
  function setPlaying(v) { playing = v; playBtn.innerHTML = v ? I.pause : I.play; playBtn.setAttribute('aria-label', v ? 'Pause' : 'Play'); if (v && tau >= T1) tau = T0; }
  playBtn.onclick = () => setPlaying(!playing);
  backBtn.onclick = () => { tau = T0; dirty = true; syncFeeds(true); };
  range.oninput = () => { tau = +range.value; dirty = true; syncFeeds(true); };
  root.onkeydown = (e) => {
    if (e.target.closest && e.target.closest('input, button, label')) return;
    if (e.key === ' ') { e.preventDefault(); setPlaying(!playing); }
    else if (e.key === 'ArrowRight') { tau = Math.min(T1, Math.floor(tau) + 1); dirty = true; syncFeeds(true); }
    else if (e.key === 'ArrowLeft') { tau = Math.max(T0, Math.ceil(tau) - 1); dirty = true; syncFeeds(true); }
  };
  function frame(now) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    if (playing) { tau = Math.min(T1, tau + dt * speed); if (tau >= T1) setPlaying(false); dirty = true; }
    let moving = false;
    for (const p of P) if (p.w) moving = camera(p, dt) || moving;
    const flash = !reduce && now - lastFlash > 110;
    if (!(dirty || moving || flash)) return;
    if (flash) lastFlash = now;
    for (const p of P) if (p.w) drawPanel(p, now);
    if (dirty) {
      range.value = tau;
      fill.style.width = pct(tau);
      clock.innerHTML = `t ${tau.toFixed(1)} s<small>${tau >= runs[0].amb.start ? `+${(tau - runs[0].amb.start).toFixed(0)} s since the ambulance's start` : ''}</small>`;
      syncFeeds(false);
    }
    dirty = false;
  }

  // hover a vehicle, drag to pan
  P.forEach((p) => {
    let drag = null;
    p.canvas.onpointerdown = (e) => { if (mode !== 'fit') return; drag = [e.clientX, e.clientY, pan[0], pan[1]]; p.cv.classList.add('drag'); p.canvas.setPointerCapture(e.pointerId); };
    p.canvas.onpointerup = () => { drag = null; p.cv.classList.remove('drag'); };
    p.canvas.onpointermove = (e) => {
      if (drag) { pan = [drag[2] + (e.clientX - drag[0]) / p.cam.s, drag[3] + fy() * (e.clientY - drag[1]) / p.cam.s]; dirty = true; p.tip.style.display = 'none'; return; }
      const b = p.canvas.getBoundingClientRect(), mx = e.clientX - b.left, my = e.clientY - b.top;
      let best = null, bd = 14 * 14;
      for (const [x, y, vi] of p.drawn) { const [sx, sy] = toS(p, x, y), d = (sx - mx) ** 2 + (sy - my) ** 2; if (d < bd) { bd = d; best = vi; } }
      if (best == null) { p.tip.style.display = 'none'; return; }
      p.tip.textContent = `${nice[types[p.r.veh.type[best]]] || types[p.r.veh.type[best]]} · flow_${p.r.veh.flow[best]}_0`;
      p.tip.style.left = `${mx}px`; p.tip.style.top = `${my}px`; p.tip.style.display = 'block';
    };
    p.canvas.onpointerleave = () => { p.tip.style.display = 'none'; };
  });

  const ro = new ResizeObserver(resize);
  P.forEach((p) => ro.observe(p.cv));
  resize();
  renderFeeds();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { dirty = true; });
  raf = requestAnimationFrame(frame);
  return () => { cancelAnimationFrame(raf); ro.disconnect(); };
}
