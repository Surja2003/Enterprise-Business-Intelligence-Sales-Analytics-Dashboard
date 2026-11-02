"use strict";
/* Web version of the Power BI report. All figures come from docs/data.json, exported from the model by tools/build_site.py. */
const GOLD = "#d6ac58", TEAL = "#58a6a6", CORAL = "#e77d67", PURPLE = "#956bc4", EMERALD = "#65c99a", GREY = "#a5a5a5";
const PAGES = [
  ["executive", "Executive Overview"], ["amazon", "Amazon Sales"], ["international", "International Sales"], ["products", "Products and Stock"],
  ["pricing", "Marketplace Pricing"], ["expenses", "Expenses and Cash"], ["logistics", "Logistics"], ["notes", "Data Notes"],
];
const STATE = { year: "", quarter: "", month: "", segment: "", grain: "Month" };
let D = null;

/* ---------- formatting ---------- */
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const big = v => !v && v !== 0 ? "—" : Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(1) + "M" : Math.abs(v) >= 1e3 ? (v / 1e3).toFixed(1) + "K" : Math.round(v).toLocaleString("en-IN");
const rs = v => v === null || v === undefined || (!v && v !== 0) ? "—" : "₹" + big(v);
const rsFull = v => v === null || v === undefined ? "" : "₹" + Math.round(v).toLocaleString("en-IN");
const int = v => v === null || v === undefined ? "" : Math.round(v).toLocaleString("en-IN");
const pct = (v, d = 1) => v === null || v === undefined || !isFinite(v) ? "" : (v * 100).toFixed(d) + "%";
const signed = v => (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%";
const div = (a, b) => (b ? a / b : null);
const sum = (arr, f = x => x) => arr.reduce((t, x) => t + (f(x) || 0), 0);
const dateLabel = d => new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/* ---------- filter logic ---------- */
function period() {
  const s = new Set();
  D.months.forEach((m, i) => { if ((!STATE.year || m.y === STATE.year) && (!STATE.quarter || m.q === STATE.quarter) && (!STATE.month || m.m === STATE.month)) s.add(i); });
  return s;
}
const monthOf = date => D._ymIndex[date.slice(0, 4) + date.slice(5, 7)];
function amzDays(p) { return D.amzDay.filter(r => p.has(monthOf(r[0]))); }
function intDays(p) { return D.intDay.filter(r => p.has(monthOf(r[0]))); }
function amz(p) {
  const days = amzDays(p), f = i => sum(days, r => r[i]);
  return { days, s: f(1) || null, u: f(2) || null, o: f(3) || null, a: f(4) || null, c: f(5) || null, r: f(6) || null, p: f(7) || null, sh: f(8) || null, d: f(9) || null };
}
function intl(p) {
  const rows = D.int.month.filter(r => p.has(r[0])), f = i => sum(rows, r => r[i]);
  const custs = new Set(D.int.customer.r.filter(r => p.has(r[0])).map(r => r[1]));
  return { rows, s: f(1) || null, u: f(2) || null, l: f(3), rate: div(f(4), f(5)), customers: custs.size };
}
function dimTotals(dim, p, idx = 2) {
  const m = new Map();
  for (const r of dim.r) if (p.has(r[0])) m.set(r[1], (m.get(r[1]) || 0) + (r[idx] || 0));
  return [...m].map(([k, v]) => [dim.k[k], v]).filter(x => x[1] > 0).sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
}
function bottom(dim, p, n) {
  const m = new Map();
  for (const r of dim.r) if (p.has(r[0])) { const e = m.get(r[1]) || [0, 0]; e[0] += r[2]; e[1] += r[3]; m.set(r[1], e); }
  return [...m].filter(([, v]) => v[0] > 0).map(([k, v]) => [dim.k[k], v[1], v[0]]).sort((a, b) => a[2] - b[2] || String(a[0]).localeCompare(String(b[0]))).slice(0, n);
}
function skuTotals(p) {
  const m = new Map();
  for (const r of D.sku.r) if (p.has(r[0])) {
    const e = m.get(r[1]) || { k: r[1], s: 0, u: 0, o: 0, a: 0, c: 0, r: 0, is: 0, iu: 0 };
    e.s += r[2]; e.u += r[3]; e.o += r[4]; e.a += r[5]; e.c += r[6]; e.r += r[7]; e.is += r[8]; e.iu += r[9]; m.set(r[1], e);
  }
  return [...m.values()];
}
function outcome(rows) {
  const order = ["Cancelled", "Returned / Failed", "In Progress", "Recognised Sale"], m = {};
  rows.forEach(r => { m[r[1]] = (m[r[1]] || 0) + r[2]; });
  return order.filter(k => m[k]).map(k => [k, m[k]]);
}
function latestGrowth(p) {
  const days = amzDays(p).filter(r => r[1]);
  if (!days.length) return null;
  const last = days[days.length - 1][0], cy = +last.slice(0, 4), cm = +last.slice(5, 7);
  const py = cm === 1 ? cy - 1 : cy, pm = cm === 1 ? 12 : cm - 1;
  const inMonth = (y, mm) => D.amzDay.filter(r => +r[0].slice(0, 4) === y && +r[0].slice(5, 7) === mm && r[1]);
  const cur = inMonth(cy, cm), pri = inMonth(py, pm);
  if (pri.length < 20) return { none: true };
  const c = sum(cur, r => r[1]), q = sum(pri, r => r[1]);
  const lab = (y, mm) => new Date(y, mm - 1, 1).toLocaleDateString("en-GB", { month: "short" }) + " " + String(y).slice(2);
  return { mom: c / q - 1, perDay: (c / cur.length) / (q / pri.length) - 1, label: lab(cy, cm) + " vs " + lab(py, pm) };
}
function spanLabel(prefix, days) {
  return days.length ? `${prefix} · ${dateLabel(days[0][0])} to ${dateLabel(days[days.length - 1][0])}` : "No data in selection";
}

/* ---------- small html builders ---------- */
function spark(values, color) {
  const v = values.filter(x => x > 0);
  if (v.length < 2) return "";
  const w = 180, h = 34, min = Math.min(...v), max = Math.max(...v);
  const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(h - 3 - (x - min) / Math.max(max - min, 1) * (h - 8)).toFixed(1)}`).join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polygon points="0,${h} ${pts} ${w},${h}" fill="${color}" fill-opacity=".12"/><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>`;
}
function kpi(label, value, sub, color = GOLD, series = null, small = false) {
  const shown = value === null || value === undefined || value === "" ? "—" : value;
  return `<div class="kpi" style="--c:${color}"><div class="l">${esc(label)}</div><div class="v${small ? " small" : ""}">${esc(shown)}</div><div class="s">${esc(sub || "")}</div>${series ? spark(series, color) : ""}</div>`;
}
const card = (span, title, sub, body, extraHead = "") => `<section class="card ${span}"><div class="card-head"><div><h2>${esc(title)}</h2>${sub ? `<p class="sub">${esc(sub)}</p>` : ""}</div>${extraHead}</div><div class="body">${body}</div></section>`;
const empty = (t = "No data in this selection") => `<p class="empty">${esc(t)}</p>`;

function bars(rows, { color = GOLD, fmt = rs, link = null, title = "" } = {}) {
  if (!rows.length) return empty();
  const max = Math.max(...rows.map(r => r[1]));
  return `<div class="bars" role="list">${rows.map(r => {
    const label = esc(r[0]), tip = esc(`${r[0]}\n${title ? title + ": " : ""}${fmt(r[1])}`), w = Math.max(r[1] / max * 76, .4);
    const inner = `<span class="name">${label}</span><span class="track"><span class="fill" style="width:${w}%;background:${color}"></span><span class="num">${esc(fmt(r[1]))}</span></span>`;
    return link ? `<a class="bar-row" role="listitem" href="${link(r[0])}" data-tip="${tip}\nClick for detail">${inner}</a>` : `<div class="bar-row" role="listitem" data-tip="${tip}">${inner}</div>`;
  }).join("")}</div>`;
}
function table(cols, rows, tall = false) {
  if (!rows.length) return empty();
  return `<div class="table-wrap${tall ? " tall" : ""}"><table><thead><tr>${cols.map(c => `<th scope="col"${c.txt ? ' class="txt"' : ""}>${esc(c.t)}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((v, i) => `<td${cols[i].txt ? ' class="txt"' : ""}>${cols[i].html ? v : esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function legend(items) { return `<div class="legend">${items.map(([n, c]) => `<span><i style="background:${c}"></i>${esc(n)}</span>`).join("")}</div>`; }

/* Stacked or grouped columns on one axis. points: {label, vals:[n,...], tip} */
function columns(points, series, { height = 250, mode = "stack", fmt = rs, width = 760, money = true } = {}) {
  if (!points.length) return empty();
  const W = width, H = height, L = 46, B = 26, T = 8, plot = H - B - T;
  const max = Math.max(...points.map(p => mode === "stack" ? sum(p.vals) : Math.max(...p.vals))) || 1;
  const step = niceStep(max), top = Math.ceil(max / step) * step, y = v => T + plot - v / top * plot;
  let g = "";
  for (let t = 0; t <= top + step / 2; t += step) g += `<line class="gridline" x1="${L}" x2="${W}" y1="${y(t)}" y2="${y(t)}"/><text x="${L - 6}" y="${y(t) + 3}" text-anchor="end">${money ? "₹" : ""}${big(t)}</text>`;
  const band = (W - L) / points.length, bw = Math.min(band * .62, 56), every = Math.ceil(points.length / Math.floor((W - L) / 58));
  points.forEach((p, i) => {
    const cx = L + band * (i + .5);
    if (mode === "stack") {
      let base = 0;
      p.vals.forEach((v, s) => { if (!v) return; const y1 = y(base + v), hh = Math.max(y(base) - y1 - (base ? 2 : 0), 1); g += `<rect class="mark" x="${cx - bw / 2}" y="${y1}" width="${bw}" height="${hh}" rx="${s === p.vals.length - 1 || !p.vals[s + 1] ? 3 : 0}" fill="${series[s][1]}" data-tip="${esc(p.tip || `${p.label}\n${series[s][0]}: ${fmt(v)}`)}"/>`; base += v; });
    } else {
      const each = bw / p.vals.length;
      p.vals.forEach((v, s) => { if (!v) return; g += `<rect class="mark" x="${cx - bw / 2 + s * each + 1}" y="${y(v)}" width="${each - 2}" height="${T + plot - y(v)}" rx="3" fill="${series[s][1]}" data-tip="${esc(`${p.label}\n${series[s][0]}: ${fmt(v)}`)}"/>`; });
    }
    if (i % every === 0) g += `<text x="${cx}" y="${H - 8}" text-anchor="middle">${esc(p.label)}</text>`;
  });
  return `${series.length > 1 ? legend(series) : ""}<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Column chart">${g}</svg></div>`;
}
function niceStep(max) { const r = max / 4, e = 10 ** Math.floor(Math.log10(r)), n = r / e; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * e; }

function waterfall(rows) {
  if (!rows.length) return empty();
  const total = sum(rows, r => r[1]), colors = { "All recorded value": "#6e6e6e", Cancelled: CORAL, "Returned / Failed": CORAL, "In Progress": GREY, "Recognised Sale": GOLD };
  let run = total;
  const items = [["All recorded value", 0, total], ...rows.map(([k, v]) => { const hi = k === "Recognised Sale" ? v : run, lo = k === "Recognised Sale" ? 0 : run - v; if (k !== "Recognised Sale") run -= v; return [k, lo, hi]; })];
  return `<div class="bars">${items.map(([k, lo, hi]) => {
    const size = hi - lo, text = `${rs(size)} · ${pct(size / total)}`;
    return `<div class="bar-row" data-tip="${esc(`${k}\n${rsFull(size)} (${pct(size / total)} of recorded value)`)}"><span class="name">${esc(k)}</span><span class="track" style="position:relative;display:block;height:30px"><span class="fill" style="position:absolute;top:7px;left:${lo / total * 70}%;width:${Math.max(size / total * 70, .5)}%;background:${colors[k]};border-radius:4px"></span><span class="num" style="position:absolute;top:8px;left:calc(${hi / total * 70}% + 6px)">${esc(text)}</span></span></div>`;
  }).join("")}</div>`;
}
function calendar(days) {
  const rows = days.filter(r => r[1]);
  if (!rows.length) return empty();
  const first = new Date(rows[0][0] + "T00:00:00"), start = new Date(first); start.setDate(first.getDate() - first.getDay());
  const lastD = new Date(rows[rows.length - 1][0] + "T00:00:00"), weeks = Math.floor((lastD - start) / 6048e5) + 1, max = Math.max(...rows.map(r => r[1]));
  const W = 400, L = 30, T = 18, cw = (W - L) / weeks, ch = Math.min(cw, 26), H = T + ch * 7 + 2;
  let g = "", lastMonth = "";
  ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].forEach((d, i) => { g += `<text x="${L - 5}" y="${T + ch * i + ch / 2 + 3}" text-anchor="end">${d}</text>`; });
  for (let w = 0; w < weeks; w += 1) {
    const dt = new Date(start.getTime() + w * 6048e5), mon = dt.toLocaleDateString("en-GB", { month: "short" });
    if (mon !== lastMonth && (w < weeks - 1)) { g += `<text x="${L + cw * w}" y="10">${mon}</text>`; lastMonth = mon; }
  }
  for (const r of rows) {
    const dt = new Date(r[0] + "T00:00:00"), w = Math.floor((dt - start) / 6048e5), t = r[1] / max;
    const mix = (a, b) => Math.round(a + (b - a) * t), fill = `rgb(${mix(0x2b, 0xd6)},${mix(0x24, 0xac)},${mix(0x16, 0x58)})`;
    g += `<rect class="mark" x="${L + cw * w + 1}" y="${T + ch * dt.getDay() + 1}" width="${cw - 2}" height="${ch - 2}" rx="3" fill="${fill}" data-tip="${esc(`${dateLabel(r[0])}\nRecorded sales: ${rsFull(r[1])}`)}"/>`;
  }
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Daily sales calendar">${g}</svg></div>`;
}
function coverage(p) {
  const months = D.months.map((m, i) => [m, i]).filter(([, i]) => p.has(i));
  const amzM = {}, intM = {};
  amzDays(p).forEach(r => { amzM[monthOf(r[0])] = (amzM[monthOf(r[0])] || 0) + r[1]; });
  D.int.month.filter(r => p.has(r[0])).forEach(r => { intM[r[0]] = r[1]; });
  const rowsAll = [];
  if (!STATE.segment || STATE.segment === "Amazon") rowsAll.push(["Amazon", amzM, GOLD]);
  if (!STATE.segment || STATE.segment === "International") rowsAll.push(["International", intM, TEAL]);
  const rows = rowsAll.filter(r => sum(Object.values(r[1])) > 0);
  if (!rows.length) return empty();
  const total = sum(rows, r => sum(Object.values(r[1])));
  const W = 420, L = 118, B = 46, rowH = 88, H = rows.length * rowH + B, cw = (W - L) / months.length;
  let g = "";
  rows.forEach(([name, vals, color], ri) => {
    const peak = Math.max(...Object.values(vals)), seg = sum(Object.values(vals));
    g += `<text x="${L - 8}" y="${ri * rowH + rowH / 2 - 2}" text-anchor="end" style="fill:#f2f2f2;font-size:12px;font-weight:600">${name}</text><text x="${L - 8}" y="${ri * rowH + rowH / 2 + 13}" text-anchor="end" style="font-size:11px">${pct(seg / total)} of sales</text>`;
    months.forEach(([m, i], ci) => { if (vals[i] > 0) g += `<rect class="mark" x="${L + ci * cw + 1}" y="${ri * rowH + 2}" width="${Math.max(cw - 2, 1)}" height="${rowH - 4}" rx="3" fill="${color}" opacity="${.3 + .7 * vals[i] / peak}" data-tip="${esc(`${name}, ${m.label}\nRecorded sales: ${rsFull(vals[i])}`)}"/>`; });
  });
  months.forEach(([m], ci) => { if (months.length <= 14) g += `<text transform="translate(${L + ci * cw + cw / 2 + 3},${rows.length * rowH + 8}) rotate(-55)" text-anchor="end" style="font-size:9px">${esc(m.label)}</text>`; });
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Sales share and months covered by each segment">${g}</svg></div>`;
}
function concentrationCurve(values) {
  const v = values.slice().sort((a, b) => b - a);
  if (v.length < 2) return empty("Needs at least two customers");
  const total = sum(v), W = 460, H = 280, L = 38, B = 32, T = 8, R = 12;
  const x = i => L + (i - 1) / (v.length - 1) * (W - L - R), y = s => T + (1 - s) * (H - T - B);
  let run = 0; const pts = v.map((a, i) => { run += a; return [i + 1, run / total]; });
  let g = "";
  [0, .25, .5, .75, 1].forEach(t => { g += `<line class="gridline" x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/><text x="${L - 6}" y="${y(t) + 3}" text-anchor="end">${t * 100}%</text>`; });
  const line = pts.map(p => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  g += `<polygon points="${x(1)},${y(0)} ${line} ${x(v.length)},${y(0)}" fill="${TEAL}" fill-opacity=".14"/><polyline points="${line}" fill="none" stroke="${TEAL}" stroke-width="2"/>`;
  [1, 10].filter(n => n <= v.length).forEach(n => {
    const p = pts[n - 1];
    g += `<circle cx="${x(n)}" cy="${y(p[1])}" r="5" fill="${GOLD}" stroke="#141414" stroke-width="2"/><text x="${x(n) + 9}" y="${y(p[1]) + 14}" style="fill:#f2f2f2;font-weight:600">Top ${n}: ${pct(p[1])}</text>`;
  });
  pts.forEach(p => { g += `<circle class="mark" cx="${x(p[0])}" cy="${y(p[1])}" r="7" fill="transparent" data-tip="Top ${p[0]} customer${p[0] > 1 ? "s" : ""}\n${pct(p[1])} of sales"/>`; });
  g += `<text x="${(W + L) / 2}" y="${H - 6}" text-anchor="middle">Customers, largest first (${v.length})</text>`;
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Cumulative share of sales by customer rank">${g}</svg></div>`;
}
function histogram(values) {
  if (!values.length) return empty();
  const size = 250, maxV = Math.max(...values), n = Math.ceil((maxV + 1) / size), counts = new Array(n).fill(0);
  values.forEach(v => { counts[Math.floor(v / size)] += 1; });
  return columns(counts.map((c, i) => ({ label: "₹" + big(i * size), vals: [c], tip: `MRP ₹${int(i * size)} to ₹${int((i + 1) * size - 1)}\n${c} products` })), [["Products", PURPLE]], { height: 300, width: 780, fmt: int, money: false });
}

/* ---------- shared page parts ---------- */
function header(eyebrow, title, right, back = false) {
  return `<header class="head"><div>${back ? `<button class="back" type="button" data-back>← Back to previous page</button>` : ""}<p class="eyebrow">${esc(eyebrow)}</p><h1>${esc(title)}</h1></div><div class="period">${esc(right)}</div></header>`;
}
function filters(segment = false) {
  const opt = (vals, cur) => `<option value="">All</option>` + vals.map(v => `<option value="${esc(v)}"${v === cur ? " selected" : ""}>${esc(v)}</option>`).join("");
  const uniq = f => [...new Set(D.months.map(f))];
  const order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const f = (id, label, vals, cur) => `<div class="filter"><label for="f-${id}">${label}</label><select id="f-${id}" data-filter="${id}">${opt(vals, cur)}</select></div>`;
  return `<div class="filters">${f("year", "Year", uniq(m => m.y).sort(), STATE.year)}${f("quarter", "Quarter", uniq(m => m.q).sort(), STATE.quarter)}${f("month", "Month", uniq(m => m.m).sort((a, b) => order.indexOf(a) - order.indexOf(b)), STATE.month)}${segment ? f("segment", "Sales segment", ["Amazon", "International"], STATE.segment) : ""}</div>`;
}
function grainButtons() {
  return `<div class="seg" role="group" aria-label="Time grain">${["Month", "Quarter", "Year", "Day"].map(g => `<button type="button" data-grain="${g}" aria-pressed="${STATE.grain === g}">${g}</button>`).join("")}</div>`;
}
function trendPoints(p, useA, useI) {
  const key = { Month: m => m.ym, Quarter: m => `${m.y} ${m.q}`, Year: m => m.y };
  if (STATE.grain === "Day") {
    const m = new Map();
    if (useA) amzDays(p).forEach(r => { if (r[1]) (m.get(r[0]) || m.set(r[0], [0, 0]).get(r[0]))[0] = r[1]; });
    if (useI) intDays(p).forEach(r => { if (r[1]) (m.get(r[0]) || m.set(r[0], [0, 0]).get(r[0]))[1] = r[1]; });
    return [...m].sort((a, b) => a[0].localeCompare(b[0])).map(([d, v]) => ({ label: new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "2-digit" }), vals: v }));
  }
  const m = new Map();
  D.months.forEach((mo, i) => {
    if (!p.has(i)) return;
    const k = key[STATE.grain](mo), label = STATE.grain === "Month" ? mo.label : k, e = m.get(k) || { label, vals: [0, 0] };
    if (useA) e.vals[0] += sum(amzDays(new Set([i])), r => r[1]);
    if (useI) e.vals[1] += sum(D.int.month.filter(r => r[0] === i), r => r[1]);
    m.set(k, e);
  });
  return [...m.values()].filter(e => e.vals[0] || e.vals[1]);
}
function monthlySeries(p, fn) { return D.months.map((m, i) => (p.has(i) ? fn(i) : 0)); }
const toSku = s => `#/sku/${encodeURIComponent(s)}`;
const toMarket = m => `#/marketplace/${encodeURIComponent(m)}`;

function topSkus(p) { return skuTotals(p).filter(e => e.u > 0).sort((a, b) => b.u - a.u || D.sku.k[a.k].localeCompare(D.sku.k[b.k])).slice(0, 15); }

/* ---------- pages ---------- */
const VIEWS = {
  executive() {
    const p = period(), A = amz(p), I = intl(p), seg = STATE.segment;
    const useA = !seg || seg === "Amazon", useI = !seg || seg === "International";
    const total = (useA ? A.s || 0 : 0) + (useI ? I.s || 0 : 0), both = (A.s || 0) + (I.s || 0), g = latestGrowth(p);
    const span = [...(useA ? A.days : []), ...(useI ? intDays(p) : [])].map(r => r[0]).sort();
    const right = span.length ? `${seg || "Amazon + International"} · ${dateLabel(span[0])} to ${dateLabel(span[span.length - 1])}` : "No data in selection";
    const amzM = monthlySeries(p, i => sum(amzDays(new Set([i])), r => r[1])), intM = monthlySeries(p, i => sum(D.int.month.filter(r => r[0] === i), r => r[1]));
    const notSel = "Segment not selected";
    const kpis = [
      kpi("Total Recorded Sales", total ? rs(total) : "—", total ? "Periods differ by segment" : "No data in selection", GOLD, amzM.map((v, i) => (useA ? v : 0) + (useI ? intM[i] : 0))),
      kpi("Amazon Recorded Sales", useA ? rs(A.s) : "—", !useA ? notSel : A.s ? `${pct(div(A.s, both))} of recorded sales` : "No data in selection", GOLD, useA ? A.days.map(r => r[1]) : null),
      kpi("International Recorded Sales", useI ? rs(I.s) : "—", !useI ? notSel : I.s ? `${pct(div(I.s, both))} of recorded sales` : "No data in selection", TEAL, useI ? intM : null),
      kpi("Amazon Orders", useA ? big(A.o) : "—", !useA ? notSel : A.o ? `Avg order ₹${int(A.s / A.o)}` : "No data in selection", GOLD, useA ? A.days.map(r => r[3]) : null),
      kpi("Amazon Units Sold", useA ? big(A.u) : "—", !useA ? notSel : A.u ? `Avg price ₹${int(A.s / A.u)}` : "No data in selection", GOLD, useA ? A.days.map(r => r[2]) : null),
      kpi("International Units", useI ? big(I.u) : "—", !useI ? notSel : I.u ? `${int(I.customers)} customers` : "No data in selection", TEAL, useI ? monthlySeries(p, i => sum(D.int.month.filter(r => r[0] === i), r => r[2])) : null),
      growthCard(g, useA, A),
      kpi("Recorded Expenses", rs(sum(D.expenses, e => e[1])), "IIGF event sheet only", PURPLE),
    ].join("");
    const styles = dimTotals(D.dims.style, p), top = styles.slice(0, 10), low = bottom(D.dims.style, p, 10);
    const monthly = D.months.map((m, i) => [m, i]).filter(([, i]) => p.has(i)).map(([m, i]) => {
      const a = sum(amzDays(new Set([i])), r => r[1]), v = sum(D.int.month.filter(r => r[0] === i), r => r[1]), prevDays = i > 0 ? amzDays(new Set([i - 1])).filter(r => r[1]) : [];
      const mom = a && prevDays.length >= 20 ? a / sum(prevDays, r => r[1]) - 1 : null;
      return [m.label, a ? rsFull(a) : "", v ? rsFull(v) : "", mom === null ? "" : (mom * 100).toFixed(1) + "%"];
    }).filter(r => r[1] || r[2]);
    return header("Sales and business performance", "Executive Overview", right) + filters(true) + `<div class="kpis">${kpis}</div><div class="grid">`
      + card("s8", "Recorded sales over time", "Amazon and International stay separate. Switch the time grain at top right.", columns(trendPoints(p, useA, useI), [["Amazon", GOLD], ["International", TEAL]], { height: 270 }), grainButtons())
      + card("s4", "Sales contribution and coverage by segment", "Share of recorded sales. Cells mark months with sales.", coverage(p))
      + card("s3", "Top 10 styles", "Amazon recorded sales", useA ? bars(top, { title: "Sales" }) : empty("Amazon segment not selected"))
      + card("s3", "Lowest 10 selling styles", "Amazon styles with at least one recognised sale", useA ? table([{ t: "Style", txt: 1 }, { t: "Units" }, { t: "Sales" }], low.map(r => [r[0], int(r[1]), rsFull(r[2])])) : empty("Amazon segment not selected"))
      + card("s3", "Sales performance by month", "Blank growth means no comparable prior month", table([{ t: "Month", txt: 1 }, { t: "Amazon" }, { t: "International" }, { t: "MoM" }], monthly))
      + `<section class="card s3 insights"><div class="card-head"><h2>Key business insights</h2></div><div class="body">${execInsights(p, A, I, styles, g)}</div></section></div>`;
  },
  amazon() {
    const p = period(), A = amz(p), none = "No data in selection";
    const kpis = [
      kpi("Amazon Recorded Sales", rs(A.s), A.s ? `${pct(div(A.s, (A.s || 0) + (intl(p).s || 0)))} of recorded sales` : none, GOLD, A.days.map(r => r[1])),
      kpi("Amazon Orders", big(A.o), A.o ? `Avg order ₹${int(A.s / A.o)}` : none, GOLD, A.days.map(r => r[3])),
      kpi("Amazon Units Sold", big(A.u), A.u ? `Avg price ₹${int(A.s / A.u)}` : none, GOLD, A.days.map(r => r[2])),
      kpi("Average Order Value", A.o ? "₹" + int(A.s / A.o) : "—", A.o ? "Recognised sales ÷ orders" : none),
      kpi("Average Selling Price", A.u ? "₹" + int(A.s / A.u) : "—", A.u ? "Recognised sales ÷ units" : none),
      kpi("Cancelled Orders", big(A.c), A.a ? `${pct(div(A.c, A.a))} of all orders` : none, CORAL, A.days.map(r => r[5])),
      kpi("Shipped Orders", big(A.sh), A.a ? "Status: Shipped" : none, EMERALD, A.days.map(r => r[8])),
      kpi("Delivered to Buyer", big(A.d), A.a ? "Status: Delivered" : none, EMERALD, A.days.map(r => r[9])),
    ].join("");
    const styles = dimTotals(D.dims.style, p), units = dimTotals(D.dims.style, p, 3);
    const cancelledValue = sum(D.amzStatus.filter(r => p.has(r[0]) && r[1] === "Cancelled"), r => r[2]);
    return header("Marketplace performance", "Amazon Sales Intelligence", spanLabel("Amazon", A.days)) + filters() + `<div class="kpis">${kpis}</div><div class="grid">`
      + card("s6", "Recorded sales over time", "Amazon recognised sales only", columns(trendPoints(p, true, false).map(t => ({ label: t.label, vals: [t.vals[0]] })), [["Amazon", GOLD]], { height: 230, width: 640 }), grainButtons())
      + card("s6", "Where order value went", "7,566 cancelled lines have no Amount, so cancelled value is understated", waterfall(outcome(D.amzStatus.filter(r => p.has(r[0])))))
      + card("s6", "Daily sales calendar", "Brighter days sold more. Hover a day for its value.", calendar(A.days))
      + card("s3", "Fulfilment", "Recognised sales", bars(dimTotals(D.dims.fulfil, p), { title: "Sales" }))
      + card("s3", "Business buyer (B2B)", "True means a business buyer", bars(dimTotals(D.dims.b2b, p), { title: "Sales" }))
      + card("s3", "Top 10 styles by sales", "", bars(styles.slice(0, 10), { title: "Sales" }))
      + card("s3", "Top 10 styles by units", "", bars(units.slice(0, 10), { fmt: int, title: "Units" }))
      + card("s3", "Lowest 10 selling styles", "", table([{ t: "Style", txt: 1 }, { t: "Units" }, { t: "Sales" }], bottom(D.dims.style, p, 10).map(r => [r[0], int(r[1]), rsFull(r[2])])))
      + card("s3", "Sales by category", "", bars(dimTotals(D.dims.category, p), { title: "Sales" }))
      + card("s3", "Top 10 states", "State spellings standardised", bars(dimTotals(D.dims.state, p).slice(0, 10), { title: "Sales" }))
      + card("s3", "Top 10 cities", "", bars(dimTotals(D.dims.city, p).slice(0, 10), { title: "Sales" }))
      + card("s3", "Sales by size", "", bars(dimTotals(D.dims.size, p), { title: "Sales" }))
      + `<section class="card s3 insights"><div class="card-head"><h2>Reading this page</h2></div><div class="body"><p>Sales count only Shipped and Delivered orders.</p>${A.a ? `<p class="warn">Cancelled value not counted: ${rs(cancelledValue)}</p><p class="muted">In progress orders not counted: ${int(A.p || 0)}</p><p class="muted">Returned or failed orders: ${int(A.r || 0)}</p>` : `<p class="muted">No Amazon orders in this selection.</p>`}<h3>Scope</h3><p class="muted">Nearly every order ships to India, so a country chart would add nothing and is left out. The 29 Jun cut-off makes June slightly short.</p></div></section></div>`;
  },
  international() {
    const p = period(), I = intl(p), none = "No data in selection", cust = dimTotals(D.int.customer, p);
    const days = intDays(p), best = I.rows.slice().sort((a, b) => b[1] - a[1])[0];
    const kpis = [
      kpi("International Recorded Sales", rs(I.s), I.s ? `${pct(div(I.s, (amz(p).s || 0) + I.s))} of recorded sales` : none, TEAL, monthlySeries(p, i => sum(D.int.month.filter(r => r[0] === i), r => r[1]))),
      kpi("International Units", big(I.u), I.u ? `${int(I.customers)} customers` : none, TEAL, monthlySeries(p, i => sum(D.int.month.filter(r => r[0] === i), r => r[2]))),
      kpi("Customers", I.customers ? int(I.customers) : "—", I.customers ? "Distinct billed names, masked" : none, TEAL),
      kpi("Realised Value per Piece", I.u ? "₹" + int(I.s / I.u) : "—", I.u ? "GROSS AMT ÷ PCS" : none, TEAL),
      kpi("Average Listed Rate", I.rate ? "₹" + int(I.rate) : "—", I.rate ? "Mean of RATE per line" : none, TEAL),
      kpi("Discount vs Listed", I.s && I.l ? pct(1 - I.s / I.l) : "—", I.s ? "GROSS AMT vs PCS × RATE" : none, PURPLE),
      kpi("Top Customer Share", cust.length ? pct(cust[0][1] / sum(cust, c => c[1])) : "—", cust.length ? cust[0][0] : none, PURPLE),
      kpi("Peak Month", best ? D.months[best[0]].label : "—", best ? "Highest recorded sales" : none, TEAL, null, true),
    ].join("");
    const skus = skuTotals(p).filter(e => e.is > 0).sort((a, b) => b.is - a.is || D.sku.k[a.k].localeCompare(D.sku.k[b.k])).slice(0, 10).map(e => [D.sku.k[e.k], e.is]);
    return header("Multi-channel export ledger", "International Sales Intelligence", spanLabel("International", days)) + filters() + `<div class="kpis">${kpis}</div><div class="grid">`
      + card("s5", "Recorded sales over time", "Original GROSS AMT values", columns(trendPoints(p, false, true).map(t => ({ label: t.label, vals: [t.vals[1]], tip: `${t.label}\nRecorded sales: ${rsFull(t.vals[1])}` })), [["International", TEAL]], { height: 290, width: 560 }), grainButtons())
      + card("s4", "Customer concentration", "Cumulative share of sales. Ranks only.", concentrationCurve(cust.map(c => c[1])))
      + card("s3", "Top 10 customers", "Names masked as Customer 001 by total sales", bars(cust.slice(0, 10), { color: TEAL, title: "Sales" }))
      + card("s3", "Top 10 styles", "", bars(dimTotals(D.int.style, p).slice(0, 10), { color: TEAL, title: "Sales" }))
      + card("s3", "Lowest 10 styles", "", table([{ t: "Style", txt: 1 }, { t: "Units" }, { t: "Sales" }], bottom(D.int.style, p, 10).map(r => [r[0], int(r[1]), rsFull(r[2])])))
      + card("s3", "Top 10 SKUs", "Click a SKU for detail. Apr to May rows have no SKU.", bars(skus, { color: TEAL, link: toSku, title: "Sales" }))
      + card("s3", "Sales by size", "", bars(dimTotals(D.int.size, p), { color: TEAL, title: "Sales" }))
      + `<section class="card s12 insights"><div class="card-head"><h2>Limits of this data</h2></div><div class="body"><p>Multi-channel export ledger, not Amazon only.</p><p class="warn">No channel, city, state or country field exists, so none is inferred.</p><p class="muted">Sales use original GROSS AMT. PCS × RATE is kept separately. May 2022 ends on the 11th, so that month is partial. Currency is not stated in the file: rupees are an assumption.</p></div></section></div>`;
  },
  products() {
    const p = period(), A = amz(p), rows = skuTotals(p).filter(e => e.a > 0), matched = rows.filter(e => D.sku.stock[e.k] !== null), none = "No data in selection";
    const matchedUnits = sum(matched, e => e.u), n = rows.length;
    const kpis = [
      kpi("Amazon SKUs Sold or Listed", n ? big(n) : "—", n ? `${int(D.stock.catalogue)} in stock catalogue` : none),
      kpi("Recorded Stock (Units)", big(D.stock.total), "A snapshot, not units sold", TEAL),
      kpi("Amazon Units Sold", big(A.u), A.u ? "Recognised orders only" : none, GOLD, A.days.map(r => r[2])),
      kpi("SKUs Matched to Stock", n ? big(matched.length) : "—", n ? `${pct(matched.length / n)} coverage` : none, EMERALD),
      kpi("SKUs Without Stock Record", n ? big(n - matched.length) : "—", n ? "Not forced to match" : none, CORAL),
      kpi("Units on Matched SKUs", matchedUnits ? big(matchedUnits) : "—", A.u ? `${pct(matchedUnits / A.u)} of Amazon units` : none),
    ].join("");
    const cats = D.stock.cat.slice().sort((a, b) => b[1] - a[1]).slice(0, 8);
    const pts = cats.map(([c, s]) => ({ label: c, vals: [s, sum(D.stock.units.filter(r => r[1] === c && p.has(r[0])), r => r[2])] }));
    const top = topSkus(p).map(e => [`<a href="${toSku(D.sku.k[e.k])}">${esc(D.sku.k[e.k])}</a>`, int(e.u), rsFull(e.s), D.sku.stock[e.k] === null ? "" : int(D.sku.stock[e.k])]);
    return header("Amazon sales against recorded stock", "Product Performance and Inventory", spanLabel("Amazon", A.days)) + filters() + `<div class="kpis">${kpis}</div><div class="grid">`
      + card("s7", "Recorded stock and units sold, top 8 categories", "Only SKUs present in both tables. Stock is one undated snapshot.", columns(pts, [["Recorded stock", TEAL], ["Units sold", GOLD]], { mode: "group", fmt: int, money: false, height: 280 }))
      + card("s5", "Top 15 SKUs by units sold", "Click a SKU for detail. Blank stock means no stock record.", table([{ t: "SKU", txt: 1, html: 1 }, { t: "Units sold" }, { t: "Sales" }, { t: "Recorded stock" }], top))
      + card("s3", "Amazon sales by category", "", bars(dimTotals(D.dims.category, p), { title: "Sales" }))
      + card("s3", "Recorded stock by size", "", bars(D.stock.size.slice().sort((a, b) => b[1] - a[1]), { color: TEAL, fmt: big, title: "Stock" }))
      + card("s3", "Top 10 colours by stock", "", bars(D.stock.colour.slice().sort((a, b) => b[1] - a[1]).slice(0, 10), { color: TEAL, fmt: big, title: "Stock" }))
      + `<section class="card s3 insights"><div class="card-head"><h2>Reading this page</h2></div><div class="body">${n ? `<p>${pct(matched.length / n, 0)} of Amazon SKUs have a stock record.</p>` : `<p>No Amazon SKUs in this selection.</p>`}<p class="muted">Unmatched SKUs are reported, not forced.</p><p class="warn">Stock is a single undated snapshot. Remaining stock and turnover cannot be calculated without inventory history.</p><p class="muted">Filters change units and sales. They do not change recorded stock.</p></div></section></div>`;
  },
  pricing() {
    const { mk, r } = D.prices, col = m => r.map(x => x[mk.indexOf(m) + 2]).filter(v => v !== null), avg = a => sum(a) / a.length;
    const stats = mk.map(m => { const v = col(m); return { m, lo: Math.min(...v), hi: Math.max(...v), av: avg(v), n: v.length }; });
    const spreads = r.map(x => { const v = x.slice(2).filter(y => y !== null); return { sku: x[0], cat: x[1], amazon: x[2], gap: v.length ? Math.max(...v) - Math.min(...v) : 0 }; }), withGap = spreads.filter(s => s.gap > 0);
    const kCard = (m, c) => kpi(`Average ${m} MRP`, "₹" + int(stats.find(s => s.m === m).av), "May 2022 snapshot", c);
    const kpis = [kCard("Amazon", GOLD), kCard("Flipkart", TEAL), kCard("Myntra", TEAL), kCard("Ajio", TEAL), kCard("Snapdeal", TEAL),
      kpi("Products With Prices", big(col("Amazon").length), `${int(r.length)} products listed`, PURPLE), kpi("Products With Price Gaps", int(withGap.length), "MRP differs by marketplace", CORAL), kpi("Average Price Gap", "₹" + int(avg(withGap.map(s => s.gap))), "Where a gap exists", CORAL)].join("");
    const maxP = Math.max(...stats.map(s => s.hi));
    const range = `<div class="bars">${stats.slice().sort((a, b) => b.av - a.av).map(s => `<a class="bar-row" href="${toMarket(s.m)}" data-tip="${esc(`${s.m}\nLowest ₹${int(s.lo)}\nAverage ₹${int(s.av)}\nHighest ₹${int(s.hi)}\nClick for detail`)}"><span class="name">${esc(s.m)}</span><span class="track" style="position:relative;display:block;height:27px"><span style="position:absolute;top:12px;height:4px;background:#3a3a3a;border-radius:2px;left:${s.lo / maxP * 92}%;width:${(s.hi - s.lo) / maxP * 92}%"></span><span style="position:absolute;top:8px;width:11px;height:11px;border-radius:50%;background:${GOLD};box-shadow:0 0 0 2px #141414;left:calc(${s.av / maxP * 92}% - 5px)"></span><span class="num" style="position:absolute;top:-1px;left:calc(${s.av / maxP * 92}% + 11px)">₹${int(s.av)}</span></span></a>`).join("")}</div><p class="sub" style="color:var(--text3);font-size:11px;margin:8px 0 0">Bar: lowest ₹${int(stats[0].lo)} to highest ₹${int(maxP)}. Dot: average.</p>`;
    const byCat = {}, gapCat = {};
    r.forEach(x => { if (x[2] !== null) (byCat[x[1]] = byCat[x[1]] || []).push(x[2]); });
    withGap.forEach(s => { gapCat[s.cat] = (gapCat[s.cat] || 0) + 1; });
    const top = withGap.slice().sort((a, b) => b.gap - a.gap || a.sku.localeCompare(b.sku)).slice(0, 12);
    return header("MRP snapshots, not revenue", "Marketplace Pricing Intelligence", "Snapshots: March 2021 and May 2022") + `<div class="kpis">${kpis}</div><div class="grid">`
      + card("s8", "MRP range by marketplace", "May 2022. March 2021 is identical. Blank prices are excluded, not treated as zero. Click a marketplace for detail.", range)
      + card("s4", "Pricing coverage", "Share of 1,330 products with a price. Click for detail.", bars(stats.map(s => [s.m, s.n / r.length]), { color: PURPLE, fmt: v => pct(v), link: toMarket, title: "Coverage" }))
      + card("s3", "Average Amazon MRP by category", "", bars(Object.entries(byCat).map(([k, v]) => [k, avg(v)]).sort((a, b) => b[1] - a[1]), { title: "Average MRP" }))
      + card("s3", "Price gaps by category", "Products whose MRP differs between marketplaces", bars(Object.entries(gapCat).sort((a, b) => b[1] - a[1]), { color: CORAL, fmt: int, title: "Products" }))
      + card("s3", "Largest price gaps", "", table([{ t: "SKU", txt: 1 }, { t: "Gap" }, { t: "Amazon MRP" }], top.map(s => [s.sku, rsFull(s.gap), rsFull(s.amazon)])))
      + `<section class="card s3 insights"><div class="card-head"><h2>Reading this page</h2></div><div class="body"><p>${int(withGap.length)} products have different MRPs across marketplaces, with an average gap of ₹${int(avg(withGap.map(s => s.gap)))} and a maximum of ₹${int(Math.max(...withGap.map(s => s.gap)))}.</p><h3>No price movement between snapshots</h3><p class="muted">March 2021 and May 2022 hold identical MRPs for every product. The two files may be one price list.</p><p class="warn">MRP is a list price, never revenue. These SKU codes match no sales table, so price and sales are not compared.</p></div></section></div>`;
  },
  expenses() {
    const total = sum(D.expenses, e => e[1]), got = sum(D.receipts, e => e[1]);
    const kpis = [kpi("Recorded Receipts", "₹" + int(got), "Four dated receipts", TEAL), kpi("Recorded Expenses", "₹" + int(total), "13 undated line items", PURPLE), kpi("Recorded Balance Difference", "₹" + int(got - total), "Source sheet: Pending Amount. Not profit", CORAL), kpi("Largest Expense", D.expenses[0][0], "By recorded amount", PURPLE, null, true)].join("");
    return header("IIGF event cash sheet", "Expense and Cash Movement", "Receipts dated 19 to 23 June 2022") + `<div class="kpis">${kpis}</div><div class="grid">`
      + card("s6", "Expense ranking by particular", "All 13 line items on the sheet. Personal names removed.", bars(D.expenses, { color: PURPLE, fmt: v => "₹" + int(v), title: "Expense" }))
      + card("s6", "Receipt timeline", "Receipts are the only dated values on the sheet", columns(D.receipts.map(r => ({ label: dateLabel(r[0]), vals: [r[1]] })), [["Receipts", TEAL]], { height: 260, width: 640, fmt: v => "₹" + int(v) }))
      + `<section class="card s12 insights"><div class="card-head"><h2>Reading this page</h2></div><div class="body"><p>This sheet appears to record one event (IIGF, June 2022): travel, hotel, labour and sundries.</p><p class="warn">It is not the cost base of the sales business, so it must not be netted against sales.</p><p class="muted">The difference of ₹${int(got - total)} matches the Pending Amount row on the sheet. It means spending exceeded receipts on this sheet. It is not a profit or loss. Expense lines have no dates, so no expense timeline is possible and date filters do not apply.</p></div></section></div>`;
  },
  logistics() {
    const pts = D.wh.rates.map(r => ({ label: r[0], vals: [r[1], r[2]] }));
    return header("Shiprocket and INCREFF", "Logistics and Warehouse Comparison", "Undated reference chart") + `<div class="grid">`
      + card("s8", "Service rates compared", "Only services quoted as a plain rate by both providers", columns(pts, [["Shiprocket", GOLD], ["INCREFF", TEAL]], { mode: "group", height: 250, fmt: v => "₹" + v.toFixed(2), money: true }))
      + `<section class="card s4 insights"><div class="card-head"><h2>Reading this page</h2></div><div class="body"><p>Shiprocket is cheaper on outbound and customer returns. Inbound is the same price at both providers.</p><p class="warn">Storage is left out of the chart because the units differ: Shiprocket quotes 25 per cft, INCREFF 0.15 per day.</p><p class="muted">Rates are reference prices with no stated unit of volume. They are not realised costs and are not part of any sales figure.</p></div></section>`
      + card("s12", "Scope of work and service terms", "As listed in the source chart, which does not say which provider each term applies to. Not realised costs.", table([{ t: "#", txt: 1 }, { t: "Section", txt: 1 }, { t: "Item", txt: 1 }, { t: "Detail", txt: 1 }], D.wh.terms.map(r => [r[0], r[1], r[2], r[3]]), true)) + `</div>`;
  },
  notes() {
    const sec = (h, items) => `<h2>${esc(h)}</h2>` + items.map(([b, t]) => `<h3>${esc(b)}</h3><p>${esc(t)}</p>`).join("");
    return header("How every number is built", "Data Definitions and Limitations", "Applies to every page") + `<div class="grid"><section class="card s6 prose">`
      + sec("About this web version", [["What this is", "A static web copy of a Power BI dashboard, so it opens from a link with no licence or install. Every figure is exported from the Power BI model."], ["Privacy", "International customer names are replaced with Customer 001, 002 and so on, ranked by total sales. Personal names on the expense sheet are removed."], ["Differences from Power BI", "This version filters by year, quarter and month, not by exact date range. Clicking a bar does not filter the other charts. SKU Detail opens for SKUs in the Top 15 and Top 10 lists."]])
      + sec("Sales definitions", [["Amazon recorded sales", "Sum of Amount where Status is Shipped or Shipped - Delivered to Buyer. Cancelled, returned, rejected, lost, damaged and pending orders are excluded from sales. Each has its own count."], ["International recorded sales", "Sum of the original GROSS AMT. PCS × RATE is kept separately, and the gap is shown as a discount."], ["Total recorded sales", "Amazon plus International. The two cover different periods and overlap only in April to May 2022, so a combined figure is not a like-for-like comparison."], ["Currency", "International has no currency field. It is shown in rupees because its rates sit in the same range as Amazon prices. This is an assumption, not a fact in the data."]])
      + sec("Metrics deliberately not shown", [["Net profit, gross profit and COGS", "No product cost data exists. Expense IIGF is one event's cash sheet, not business costs."], ["Year-over-year growth", "No period exists in both years for the same segment."], ["Stock turnover", "Stock is a single undated snapshot with no history."]])
      + `</section><section class="card s6 prose">`
      + sec("Corrections applied to the source files", [["International sale Report", "The file stacks several exports. Only 12,939 of its 37,432 rows are the true ledger. Removed 5,696 rows repeating earlier rows, 1,041 rows of a stray stock list, and 17,756 rows of a re-export with shifted columns, which also holds 229 shipping and label charge lines that are not product sales."], ["Amazon Sale Report", "All 128,975 rows are loaded. Non-shipped orders had been filtered out, which made cancellations look like zero. State spellings are standardised. 7,566 of 18,332 cancelled lines have no Amount, so the cancelled value is lower than the true value of those orders."], ["Expense IIGF", "A subtotal row and a Pending Amount row were being added as expenses, overstating the total as 13,095. The true total is 8,095."]])
      + sec("Dataset boundaries", [["Pricing snapshots", "May 2022 and March 2021 list the same 1,330 products with identical MRPs, so no price movement can be shown. Their SKU codes match no sales or stock table."], ["SKU matching", "92% of Amazon SKUs match a stock record. Unmatched SKUs are reported, never forced to match."], ["Data age", "Sales data ends in June 2022. It is historical and does not describe current performance."]])
      + `</section></div>`;
  },
  sku(code) {
    const p = period(), idx = D.sku.k.indexOf(code), det = D.detail[code];
    if (idx < 0 || !det) return header("SKU detail", code, "", true) + empty("Detail is available for SKUs in the Top 15 and Top 10 lists.");
    const rows = D.sku.r.filter(r => r[1] === idx && p.has(r[0])), f = i => sum(rows, r => r[i]), none = "No data in selection";
    const s = f(2), u = f(3), o = f(4), a = f(5), c = f(6), rr = f(7), is = f(8), iu = f(9), stock = D.sku.stock[idx], ALL = sum(amzDays(p), r => r[1]);
    const attr = det.attr, eyebrow = ["SKU detail", attr.cat, attr.style && `Style ${attr.style}`, attr.size && `Size ${attr.size}`, attr.colour].filter(Boolean).join("  ·  ");
    const days = det.day.filter(r => p.has(monthOf(r[0]))), mo = D.months.map((m, i) => [m, i]).filter(([, i]) => p.has(i));
    const skuM = i => { const x = D.sku.r.find(r => r[1] === idx && r[0] === i); return x ? [x[2], x[8]] : [0, 0]; };
    const kpis = [
      kpi("Amazon Recorded Sales", s ? rs(s) : "—", s ? `${pct(s / ALL, 2)} of Amazon sales` : "No recognised Amazon sale", GOLD, days.map(r => r[1])),
      kpi("Amazon Units Sold", u ? big(u) : "—", u ? `Avg price ₹${int(s / u)}` : none),
      kpi("Amazon Orders", o ? big(o) : "—", `${int(a)} including all outcomes`),
      kpi("Cancelled Orders", c ? big(c) : "—", a ? `${pct(c / a)} of all orders` : "No Amazon orders", CORAL),
      kpi("Returned / Failed Orders", rr ? big(rr) : "—", a ? `${pct(rr / a)} of all orders` : "No Amazon orders", CORAL),
      kpi("Recorded Stock (Units)", stock === null ? "—" : big(stock), stock === null ? "No stock record for this SKU" : "Undated snapshot", TEAL),
      kpi("International Sales", is ? rs(is) : "—", is ? "Original GROSS AMT" : "No International line", TEAL),
      kpi("International Units", iu ? big(iu) : "—", "Apr to May 2022 lines carry no SKU", TEAL),
    ].join("");
    const roll = list => { const m = {}; list.filter(r => p.has(r[0])).forEach(r => { m[r[1]] = (m[r[1]] || 0) + r[2]; }); return Object.entries(m).sort((x, y) => y[1] - x[1]).slice(0, 10); };
    const pts = mo.map(([m, i]) => ({ label: m.label, vals: skuM(i) })).filter(t => t.vals[0] || t.vals[1]);
    const monthly = pts.map(t => [t.label, t.vals[0] ? rsFull(t.vals[0]) : "", t.vals[1] ? rsFull(t.vals[1]) : ""]);
    return header(eyebrow, code, days.length ? `Amazon · ${dateLabel(days[0][0])} to ${dateLabel(days[days.length - 1][0])}` : none, true) + filters() + `<div class="kpis">${kpis}</div><div class="grid">`
      + card("s5", "Recorded sales by month", "Amazon and International stay separate", columns(pts, [["Amazon", GOLD], ["International", TEAL]], { height: 270, width: 560 }))
      + card("s4", "Where order value went", "Cancelled lines can have no Amount", waterfall(outcome(det.status.filter(r => p.has(r[0])))))
      + card("s3", "Daily Amazon sales", "Brighter days sold more", calendar(days))
      + card("s3", "Top 10 states", "Amazon recorded sales", bars(roll(det.state), { title: "Sales" }))
      + card("s3", "Top 10 cities", "Amazon recorded sales", bars(roll(det.city), { title: "Sales" }))
      + card("s3", "Sales by month", "Months with no sale are left out", table([{ t: "Month", txt: 1 }, { t: "Amazon" }, { t: "International" }], monthly))
      + `<section class="card s3 insights"><div class="card-head"><h2>Reading this page</h2></div><div class="body"><p>Sales count only Shipped and Delivered orders. Cancelled and returned orders are shown but never added to sales.</p><h3>Stock is not compared over time</h3><p class="muted">Stock is one undated snapshot, so no turnover or days of cover can be calculated. A blank stock card means no record, not zero.</p><p class="warn">International April to May 2022 lines have no SKU, so International sales for this SKU may be higher.</p></div></section></div>`;
  },
  marketplace(name) {
    const { mk, r } = D.prices, c = mk.indexOf(name);
    if (c < 0) return header("Marketplace detail", name, "", true) + empty("Unknown marketplace.");
    const items = r.map(x => { const v = x.slice(2).filter(y => y !== null); return { sku: x[0], cat: x[1], p: x[c + 2], hi: v.length ? Math.max(...v) : null, lo: v.length ? Math.min(...v) : null, all: v }; });
    const priced = items.filter(i => i.p !== null), avg = sum(priced, i => i.p) / priced.length, allV = items.flatMap(i => i.all), allAvg = sum(allV) / allV.length;
    const differ = priced.filter(i => i.hi > i.lo), atHi = differ.filter(i => i.p === i.hi), atLo = differ.filter(i => i.p === i.lo);
    const avgs = mk.map((m, j) => { const v = r.map(x => x[j + 2]).filter(y => y !== null); return sum(v) / v.length; }), rank = 1 + avgs.filter(a => a > avg + 1e-9).length;
    const kpis = [
      kpi("Average MRP", "₹" + int(avg), `All marketplaces ₹${int(allAvg)}`),
      kpi("Against All Marketplaces", signed(avg / allAvg - 1), "Difference in average MRP"),
      kpi("Rank by Average MRP", "#" + rank, "Of 8. Ties share a rank", PURPLE),
      kpi("MRP Range", `₹${int(Math.min(...priced.map(i => i.p)))} – ₹${int(Math.max(...priced.map(i => i.p)))}`, "Lowest to highest listed", PURPLE, null, true),
      kpi("Products Priced", int(priced.length), `${pct(priced.length / r.length)} of listed products`, TEAL),
      kpi("Products at Highest MRP", int(atHi.length), "Only where marketplaces differ", CORAL),
      kpi("Products at Lowest MRP", int(atLo.length), "Only where marketplaces differ", EMERALD),
    ].join("");
    const cats = [...new Set(r.map(x => x[1]))];
    const catAvg = (list, f) => { const v = list.map(f).filter(y => y !== null); return v.length ? sum(v) / v.length : 0; };
    const pts = cats.map(ca => { const ii = items.filter(i => i.cat === ca); return { label: ca, vals: [catAvg(ii, i => i.p), (() => { const a = ii.flatMap(i => i.all); return a.length ? sum(a) / a.length : 0; })()] }; }).sort((a, b) => b.vals[0] - a.vals[0]);
    const gaps = priced.filter(i => i.p > i.lo).sort((a, b) => (b.p - b.lo) - (a.p - a.lo) || a.sku.localeCompare(b.sku)).slice(0, 15).map(i => [i.sku, rsFull(i.p), rsFull(i.lo), rsFull(i.p - i.lo)]);
    const pos = cats.map(ca => ({ label: ca, vals: [atHi.filter(i => i.cat === ca).length, atLo.filter(i => i.cat === ca).length] })).filter(t => t.vals[0] || t.vals[1]).sort((a, b) => b.vals[1] - a.vals[1]);
    return header("Marketplace detail  ·  MRP, not revenue", name, "May 2022 snapshot", true) + `<div class="kpis">${kpis}</div><div class="grid">`
      + card("s6", "Average MRP by category", "This marketplace against all eight", columns(pts, [["This marketplace", GOLD], ["All marketplaces", GREY]], { mode: "group", height: 280, width: 640 }))
      + card("s6", "How products are priced", "Products in each MRP band. Blank prices are excluded.", histogram(priced.map(i => i.p)))
      + card("s5", "Largest gaps above the lowest listing", "Top 15 products where this marketplace lists above the lowest", table([{ t: "SKU", txt: 1 }, { t: "This MRP" }, { t: "Lowest anywhere" }, { t: "Gap" }], gaps))
      + card("s4", "Highest and lowest MRP by category", "Products where marketplaces differ", columns(pos, [["At highest", CORAL], ["At lowest", EMERALD]], { mode: "group", height: 280, width: 480, fmt: int, money: false }))
      + `<section class="card s3 insights"><div class="card-head"><h2>Reading this page</h2></div><div class="body"><p>${esc(name)} has a price for ${int(priced.length)} of ${int(r.length)} products. Average MRP is ${signed(avg / allAvg - 1)} against all marketplaces.</p><h3>MRP is a list price, never revenue</h3><p class="muted">These prices do not show what sold on this marketplace. Only Amazon has sales data here, and these SKU codes match no sales table.</p><p class="warn">March 2021 holds identical MRPs, so no price change can be shown.</p></div></section></div>`;
  },
};

function growthCard(g, useA, A) {
  if (!useA) return kpi("Amazon Sales Growth MoM", "—", "Segment not selected", EMERALD);
  if (!A.s) return kpi("Amazon Sales Growth MoM", "—", "No data in selection", EMERALD);
  if (!g || g.none) return kpi("Amazon Sales Growth MoM", "n/a", "Needs two full months", EMERALD);
  return kpi("Amazon Sales Growth MoM", `${g.mom >= 0 ? "▲" : "▼"} ${pct(Math.abs(g.mom))}`, `${g.label}. ${signed(g.perDay)} per day`, g.mom < 0 ? CORAL : EMERALD, A.days.map(r => r[1]));
}
function execInsights(p, A, I, styles, g) {
  const out = [];
  if (!A.s) out.push("<p>No Amazon sales in this selection.</p>");
  else {
    out.push(I.s ? `<p>Amazon brings ${pct(A.s / (A.s + I.s), 0)} of recorded sales: ${rs(A.s)} vs ${rs(I.s)}.</p>` : `<p>All recorded sales here are Amazon: ${rs(A.s)}.</p>`);
    const states = dimTotals(D.dims.state, p);
    out.push(`<p>Top 10 styles earn ${pct(sum(styles.slice(0, 10), s => s[1]) / A.s, 0)} of Amazon sales, led by ${esc(styles[0][0])}.</p>`);
    out.push(`<p>${esc(states[0][0])} is the largest Amazon market at ${pct(states[0][1] / A.s, 0)} of sales.</p>`);
    out.push(`<p class="warn">${pct(A.c / A.a)} of Amazon orders were cancelled and ${pct((A.r || 0) / A.a)} came back or failed in delivery.</p>`);
  }
  const cust = dimTotals(D.int.customer, p);
  out.push(cust.length ? `<p>Largest International buyer is ${esc(cust[0][0])}, at ${pct(cust[0][1] / sum(cust, c => c[1]), 0)} of that segment.</p>` : "<p>No International sales in this selection.</p>");
  out.push(`<h3>Read this before comparing</h3><p class="muted">Amazon covers 31 Mar to 29 Jun 2022. International covers 5 Jun 2021 to 11 May 2022. They overlap only in Apr to May 2022, so totals are not like for like.</p><p class="warn">Net profit is not available: COGS data is required. Expenses are one event sheet, not business costs. Stock and MRP are not sales.</p>`);
  return out.join("");
}

/* ---------- routing and events ---------- */
function route() {
  const parts = location.hash.replace(/^#\/?/, "").split("/");
  return { name: parts[0] || "executive", arg: parts[1] ? decodeURIComponent(parts[1]) : null };
}
function render(keepScroll = false) {
  const { name, arg } = route(), view = VIEWS[name] || VIEWS.executive, active = name === "sku" ? "products" : name === "marketplace" ? "pricing" : VIEWS[name] ? name : "executive";
  document.getElementById("nav").innerHTML = PAGES.map(([k, l]) => `<a href="#/${k}"${k === active ? ' aria-current="page"' : ""}>${esc(l)}</a>`).join("");
  const y = window.scrollY, app = document.getElementById("app");
  app.innerHTML = view(arg);
  document.title = (PAGES.find(x => x[0] === active) || ["", "Dashboard"])[1] + " | Sales Intelligence";
  window.scrollTo(0, keepScroll ? y : 0);
}
function bind() {
  window.addEventListener("hashchange", () => { hideTip(); render(); document.getElementById("app").focus({ preventScroll: true }); });
  document.addEventListener("change", e => { const k = e.target.dataset && e.target.dataset.filter; if (k) { STATE[k] = e.target.value; render(true); document.getElementById("f-" + k)?.focus(); } });
  document.addEventListener("click", e => {
    const g = e.target.closest("[data-grain]");
    if (g) { STATE.grain = g.dataset.grain; render(true); return; }
    if (e.target.closest("[data-back]")) { if (history.length > 1) history.back(); else location.hash = "#/executive"; }
  });
  document.getElementById("clear").addEventListener("click", () => { Object.assign(STATE, { year: "", quarter: "", month: "", segment: "", grain: "Month" }); render(true); });
  const tip = document.getElementById("tip");
  const hide = hideTip;
  document.addEventListener("mousemove", e => {
    const t = e.target.closest && e.target.closest("[data-tip]");
    if (!t) return hide();
    tip.textContent = t.dataset.tip; tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.min(e.clientX + 14, innerWidth - w - 8) + "px";
    tip.style.top = (e.clientY + 16 + h > innerHeight ? e.clientY - h - 10 : e.clientY + 16) + "px";
  });
  document.addEventListener("mouseleave", hide);
}
function hideTip() { const t = document.getElementById("tip"); if (t) t.hidden = true; }

fetch("data.json").then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(data => {
  D = data;
  D._ymIndex = {};
  D.months.forEach((m, i) => { D._ymIndex[String(m.ym)] = i; });
  bind();
  render();
  window.__dash = { D, STATE, period, amz, intl, skuTotals, topSkus, render };
}).catch(err => { document.getElementById("app").innerHTML = `<p class="loading">The dashboard data could not load (${esc(err.message)}).</p>`; });
