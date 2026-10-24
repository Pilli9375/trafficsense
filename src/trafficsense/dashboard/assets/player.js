// Live Detection player: plays the frames the detector just processed, draws its boxes on a canvas
// (class colours; click a class to hide it), and shows the per-class count of every frame.
// Everything it shows comes from `data`, measured on this machine by views/detection.py.
const PLAY = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 5v14l12-7z"/></svg>';
const PAUSE = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';

export default function (component) {
  const { data, parentElement } = component;
  const host = parentElement.querySelector('.pl-host') || parentElement.appendChild(Object.assign(document.createElement('div'), { className: 'pl-host' }));
  const n = data.frames.length;
  const s = data.stats;
  const classes = data.present;
  host.innerHTML = `
  <div class="pl">
    <div class="pl-grid">
      <div class="pl-card">
        <div class="pl-stage"><canvas></canvas><div class="pl-tip"></div></div>
        <div class="pl-bar">
          <button class="pl-btn" aria-label="Play">${PLAY}</button>
          <input class="pl-range" type="range" min="0" max="${n - 1}" value="0" step="1" aria-label="Frame">
          <span class="pl-time"></span>
          <div class="pl-seg" role="group" aria-label="Speed"></div>
        </div>
      </div>
      <div class="pl-card pl-side">
        <div><div class="pl-h">This frame <span class="pl-hud"></span></div>
        <div class="pl-now"></div><div class="pl-hint">Click a class to hide its boxes.</div></div>
        <div><div class="pl-h">Per frame <span>boxes per class</span></div>
        <div class="pl-chart"><svg preserveAspectRatio="none"></svg></div></div>
      </div>
    </div>
    <div class="pl-stats"></div>
    <div class="pl-note"></div>
  </div>`;
  const $ = (q) => host.querySelector(q);
  const canvas = $('canvas'), ctx = canvas.getContext('2d'), stage = $('.pl-stage'), tip = $('.pl-tip');
  const btn = $('.pl-btn'), range = $('.pl-range'), time = $('.pl-time'), hud = $('.pl-hud');
  const off = new Set();
  let k = 0, playing = false, speed = 1, raf = 0, last = 0, hover = null;

  // stats tiles: measured now
  const tiles = [
    ['Detector speed', s.detector_fps.toFixed(1), 'FPS', 'pre-process + inference + NMS'],
    ['Latency per frame', s.latency_ms_mean.toFixed(1), 'ms', `p95 ${s.latency_ms_p95.toFixed(1)} ms`],
    ['End to end', s.e2e_fps.toFixed(1), 'FPS', 'decode, detect, encode'],
    ['Device', s.device_short, '', s.device_detail],
  ];
  $('.pl-stats').innerHTML = tiles.map(([k_, v, u, sub]) =>
    `<div class="pl-stat"><div class="k"><span class="pl-live"></span>${k_}</div><div class="v">${v}<small>${u}</small></div><div class="s"></div></div>`).join('');
  host.querySelectorAll('.pl-stat .s').forEach((e, i) => { e.textContent = tiles[i][3]; });
  $('.pl-note').textContent = `${n} of ${s.n_total || n} frames · ${data.label} · measured on this machine, not stored. ` +
    'Counts are boxes per frame (no tracking): a vehicle seen in ten frames counts ten times.';

  // speed buttons
  const seg = $('.pl-seg');
  [0.5, 1, 2, 4].forEach((v) => {
    const b = document.createElement('button');
    b.textContent = `${v}×`; b.setAttribute('aria-pressed', String(v === speed));
    b.onclick = () => { speed = v; seg.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); };
    seg.appendChild(b);
  });

  // frames
  const imgs = data.frames.map((src) => { const im = new Image(); im.src = src; return im; });
  const counts = (i) => {
    const c = {}; classes.forEach((name) => { c[name] = 0; });
    for (const b of data.boxes[i]) { const name = data.classes[b[4]]; if (name in c) c[name] += 1; }
    return c;
  };
  const series = classes.map((name) => data.boxes.map((bs) => bs.filter((b) => data.classes[b[4]] === name).length));
  const maxCount = Math.max(1, ...series.flat());

  // per-class rows
  const now = $('.pl-now');
  classes.forEach((name) => {
    const r = document.createElement('div');
    r.className = 'pl-row'; r.setAttribute('role', 'button'); r.tabIndex = 0;
    r.innerHTML = `<span class="n"><span class="sw" style="background:${data.colours[name]}"></span></span><span class="tr"><i style="background:${data.colours[name]}"></i></span><span class="v"></span>`;
    r.querySelector('.n').appendChild(document.createTextNode(name));
    const toggle = () => { off.has(name) ? off.delete(name) : off.add(name); r.classList.toggle('off', off.has(name)); draw(); chart(); };
    r.onclick = toggle; r.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } };
    r.dataset.cls = name;
    now.appendChild(r);
  });

  function fit() {
    const r = stage.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(r.width * dpr); canvas.height = Math.round(r.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return r;
  }
  let view = fit();
  function geom() {  // contain the frame in the stage
    const sc = Math.min(view.width / data.w, view.height / data.h);
    return { sc, ox: (view.width - data.w * sc) / 2, oy: (view.height - data.h * sc) / 2 };
  }
  function rr(x, y, w, h, r) { ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, h, r) : ctx.rect(x, y, w, h); }

  function draw() {
    const { sc, ox, oy } = geom();
    ctx.clearRect(0, 0, view.width, view.height);
    const im = imgs[k];
    if (im.complete && im.naturalWidth) ctx.drawImage(im, ox, oy, data.w * sc, data.h * sc);
    else im.onload = () => draw();
    ctx.font = '600 11px "Geist Mono", ui-monospace, monospace';
    data.boxes[k].forEach((b, i) => {
      const name = data.classes[b[4]];
      if (off.has(name) || !(name in data.colours)) return;
      const x = ox + b[0] * sc, y = oy + b[1] * sc, w = (b[2] - b[0]) * sc, h = (b[3] - b[1]) * sc;
      const col = data.colours[name], hot = hover === i;
      ctx.save();
      if (hot) { ctx.shadowColor = col; ctx.shadowBlur = 14; }
      ctx.lineWidth = hot ? 3 : 1.8; ctx.strokeStyle = col; rr(x, y, w, h, 3); ctx.stroke();
      ctx.fillStyle = col + (hot ? '33' : '14'); ctx.fill();
      ctx.restore();
      if (w > 26 || hot) {
        const label = `${name} ${b[5].toFixed(2)}`, tw = ctx.measureText(label).width + 10;
        const ly = y - 17 < oy ? y + 1 : y - 17, lx = Math.min(x, ox + data.w * sc - tw);   // keep the label on the frame
        ctx.fillStyle = col; rr(lx, ly, tw, 16, 4); ctx.fill();
        ctx.fillStyle = '#ffffff'; ctx.fillText(label, lx + 5, ly + 12);
      }
    });
    // HUD and side panel
    const c = counts(k);
    const shown = data.boxes[k].filter((b) => !off.has(data.classes[b[4]])).length;
    hud.textContent = `${shown} boxes`;
    now.querySelectorAll('.pl-row').forEach((r) => {
      const v = c[r.dataset.cls];
      r.querySelector('.v').textContent = v;
      r.querySelector('i').style.width = `${(100 * v) / maxCount}%`;
    });
    range.value = k;
    time.textContent = `frame ${k + 1} / ${n} · ${(k / data.fps).toFixed(2)} s`;
    chart();
  }

  function chart() {
    const svg = $('.pl-chart svg'), W = 300, H = 150, pl = 22, pb = 16;
    const x = (i) => pl + (n === 1 ? 0 : (i / (n - 1)) * (W - pl - 4)), y = (v) => H - pb - (v / maxCount) * (H - pb - 6);
    let out = `<line x1="${pl}" y1="${H - pb}" x2="${W}" y2="${H - pb}" stroke="#1d2532"/>`;
    [0, maxCount].forEach((v) => { out += `<text x="${pl - 6}" y="${y(v) + 4}" fill="#7d8896" font-size="10" text-anchor="end" font-family="Geist Mono, monospace">${v}</text>`; });
    classes.forEach((name, j) => {
      if (off.has(name)) return;
      const pts = series[j].map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
      out += `<polyline points="${pts}" fill="none" stroke="${data.colours[name]}" stroke-width="1.6" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`;
    });
    out += `<line x1="${x(k)}" y1="4" x2="${x(k)}" y2="${H - pb}" stroke="#19e6d2" stroke-width="1.2" vector-effect="non-scaling-stroke"/>`;
    out += `<text x="${pl}" y="${H - 2}" fill="#7d8896" font-size="10" font-family="Geist Mono, monospace">frame 1</text>`;
    out += `<text x="${W}" y="${H - 2}" fill="#7d8896" font-size="10" text-anchor="end" font-family="Geist Mono, monospace">frame ${n}</text>`;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.innerHTML = out;
  }
  $('.pl-chart').onclick = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    k = Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width) * (n - 1)))); draw();
  };

  function setPlaying(p) { playing = p; btn.innerHTML = p ? PAUSE : PLAY; btn.setAttribute('aria-label', p ? 'Pause' : 'Play'); last = performance.now(); }
  btn.onclick = () => setPlaying(!playing);
  range.oninput = () => { k = +range.value; draw(); };
  function loop(t) {
    raf = requestAnimationFrame(loop);
    if (!playing) return;
    if (t - last >= 1000 / (data.fps * speed)) { last = t; k = (k + 1) % n; draw(); }
  }
  raf = requestAnimationFrame(loop);

  // hover a box
  canvas.onmousemove = (e) => {
    const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top, { sc, ox, oy } = geom();
    let best = null, area = Infinity;
    data.boxes[k].forEach((b, i) => {
      if (off.has(data.classes[b[4]])) return;
      const x1 = ox + b[0] * sc, y1 = oy + b[1] * sc, x2 = ox + b[2] * sc, y2 = oy + b[3] * sc;
      if (mx >= x1 && mx <= x2 && my >= y1 && my <= y2 && (x2 - x1) * (y2 - y1) < area) { best = i; area = (x2 - x1) * (y2 - y1); }
    });
    if (best !== hover) { hover = best; draw(); }
    if (best === null) { tip.style.display = 'none'; return; }
    const b = data.boxes[k][best];
    tip.textContent = `${data.classes[b[4]]} · confidence ${b[5].toFixed(2)}`;
    tip.style.left = `${mx}px`; tip.style.top = `${my}px`; tip.style.display = 'block';
  };
  canvas.onmouseleave = () => { hover = null; tip.style.display = 'none'; draw(); };
  const ro = new ResizeObserver(() => { view = fit(); draw(); });
  ro.observe(stage);
  draw();
  return () => { cancelAnimationFrame(raf); ro.disconnect(); };
}
