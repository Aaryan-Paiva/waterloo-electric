/** Isometric Waterloo scene (schematic layout, not real geography). Deterministic; every dynamic effect is bound to a SimState value that comes from
 *  the real sandbox run (device glow = that group actually dispatched, line colour = load vs capacity). */
export type Season = "winter" | "spring" | "summer" | "fall";
export type Phase = "calm" | "stress" | "balancing" | "balanced";
export interface Look { season: Season; night: number }
export type LoadKind = "data_centre" | "housing" | "ev_depot";
export interface PlacedLoad { id: string; kind: LoadKind; lot: number; rise: number }
export interface SimState { phase: Phase; active: { battery: boolean; ev: boolean; building: boolean }; loads: PlacedLoad[]; t: number; dragging: boolean; hoverLot: number | null }
export const W = 1440, H = 900;
const TW = 64, TH = 32, OX = 720, OY = 246;
export const P = (x: number, y: number): [number, number] => [OX + ((x - y) * TW) / 2, OY + ((x + y) * TH) / 2];
export const LOTS: { x: number; y: number }[] = [{ x: 7.4, y: 9.4 }, { x: 10, y: 9.4 }, { x: 7.4, y: 11.4 }, { x: 10, y: 11.4 }];
export const ANCHORS = { battery: P(3.4, 12.2), ev: P(3.0, 8.4), building: P(9.9, 2.9), industry: P(12.8, 8.9), substation: P(6.5, 6.5) };

const hx = (c: string) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
const mix = (a: string, b: string, t: number) => { const A = hx(a), B = hx(b); return "#" + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, "0")).join(""); };
function rng(seed: number) { let s = seed >>> 0; return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

type C = CanvasRenderingContext2D;
interface Obj { k: number; draw: (c: C, st: SimState, lk: Look) => void }
const tone = (lk: Look, col: string) => (lk.night > 0 ? mix(col, "#16204A", 0.62 * lk.night) : col);

function poly(c: C, pts: [number, number][], fill: string, stroke?: string, sw = 1) {
  c.beginPath(); pts.forEach((p, i) => (i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1]))); c.closePath();
  c.fillStyle = fill; c.fill(); if (stroke) { c.strokeStyle = stroke; c.lineWidth = sw; c.stroke(); }
}
const up = (p: [number, number], h: number): [number, number] => [p[0], p[1] - h];
function box(c: C, lk: Look, x: number, y: number, w: number, d: number, h: number, top: string, left: string, right: string, z = 0) {
  const A = P(x, y), B = P(x + w, y), Cc = P(x + w, y + d), D = P(x, y + d);
  poly(c, [up(D, z), up(Cc, z), up(Cc, h + z), up(D, h + z)], tone(lk, left));
  poly(c, [up(B, z), up(Cc, z), up(Cc, h + z), up(B, h + z)], tone(lk, right));
  poly(c, [up(A, h + z), up(B, h + z), up(Cc, h + z), up(D, h + z)], tone(lk, top));
}
function bil(q: [number, number][], u: number, v: number): [number, number] {
  const [p0, p1, p2, p3] = q;
  return [p0[0] * (1 - u) * (1 - v) + p1[0] * u * (1 - v) + p2[0] * u * v + p3[0] * (1 - u) * v, p0[1] * (1 - u) * (1 - v) + p1[1] * u * (1 - v) + p2[1] * u * v + p3[1] * (1 - u) * v];
}
function faceRect(c: C, lk: Look, q: [number, number][], u0: number, u1: number, v0: number, v1: number, fill: string, lit = false) {
  poly(c, [bil(q, u0, v0), bil(q, u1, v0), bil(q, u1, v1), bil(q, u0, v1)], lit ? fill : tone(lk, fill));
}
function shadow(c: C, x: number, y: number, w: number, d: number, h: number) {
  const B = P(x + w, y), Cc = P(x + w, y + d), D = P(x, y + d), o = h * 0.5;
  c.fillStyle = "rgba(26,42,18,.10)";
  poly(c, [D, Cc, [Cc[0] + o, Cc[1] + o * 0.35], [D[0] + o, D[1] + o * 0.35]], "rgba(26,42,18,.10)");
  poly(c, [B, Cc, [Cc[0] + o, Cc[1] + o * 0.35], [B[0] + o, B[1] + o * 0.35]], "rgba(26,42,18,.10)");
}
function glow(c: C, x: number, y: number, r: number, col: string, a: number) { c.globalAlpha = a; c.fillStyle = col; c.beginPath(); c.arc(x, y, r, 0, 7); c.fill(); c.globalAlpha = 1; }

function tree(x: number, y: number, sc = 1): Obj {
  return { k: x + y + 0.5, draw: (c, _s, lk) => {
    const p = P(x, y); const t = tone(lk, "#6B4A2B");
    c.fillStyle = "rgba(26,42,18,.12)"; c.beginPath(); c.ellipse(p[0] + 4, p[1], 9 * sc, 4 * sc, 0, 0, 7); c.fill();
    if (lk.season === "winter") {
      if (Math.floor(x * 3 + y * 5) % 3 === 0) {
        c.strokeStyle = t; c.lineWidth = 2; c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(p[0], p[1] - 6); c.stroke();
        [[13, -7], [10, -15], [7, -22]].forEach(([w, yy]) => { poly(c, [[p[0] - w * sc, p[1] + yy * sc], [p[0] + w * sc, p[1] + yy * sc], [p[0], p[1] + (yy - 12) * sc]], tone(lk, "#3F6B4A")); poly(c, [[p[0] - w * sc * 0.55, p[1] + (yy - 6) * sc], [p[0] + w * sc * 0.55, p[1] + (yy - 6) * sc], [p[0], p[1] + (yy - 12) * sc]], tone(lk, "#F4F8FA")); });
      } else {
        c.strokeStyle = t; c.lineWidth = 2; c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(p[0], p[1] - 16 * sc); c.moveTo(p[0], p[1] - 12 * sc); c.lineTo(p[0] - 7 * sc, p[1] - 21 * sc); c.moveTo(p[0], p[1] - 12 * sc); c.lineTo(p[0] + 7 * sc, p[1] - 21 * sc); c.stroke();
        c.fillStyle = tone(lk, "#FFFFFF"); c.fillRect(p[0] - 9 * sc, p[1] - 22 * sc, 8, 3); c.fillRect(p[0] + 2 * sc, p[1] - 22 * sc, 8, 3);
      }
      return;
    }
    const alt = Math.floor(x * 7 + y * 3) % 2 === 0;
    const c1 = lk.season === "fall" ? (alt ? "#C7761C" : "#B8501F") : alt ? "#3F7A1E" : "#4E8A26", c2 = lk.season === "fall" ? (alt ? "#E0A040" : "#D9742F") : alt ? "#5E9E2E" : "#77B23C";
    c.strokeStyle = t; c.lineWidth = 3; c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(p[0], p[1] - 11 * sc); c.stroke();
    c.fillStyle = tone(lk, c1); c.beginPath(); c.ellipse(p[0], p[1] - 19 * sc, 11 * sc, 12 * sc, 0, 0, 7); c.fill();
    c.fillStyle = tone(lk, c2); c.beginPath(); c.ellipse(p[0] - 3 * sc, p[1] - 22 * sc, 7 * sc, 8 * sc, 0, 0, 7); c.fill();
    if (lk.season === "spring") { c.fillStyle = "#F4C0D1"; c.fillRect(p[0] + 2, p[1] - 24 * sc, 3, 3); c.fillRect(p[0] - 5, p[1] - 17 * sc, 3, 3); }
  } };
}

function house(x: number, y: number, solar: boolean, idx: number): Obj {
  const w = 0.62, d = 0.6, h = 15, rh = 10;
  const walls = [["#F3E6D0", "#DCC9AB", "#E9D9BE"], ["#F6EBDD", "#E0CDB4", "#EBDCC5"], ["#E6EDF2", "#C8D3DC", "#D6E0E8"], ["#F1E2DA", "#DAC2B6", "#E7D1C6"]][idx % 4];
  const roofs = [["#C46A4A", "#A95536"], ["#8F6C5A", "#775646"], ["#B0553C", "#953F2A"]][idx % 3];
  return { k: x + y + 0.9, draw: (c, _s, lk) => {
    const A = P(x, y), B = P(x + w, y), Cc = P(x + w, y + d), D = P(x, y + d);
    shadow(c, x, y, w, d, h);
    poly(c, [D, Cc, up(Cc, h), up(D, h)], tone(lk, walls[1]));
    poly(c, [B, Cc, up(Cc, h), up(B, h)], tone(lk, walls[2]));
    void A;
    const RL = P(x, y + d / 2), RR = P(x + w, y + d / 2);
    const winter = lk.season === "winter";
    const rl = winter ? "#FBFDFE" : roofs[0], rr = winter ? "#E6EDF2" : roofs[1];
    poly(c, [up(D, h), up(Cc, h), up(RR, h + rh), up(RL, h + rh)], tone(lk, rl));
    poly(c, [up(B, h), up(Cc, h), up(RR, h + rh)], tone(lk, rr));
    if (solar && (!winter || idx % 2 === 0)) {
      const q: [number, number][] = [up(D, h), up(Cc, h), up(RR, h + rh), up(RL, h + rh)];
      poly(c, [bil(q, 0.14, 0.16), bil(q, 0.86, 0.16), bil(q, 0.86, 0.84), bil(q, 0.14, 0.84)], tone(lk, winter ? "#3A4E78" : "#22345A"), tone(lk, "#9DB4D9"), 0.8);
    }
    const wq: [number, number][] = [D, Cc, up(Cc, h), up(D, h)];
    const lit = lk.night > 0.35;
    ([[0.16, 0.36], [0.6, 0.8]] as const).forEach(([u0, u1]) => {
      faceRect(c, lk, wq, u0, u1, 0.32, 0.72, lit ? "#FFD27A" : "#9FB9CF", lit);
      if (lit) { const g = bil(wq, (u0 + u1) / 2, 0.52); glow(c, g[0], g[1], 9, "#FFD27A", 0.22); }
    });
    faceRect(c, lk, wq, 0.42, 0.54, 0, 0.5, "#8A5A3C");
  } };
}

function tower(x: number, y: number, w: number, h: number, idx: number): Obj {
  const pal = [["#C9D4E4", "#8FA3C1", "#7488A8"], ["#D9D2E8", "#A79BC9", "#8B7FB0"], ["#CFE0DD", "#8DB3AC", "#729C94"]][idx % 3];
  return { k: x + y + w * 2, draw: (c, st, lk) => {
    shadow(c, x, y, w, w, h);
    box(c, lk, x, y, w, w, h, pal[0], pal[1], pal[2]);
    const B = P(x + w, y), Cc = P(x + w, y + w), D = P(x, y + w);
    const lit = lk.night > 0.35, dim = st.active.building;
    const faces: [string, [number, number][]][] = [["L", [D, Cc, up(Cc, h), up(D, h)]], ["R", [B, Cc, up(Cc, h), up(B, h)]]];
    faces.forEach(([f, q]) => {
      const rows = Math.floor(h / 9);
      for (let r = 1; r < rows; r++) { const v = r / rows; const on = lit && (r * 7 + idx * 3 + (f === "R" ? 1 : 0)) % 3 !== 0; faceRect(c, lk, q, 0.1, 0.9, v - 0.02, v + 0.035, on ? (dim ? "#C9B27A" : "#FFD27A") : lit ? "#2B3766" : dim ? "#B9C8D6" : "#E9F2FA", on); }
    });
    box(c, lk, x + w * 0.3, y + w * 0.3, w * 0.35, w * 0.35, 7, "#E5E7EA", "#B9BDC4", "#9CA1AA", h);
    if (dim) { const p = P(x + w / 2, y + w / 2); glow(c, p[0], p[1] - h - 8, 22, "#AFA9EC", 0.35 + 0.15 * Math.sin(st.t / 6)); }
  } };
}

function university(): Obj {
  const x = 7.3, y = 4.4;
  return { k: x + y + 4.4, draw: (c, _s, lk) => {
    shadow(c, x, y, 3.4, 0.9, 20); box(c, lk, x, y, 3.4, 0.9, 20, "#EAD9C0", "#CDB593", "#B89D7A");
    box(c, lk, x + 3.5, y + 0.05, 0.8, 0.8, 46, "#E9DAC4", "#C9B18F", "#B39876");
    const a = P(x + 3.9, y + 0.45);
    c.fillStyle = "#FBF5E6"; c.strokeStyle = "#8A6D45"; c.lineWidth = 1.4; c.beginPath(); c.arc(a[0], a[1] - 56, 6.5, 0, 7); c.fill(); c.stroke();
    c.strokeStyle = "#5A4630"; c.beginPath(); c.moveTo(a[0], a[1] - 56); c.lineTo(a[0], a[1] - 60); c.moveTo(a[0], a[1] - 56); c.lineTo(a[0] + 3.5, a[1] - 56); c.stroke();
    const q = [P(x + 3.5, y + 0.05), P(x + 4.3, y + 0.05), P(x + 4.3, y + 0.85), P(x + 3.5, y + 0.85)].map((p) => up(p, 46));
    poly(c, q as [number, number][], tone(lk, "#8E4A38"));
  } };
}

function battery(x: number, y: number, units: number, idx: number): Obj {
  return { k: x + y + 0.75 + 0.62, draw: (c, st, lk) => {
    shadow(c, x, y, 1.5, 0.62, 11);
    for (let k = 0; k < units; k++) {
      const xx = x + k * 0.5;
      box(c, lk, xx, y, 0.46, 0.62, 12, "#DDE9F7", "#5B9BE0", "#3B78C2");
      const q: [number, number][] = [P(xx, y + 0.62), P(xx + 0.46, y + 0.62), up(P(xx + 0.46, y + 0.62), 12), up(P(xx, y + 0.62), 12)];
      faceRect(c, lk, q, 0.15, 0.85, 0.42, 0.5, "#CFE3FA");
      const a = bil(q, 0.5, 0.8); c.fillStyle = st.active.battery ? "#5EEAD4" : "#9FE3C2"; c.beginPath(); c.arc(a[0], a[1], 1.8, 0, 7); c.fill();
    }
    if (st.active.battery) {
      const cc = P(x + 0.75, y + 0.3);
      glow(c, cc[0], cc[1] - 6, 30, "#7FD1FF", 0.22 + 0.1 * Math.sin(st.t / 4 + idx));
      for (let k = 0; k < 4; k++) { const yy = (st.t * 1.4 + k * 14 + idx * 5) % 38; c.fillStyle = `rgba(207,239,255,${Math.max(0, 0.9 - yy / 38)})`; c.fillRect(cc[0] - 16 + k * 10, cc[1] - 26 - yy, 3, 3); }
    }
  } };
}
function charger(x: number, y: number, i: number): Obj {
  return { k: x + y + 0.4, draw: (c, st, lk) => {
    const p = P(x, y), paused = st.active.ev && i % 3 !== 0;
    c.fillStyle = tone(lk, "#4A4B4F"); c.fillRect(p[0] - 2, p[1] - 13, 4, 13);
    c.fillStyle = paused ? "#F2A72E" : "#1F9E89"; c.beginPath(); c.roundRect(p[0] - 4, p[1] - 17, 8, 6, 1.5); c.fill();
  } };
}
function car(x: number, y: number, col: string, ax: "x" | "y", dyn = false): Obj {
  const w = ax === "x" ? 0.44 : 0.24, d = ax === "x" ? 0.24 : 0.44;
  return { k: x + y + 0.9, draw: (c, st, lk) => {
    const xx = dyn ? x + (ax === "x" ? ((st.t * 0.006) % 14) : 0) : x, yy = dyn ? y + (ax === "y" ? ((st.t * 0.006) % 14) : 0) : y;
    void xx; void yy;
    shadow(c, x, y, w, d, 6); box(c, lk, x, y, w, d, 5, col, mix(col, "#000000", 0.15), mix(col, "#000000", 0.28));
    box(c, lk, x + w * 0.2, y + d * 0.15, w * 0.5, d * 0.7, 3, "#DDE6EF", "#B9C6D3", "#9FB0C1", 5);
    if (lk.night > 0.4) { const p = P(x + w * 0.95, y + d * 0.5); c.fillStyle = "#FAC775"; c.fillRect(p[0], p[1] - 4, 2, 2); }
  } };
}
function warehouse(x: number, y: number, w: number, d: number, h: number): Obj {
  return { k: x + y + w + d, draw: (c, _s, lk) => {
    shadow(c, x, y, w, d, h); box(c, lk, x, y, w, d, h, "#E3E4E8", "#BFC3CB", "#A6ABB5");
    const q: [number, number][] = [P(x, y + d), P(x + w, y + d), up(P(x + w, y + d), h), up(P(x, y + d), h)];
    for (let k = 0; k < 4; k++) faceRect(c, lk, q, 0.08 + k * 0.23, 0.24 + k * 0.23, 0.1, 0.62, lk.night > 0.35 ? "#FFD27A" : "#8D97A8", lk.night > 0.35);
  } };
}

export interface Scene { objs: Obj[]; ground: (c: C, lk: Look) => void }
export function buildScene(season: Season): Scene {
  const r = rng(11), objs: Obj[] = [];
  for (let x = 0; x < 6; x++) for (let y = 0; y < 6; y++) { const q = r(); if (x === 2 && (y === 2 || y === 3)) continue; if (q < 0.74) objs.push(house(x + 0.18, y + 0.2, r() < 0.55, x * 3 + y)); else objs.push(tree(x + 0.5, y + 0.5)); }
  ([[7.2, 0.2, 1.7, 62, 0], [9.2, 0.5, 1.5, 44, 1], [11.2, 0.3, 1.8, 76, 2], [7.4, 2.6, 1.4, 34, 1], [9.6, 2.6, 1.6, 52, 0], [11.6, 2.8, 1.3, 30, 2]] as const).forEach(([x, y, w, h, i]) => objs.push(tower(x, y, w, h, i)));
  objs.push(university());
  [[12.3, 4.9], [12.7, 5.3], [7.1, 5.4], [9.1, 5.6], [11.2, 5.5]].forEach(([x, y]) => objs.push(tree(x, y, 0.9)));
  const cols = ["#1F9E89", "#5B9BE0", "#F0997B", "#E8C36A", "#8C7AE0", "#D4537E"];
  for (let a = 0; a < 3; a++) for (let b = 0; b < 4; b++) { const x = 1 + b * 1.15, y = 7.55 + a * 2, i = a * 4 + b; objs.push(charger(x + 0.2, y + 0.5, i)); if ((i * 5) % 7 !== 0) objs.push(car(x + 0.35, y + 0.5, cols[i % 6], "x")); }
  objs.push(battery(0.5, 10.7, 3, 0), battery(3.3, 12.15, 3, 1));
  objs.push({ k: 4.4 + 9.2 + 1.5, draw: (c, _s, lk) => { shadow(c, 4.4, 9.3, 1.3, 1.6, 14); box(c, lk, 4.4, 9.3, 1.3, 1.6, 14, "#D9DBDF", "#B7BBC2", "#9CA1AA"); } });
  [[0.5, 13.2], [5.2, 13.3], [5.4, 7.3]].forEach(([x, y]) => objs.push(tree(x, y, 0.9)));
  objs.push(warehouse(7.3, 7.3, 2.4, 1.3, 14), warehouse(10.3, 7.3, 2.6, 1.3, 17));
  objs.push({ k: 12.6 + 8.9 + 0.5, draw: (c, _s, lk) => {
    shadow(c, 12.6, 8.9, 0.4, 0.4, 40); box(c, lk, 12.6, 8.9, 0.4, 0.4, 40, "#C9BCB0", "#A89A8C", "#8C7E70");
    const p = P(12.8, 9.1); [[4, -52, 7], [12, -62, 9], [22, -74, 11]].forEach(([dx, dy, rr], k) => { c.fillStyle = `rgba(255,255,255,${0.7 - k * 0.16})`; c.beginPath(); c.arc(p[0] + dx, p[1] + dy, rr, 0, 7); c.fill(); });
  } });
  objs.push(battery(7.5, 8.7, 2, 2), battery(10.4, 8.7, 2, 3));
  [[12.9, 12.4], [7.4, 12.6], [12.4, 10.4]].forEach(([x, y]) => objs.push(tree(x, y, 0.95)));
  const rr = rng(3);
  for (let i = 0; i < 70; i++) { const x = -6 + rr() * 25, y = -6 + rr() * 25; if ((x >= -0.5 && x < 14.5 && y >= -0.5 && y < 14.5) || (y < -0.5 && x > 4)) continue; objs.push(tree(x, y, 0.9 + rr() * 0.4)); }
  const roadCars: [number, number, "x" | "y"][] = [[1.2, 6.15, "x"], [3.6, 6.62, "x"], [8.4, 6.15, "x"], [11.0, 6.62, "x"], [6.15, 2.2, "y"], [6.62, 4.0, "y"], [6.15, 9.4, "y"], [6.62, 12.0, "y"]];
  roadCars.forEach(([x, y, a], i) => objs.push({ k: x + y + 0.5, draw: (c, st, lk) => { if (lk.night > 0.6 && i > 3) return; car(x, y, cols[i % 6], a).draw(c, st, lk); } }));
  for (let k = 0; k < 14; k += 2) for (const [x, y] of [[6.08, k + 0.5], [k + 0.5, 6.08]] as const) { if (k >= 5 && k <= 6) continue; objs.push({ k: x + y + 0.1, draw: (c, _s, lk) => { const p = P(x, y); c.strokeStyle = "#3A3C42"; c.lineWidth = 2; c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(p[0], p[1] - 16); c.stroke(); if (lk.night > 0.25) { glow(c, p[0], p[1] - 16, 20, "#FFD27A", 0.28); c.fillStyle = "#FFE3A0"; c.beginPath(); c.arc(p[0], p[1] - 16, 2.8, 0, 7); c.fill(); } } }); }
  // substation
  objs.push({ k: 6.5 + 6.5 + 2.2, draw: (c, st, lk) => {
    shadow(c, 5.6, 5.6, 1.8, 1.8, 10); box(c, lk, 5.6, 5.6, 1.8, 1.8, 5, "#C9CBCF", "#9EA2A9", "#82868E");
    ([[0.15, 0.15], [0.85, 0.15], [0.15, 0.85], [0.85, 0.85]] as const).forEach(([dx, dy]) => box(c, lk, 5.6 + dx * 0.75, 5.6 + dy * 0.75, 0.42, 0.42, 18, "#D8DADF", "#B0B4BB", "#8F949C", 5));
    const cc = P(6.5, 6.5);
    c.strokeStyle = tone(lk, "#4A4B4F"); c.lineWidth = 2; c.beginPath(); c.moveTo(cc[0] - 14, cc[1] - 4); c.lineTo(cc[0] - 3, cc[1] - 70); c.lineTo(cc[0] + 3, cc[1] - 70); c.lineTo(cc[0] + 14, cc[1] - 4); c.stroke();
    c.lineWidth = 1.6; c.beginPath(); c.moveTo(cc[0] - 10, cc[1] - 30); c.lineTo(cc[0] + 10, cc[1] - 30); c.moveTo(cc[0] - 6, cc[1] - 50); c.lineTo(cc[0] + 6, cc[1] - 50); c.stroke();
    const led = st.phase === "stress" ? "#E5533D" : st.phase === "balancing" ? "#F2A72E" : "#3FD1A0";
    glow(c, cc[0], cc[1] - 74, st.phase === "stress" ? 16 + 3 * Math.sin(st.t / 4) : 11, led, 0.35); c.fillStyle = led; c.beginPath(); c.arc(cc[0], cc[1] - 74, 5, 0, 7); c.fill();
  } });
  objs.sort((a, b) => a.k - b.k);
  const ground = (c: C, lk: Look) => {
    const winter = season === "winter";
    const g0 = winter ? "#EEF3F6" : season === "fall" ? "#C9B26A" : season === "spring" ? "#B9DA96" : "#BFDD94", g1 = winter ? "#E2EAF0" : season === "fall" ? "#BFA85F" : season === "spring" ? "#AED28C" : "#B4D688";
    const rd = winter ? "#7C7A78" : "#6F6B66";
    c.fillStyle = tone(lk, g1); c.fillRect(0, 0, W, H);
    for (let i = -7; i < 21; i++) for (let j = -7; j < 21; j++) {
      const inside = i >= 0 && i < 14 && j >= 0 && j < 14, road = inside && (i === 6 || j === 6);
      let col = (i + j) % 2 === 0 ? g0 : g1;
      if (inside) { if (road) col = rd; else if (i < 6 && j >= 7) col = winter ? "#D3D8DD" : "#A9A6A0"; else if (i >= 7 && j >= 7 && j < 9) col = winter ? "#DDE0E2" : "#B9B4A8"; }
      else if (!winter) col = mix(col, "#9CC97A", 0.3 + 0.1 * (((i * 7 + j * 3) % 3 + 3) % 3));
      poly(c, [P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1)], tone(lk, col));
    }
    c.strokeStyle = tone(lk, "#E9E2D0"); c.lineWidth = 2; c.setLineDash([6, 6]);
    for (let k = 0; k < 14; k++) { if (k >= 5 && k <= 6) continue; let a = P(6.47, k + 0.2), b = P(6.47, k + 0.8); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); a = P(k + 0.2, 6.47); b = P(k + 0.8, 6.47); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); }
    c.setLineDash([]);
    poly(c, [P(-7, 3.2), P(-2, 3.6), P(3, -1.2), P(9, -5.5), P(14, -8), P(14, -6.6), P(9, -4.4), P(3.4, -0.2), P(-2, 4.9), P(-7, 4.5)], tone(lk, winter ? "#C5DCE9" : "#8EC5E8"));
  };
  return { objs, ground };
}

export function drawFrame(c: C, sc: Scene, st: SimState, lk: Look) {
  sc.ground(c, lk);
  // empty lots (drop targets): every free lot stays marked until it is used
  const used = new Set(st.loads.map((l) => l.lot));
  LOTS.forEach((l, i) => {
    if (used.has(i)) return;
    const pts = [P(l.x, l.y), P(l.x + 2, l.y), P(l.x + 2, l.y + 2), P(l.x, l.y + 2)] as [number, number][];
    const hot = st.hoverLot === i;
    poly(c, pts, hot ? "rgba(242,167,46,.45)" : st.dragging ? "rgba(255,255,255,.34)" : "rgba(255,255,255,.22)", hot ? "#F2A72E" : "#FFFFFF", 2.4);
    if (!st.dragging) { const m = P(l.x + 1, l.y + 1); c.fillStyle = "#FBF7EE"; c.strokeStyle = "#1D2320"; c.lineWidth = 1.6; c.beginPath(); c.arc(m[0], m[1], 13, 0, 7); c.fill(); c.stroke(); c.lineWidth = 2.2; c.beginPath(); c.moveTo(m[0] - 6, m[1]); c.lineTo(m[0] + 6, m[1]); c.moveTo(m[0], m[1] - 6); c.lineTo(m[0], m[1] + 6); c.stroke(); }
  });
  const loadObjs: Obj[] = st.loads.map((ld) => ({ k: LOTS[ld.lot].x + LOTS[ld.lot].y + 2.6, draw: (cc, s2, lk) => drawLoad(cc, s2, lk, ld) }));
  const list = loadObjs.length ? [...sc.objs, ...loadObjs].sort((a, b) => a.k - b.k) : sc.objs;
  list.forEach((o) => o.draw(c, st, lk));
  drawLines(c, st, lk);
  if (lk.night > 0) { c.fillStyle = `rgba(14,22,56,${0.1 * lk.night})`; c.fillRect(0, 0, W, H); }
  if (lk.season === "winter" || lk.season === "fall") {
    const r = rng(9); c.fillStyle = lk.season === "winter" ? "#FFFFFF" : "#D85A30";
    for (let i = 0; i < 80; i++) { const sx = r() * W, sy = r() * H, v = 0.4 + r(); const y = (sy + st.t * v * (lk.season === "winter" ? 0.9 : 0.6)) % H, x = sx + Math.sin((y + i * 9) / 30) * 6; c.globalAlpha = 0.6; c.fillRect(x, y, lk.season === "winter" ? 2 : 3, 2); }
    c.globalAlpha = 1;
  }
}
function drawLoad(c: C, st: SimState, lk: Look, ld: PlacedLoad) {
  const { x, y } = LOTS[ld.lot];
  if (ld.kind === "housing") return drawHousing(c, lk, x, y, ld.rise);
  if (ld.kind === "ev_depot") return drawDepot(c, st, lk, x, y, ld.rise);
  const h = 38 * Math.min(1, ld.rise);
  shadow(c, x, y, 2, 2, h); box(c, lk, x, y, 2, 2, h, "#7C8595", "#4F5666", "#3B4150");
  if (ld.rise < 1) return;
  const strip = st.phase === "stress" ? "#E5533D" : st.phase === "balancing" ? "#F2A72E" : "#3FD1A0";
  const q: [number, number][] = [P(x, y + 2), P(x + 2, y + 2), up(P(x + 2, y + 2), h), up(P(x, y + 2), h)];
  for (let k = 0; k < 4; k++) faceRect(c, lk, q, 0.08, 0.92, 0.14 + k * 0.2, 0.21 + k * 0.2, strip, true);
  const q2: [number, number][] = [P(x + 2, y), P(x + 2, y + 2), up(P(x + 2, y + 2), h), up(P(x + 2, y), h)];
  for (let k = 0; k < 4; k++) faceRect(c, lk, q2, 0.08, 0.92, 0.14 + k * 0.2, 0.19 + k * 0.2, mix(strip, "#000000", 0.25), true);
  ([[0.25, 0.25], [1.0, 0.3], [0.5, 1.0], [1.2, 1.1]] as const).forEach(([a, b]) => { box(c, lk, x + a, y + b, 0.5, 0.5, 7, "#DDE1E7", "#B3BAC5", "#98A0AD", h); const p = P(x + a + 0.25, y + b + 0.25); c.fillStyle = "#7C8595"; c.beginPath(); c.arc(p[0], p[1] - h - 9, 7, 0, 7); c.fill(); });
  if (st.phase === "stress") { const t = P(x + 1, y + 1); c.strokeStyle = `rgba(229,83,61,${0.7 - 0.3 * Math.sin(st.t / 5)})`; c.lineWidth = 3; c.beginPath(); c.ellipse(t[0], t[1] + 6, 70, 34, 0, 0, 7); c.stroke(); c.lineWidth = 2; c.globalAlpha = 0.4; c.beginPath(); c.ellipse(t[0], t[1] + 6, 92, 45, 0, 0, 7); c.stroke(); c.globalAlpha = 1; }
}
/** A new housing development: a 3 x 3 block of small homes (drawn units), rising with `rise`. */
function drawHousing(c: C, lk: Look, x: number, y: number, rise: number) {
  const rs = rng(31);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
    const k = i * 3 + j; if (k / 9 > rise) continue;
    const hx = x + 0.1 + i * 0.62, hy = y + 0.1 + j * 0.62; const o = house(hx, hy, rs() < 0.6, k);
    o.draw(c, { phase: "calm", active: { battery: false, ev: false, building: false }, loads: [], t: 0, dragging: false, hoverLot: null }, lk);
  }
}
/** A new EV depot: a paved lot with chargers and parked cars (drawn units). Chargers amber when EV charging is being shifted. */
function drawDepot(c: C, st: SimState, lk: Look, x: number, y: number, rise: number) {
  poly(c, [P(x, y), P(x + 2, y), P(x + 2, y + 2), P(x, y + 2)], tone(lk, lk.season === "winter" ? "#D3D8DD" : "#A9A6A0"));
  const cols = ["#1F9E89", "#5B9BE0", "#F0997B", "#E8C36A", "#8C7AE0", "#D4537E"];
  for (let a = 0; a < 2; a++) for (let b = 0; b < 4; b++) {
    if ((a * 4 + b) / 8 > rise) continue;
    const cx = x + 0.2 + b * 0.45, cy = y + 0.35 + a * 0.9, p = P(cx, cy), paused = st.active.ev && (a + b) % 2 === 0;
    c.fillStyle = tone(lk, "#4A4B4F"); c.fillRect(p[0] - 2, p[1] - 13, 4, 13); c.fillStyle = paused ? "#F2A72E" : "#1F9E89"; c.fillRect(p[0] - 3, p[1] - 17, 6, 5);
    car(cx - 0.05, cy + 0.32, cols[(a * 4 + b) % 6], "y").draw(c, st, lk);
  }
}
function drawLines(c: C, st: SimState, lk: Look) {
  const sub = P(6.5, 6.5), x1 = sub[0], y1 = sub[1] - 72;
  const targets: [string, [number, number]][] = [["homes", P(3, 3)], ["downtown", P(9.5, 2.4)], ["depot", P(2.6, 10)], ["industry", P(10, 9.4)]];
  st.loads.forEach((l) => targets.push([l.kind === "data_centre" ? "dc" : "load", P(LOTS[l.lot].x + 1, LOTS[l.lot].y + 1)]));
  targets.forEach(([name, q], i) => {
    const x2 = q[0], y2 = q[1] - 52, mx = (x1 + x2) / 2, my = Math.max(y1, y2) + 16;
    const hot = st.phase === "stress" && (name === "dc" || name === "industry" || name === "load");
    c.strokeStyle = tone(lk, hot ? "#E5533D" : st.phase === "stress" ? "#8A6A3A" : "#5A5B60"); c.lineWidth = hot ? 3.4 : 1.6;
    c.beginPath(); c.moveTo(x1, y1); c.quadraticCurveTo(mx, my, x2, y2); c.stroke();
    for (let k = 0; k < 5; k++) {
      const t = (((k + 0.5) / 5) + st.t * (hot ? 0.012 : 0.006) + i * 0.13) % 1;
      const px = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * mx + t * t * x2, py = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * my + t * t * y2;
      c.fillStyle = hot ? "#FFE1DA" : st.phase === "balancing" && name !== "dc" ? "#7FE0C9" : "#FFC24D"; c.beginPath(); c.arc(px, py, hot ? 3.6 : 2.6, 0, 7); c.fill();
    }
    c.strokeStyle = tone(lk, "#4A4B4F"); c.lineWidth = 2; c.beginPath(); c.moveTo(x2, y2); c.lineTo(x2, y2 + 52); c.stroke();
  });
}
export function lotAt(px: number, py: number): number | null {
  const u = (px - OX) / (TW / 2), v = (py - OY) / (TH / 2), x = (u + v) / 2, y = (v - u) / 2;
  const i = LOTS.findIndex((l) => x >= l.x - 0.3 && x <= l.x + 2.3 && y >= l.y - 0.3 && y <= l.y + 2.3);
  return i >= 0 ? i : null;
}
