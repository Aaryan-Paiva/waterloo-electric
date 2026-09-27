"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { IsoWorld } from "@/components/iso/IsoWorld";
import { ANCHORS, H, W, lotAt, type Phase, type Season } from "@/components/iso/scene";
import { fetchSandboxWorld, fetchWorldFor, postMatrix, postSandboxRun, type CellState, type DeviceParams, type Matrix, type SeasonCell, type Group, type LoadKind, type SandboxRun, type SandboxWorldInfo, type ScriptStep } from "@/lib/sandbox";
import { changeNote, derivePhase, gaugeLoad, hourLabel, nightOf } from "@/lib/sandboxLogic";

const INK = "#1D2320", PAPER = "#FBF7EE", LINE = "#D9D1BE", AMB = "#F2A72E", TEAL = "#1F9E89", CORAL = "#E5533D", BLUE = "#3F86D8", VIO = "#8C7AE0";
const FD = "var(--font-display), 'Bricolage Grotesque', system-ui, sans-serif", FB = "var(--font-body), 'IBM Plex Sans', system-ui, sans-serif";
const GROUP_COLOR: Record<Group, string> = { battery: BLUE, ev: TEAL, building: VIO };
const DELAY: Record<ScriptStep["kind"], number> = { request: 1100, owner_offer: 130, owner_decline: 130, validation_fail: 520, revision: 200, accepted: 130, clearing: 1200, dispatch: 1500, done: 0 };
const STEP_LABEL: Record<Group, string> = { battery: "Batteries discharge", ev: "EV charging shifted later", building: "Buildings and homes trim" };
interface HistoryEntry { n: number; loads: { kind: LoadKind; size: number; lot: number }[]; params: DeviceParams; provider: "stub" | "openai"; season: Season; hour: number; outcome: SandboxRun["outcome"]; overloadMw: number; absorbedMw: number; remainingMw: number; source: string }
interface Load { id: string; kind: LoadKind; size: number; lot: number }
const LOAD_META: Record<LoadKind, { label: string; unit: string; def: number; min: number; max: number; step: number; blurb: string }> = {
  data_centre: { label: "Data centre", unit: "MW", def: 20, min: 5, max: 60, step: 5, blurb: "runs 24/7" },
  housing: { label: "Housing", unit: "homes", def: 1000, min: 200, max: 5000, step: 200, blurb: "evening peak" },
  ev_depot: { label: "EV depot", unit: "chargers", def: 50, min: 10, max: 300, step: 10, blurb: "charges overnight" },
};
const SEASONS: Season[] = ["winter", "spring", "summer", "fall"];
const DEFAULTS: DeviceParams = { fleetSizeX: 1, batteryCount: 60, evFleetCount: 42, buildingCount: 108, solarCount: 24, batteryReservePct: 25, ownersEnrolledPct: 100, minPriceScale: 1, evShiftablePct: 60, evMaxDelayH: 4, buildingOffsetC: 2, buildingMaxHours: 3, reboundPct: 70, dcFlexPct: 0, dcMaxDeferH: 3 };
const cap = (s: string) => s[0].toUpperCase() + s.slice(1);

function theme(dark: boolean) { return { bg: dark ? "rgba(22,28,40,.92)" : "rgba(251,247,238,.95)", fg: dark ? "#F4EFE2" : INK, mut: dark ? "#A9B3C4" : "#6A6F66", ln: dark ? "#33405A" : LINE, sub: dark ? "rgba(255,255,255,.08)" : "rgba(29,35,32,.07)", dark }; }
type T = ReturnType<typeof theme>;
const Card = ({ t, x, y, w, h, children, pad = 16 }: { t: T; x: number; y: number; w: number; h?: number; children: React.ReactNode; pad?: number }) => (
  <div style={{ position: "absolute", left: x, top: y, width: w, height: h, boxSizing: "border-box", padding: pad, borderRadius: 16, background: t.bg, border: `1px solid ${t.ln}`, color: t.fg, fontFamily: FB }}>{children}</div>
);
const Pill = ({ children, bg, fg }: { children: React.ReactNode; bg: string; fg: string }) => <span style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 24, padding: "0 10px", borderRadius: 12, background: bg, color: fg, fontSize: 12, fontWeight: 600, whiteSpace: "nowrap" }}>{children}</span>;
const Dot = ({ c }: { c: string }) => <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: c }} />;

export function Sandbox() {
  const [world, setWorld] = useState<SandboxWorldInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [season, setSeason] = useState<Season>("summer");
  const [hour, setHour] = useState(14);
  const [loads, setLoads] = useState<Load[]>([]);
  const [dragKind, setDragKind] = useState<LoadKind>("data_centre");
  const [trayOpen, setTrayOpen] = useState(false);
  const [tab, setTab] = useState<"result" | "seasons" | "history">("result");
  const [matrix, setMatrix] = useState<{ key: string; data: Matrix } | null>(null);
  const [matrixBusy, setMatrixBusy] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const histN = useRef(0);
  const [devWorld, setDevWorld] = useState<SandboxWorldInfo | null>(null);
  const nextId = useRef(1);
  const [params, setParams] = useState<DeviceParams>(DEFAULTS);
  const [provider, setProvider] = useState<"stub" | "openai">("stub");
  const [run, setRun] = useState<SandboxRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [prog, setProg] = useState(0);
  const [drawer, setDrawer] = useState(false);
  const [speak, setSpeak] = useState(false);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const [hoverLot, setHoverLot] = useState<number | null>(null);
  const [scale, setScale] = useState(1);
  const [inspect, setInspect] = useState<Group | "solar" | null>(null);
  const [retry, setRetry] = useState(0);
  const [prev, setPrev] = useState<{ absorbed: number; remaining: number } | null>(null);
  const runRef = useRef<SandboxRun | null>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const reqId = useRef(0);
  const lastDone = useRef<{ absorbed: number; remaining: number } | null>(null);
  useEffect(() => { runRef.current = run; }, [run]);

  useEffect(() => { fetchSandboxWorld().then(setWorld).catch((e) => setErr(String(e))); }, []);
  useEffect(() => {
    const el = wrap.current; if (!el) return;
    const ro = new ResizeObserver(() => setScale(Math.min(el.clientWidth / W, (window.innerHeight - 24) / H)));
    ro.observe(el); return () => ro.disconnect();
  }, []);

  // one real run per (drop, size, season, hour, device parameters); debounced; stale responses are ignored
  useEffect(() => {
    if (loads.length === 0 || !world) return;
    const id = ++reqId.current;
    const h = setTimeout(() => {
      setBusy(true); setRun(null); setProg(0);
      postSandboxRun({ season, hour, loads: loads.map((l) => ({ kind: l.kind, size: l.size, lot: l.lot })), provider, incentivePerMwh: 100, deviceParams: params })
        .then((r) => { if (id === reqId.current) { const o = lastDone.current; setPrev(o); setRun(r); setProg(0); setErr(null); setTab("result");
          setHistory((h) => [...h, { n: ++histN.current, loads: loads.map((l) => ({ kind: l.kind, size: l.size, lot: l.lot })), params, provider, season, hour, outcome: r.outcome, overloadMw: r.overloadMw, absorbedMw: r.absorbedMw, remainingMw: r.remainingMw, source: r.decisionSource }]); } })
        .catch((e) => id === reqId.current && setErr(String(e)))
        .finally(() => id === reqId.current && setBusy(false));
    }, 350);
    return () => clearTimeout(h);
  }, [loads, season, hour, params, provider, world, retry]);

  // the season test: the same loads and settings against each season's real day (fetched when the Seasons tab is open)
  const cfgKey = JSON.stringify([loads.map((l) => [l.kind, l.size]), params, provider]);
  useEffect(() => {
    if (tab !== "seasons" || loads.length === 0 || (matrix && matrix.key === cfgKey)) return;
    let live = true;
    const h = setTimeout(() => {
      setMatrixBusy(true);
      postMatrix({ loads: loads.map((l) => ({ kind: l.kind, size: l.size })), provider, incentivePerMwh: 100, deviceParams: params })
        .then((d) => live && setMatrix({ key: cfgKey, data: d }))
        .catch((e) => live && setErr(String(e.message ?? e)))
        .finally(() => live && setMatrixBusy(false));
    }, 200);
    return () => { live = false; clearTimeout(h); };
  }, [tab, cfgKey, loads, provider, params, matrix]);

  // real totals for the device configuration the user built (debounced)
  useEffect(() => {
    const h = setTimeout(() => { fetchWorldFor(params).then(setDevWorld).catch(() => undefined); }, 250);
    return () => clearTimeout(h);
  }, [params]);

  // playback: reveal the recorded script step by step
  const steps = useMemo(() => run?.script ?? [], [run]);
  useEffect(() => {
    if (!run || prog >= steps.length) return;
    const t = setTimeout(() => setProg((p) => p + 1), prog === 0 ? 350 : DELAY[steps[prog - 1].kind]);
    return () => clearTimeout(t);
  }, [run, prog, steps]);
  const visible = useMemo(() => steps.slice(0, prog), [steps, prog]);
  const finished = !!run && prog >= steps.length;
  useEffect(() => { if (run && finished && run.hasOverload) lastDone.current = { absorbed: run.absorbedMw, remaining: run.remainingMw }; }, [run, finished]);
  const last = visible[visible.length - 1];

  useEffect(() => {
    if (!speak || !last || typeof speechSynthesis === "undefined") return;
    if (["request", "validation_fail", "dispatch", "done"].includes(last.kind)) { speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(last.text)); }
  }, [last, speak]);

  const base = world ? world.seasons[season].hourlyBaselineMw[hour] : 78;
  const capacity = world?.capacityMw ?? 90;
  const cleared = visible.some((s) => s.kind === "clearing");
  const lastDispatch = [...visible].reverse().find((s) => s.kind === "dispatch");
  const loadNow = gaugeLoad({ run, placed: loads.length > 0, finished, lastDispatchLoad: lastDispatch?.loadAfterMw, base, dcMw: loads.filter((l) => l.kind === "data_centre").reduce((a, l) => a + l.size, 0) });
  const phase: Phase = derivePhase({ run, placed: loads.length > 0, finished, cleared, capacity });
  const active = useMemo(() => {
    const a = { battery: false, ev: false, building: false };
    if (run && !finished) visible.forEach((s) => { if (s.kind === "dispatch" && s.group && (s.mw ?? 0) > 0.005) a[s.group] = true; });
    return a;
  }, [run, finished, visible]);
  const night = nightOf(hour), t = theme(night > 0.5);

  // drag and drop from the tray
  const toStage = useCallback((cx: number, cy: number) => { const r = stage.current!.getBoundingClientRect(); return { x: (cx - r.left) / scale, y: (cy - r.top) / scale }; }, [scale]);
  useEffect(() => {
    if (!drag) return;
    const mv = (e: PointerEvent) => { const p = toStage(e.clientX, e.clientY); setDrag(p); setHoverLot(lotAt(p.x, p.y)); };
    const up = (e: PointerEvent) => { const p = toStage(e.clientX, e.clientY); const l = lotAt(p.x, p.y); setDrag(null); setHoverLot(null); if (l !== null) { setLoads((cur) => cur.some((x) => x.lot === l) ? cur : [...cur, { id: `l${nextId.current++}`, kind: dragKind, size: LOAD_META[dragKind].def, lot: l }]); setDrawer(false); setTrayOpen(false); } };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); };
  }, [drag, toStage, dragKind]);

  const reset = () => { reqId.current++; setLoads([]); setRun(null); setProg(0); setBusy(false); setPrev(null); lastDone.current = null; setErr(null); setInspect(null); };
  const setP = (k: keyof DeviceParams, v: number) => setParams((p) => ({ ...p, [k]: v }));

  if (err && !world) return (
    <main style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#1D2320", fontFamily: FB }}>
      <div role="alert" style={{ maxWidth: 520, padding: 28, borderRadius: 16, background: PAPER, color: INK }}>
        <div style={{ fontFamily: FD, fontWeight: 700, fontSize: 20 }}>The simulation isn&apos;t running</div>
        <p style={{ fontSize: 14, lineHeight: 1.5 }}>Waterloo Electric couldn&apos;t reach its API. Start it, then try again:</p>
        <code style={{ display: "block", padding: 10, borderRadius: 8, background: "rgba(29,35,32,.07)", fontSize: 12 }}>cd apps/api &amp;&amp; .venv/bin/uvicorn src.main:app --port 8000</code>
        <button onClick={() => window.location.reload()} style={{ marginTop: 14, height: 36, padding: "0 16px", borderRadius: 18, border: 0, background: INK, color: PAPER, fontWeight: 600, cursor: "pointer" }}>Try again</button>
      </div>
    </main>
  );

  const caption = !world ? "Loading the world…" : busy ? "Asking the flexible devices for help…" : last ? last.text : loads.length > 0 ? "Loads added. Checking the grid…" : `${(devWorld ?? world).devices.battery + (devWorld ?? world).devices.ev_fleet + (devWorld ?? world).devices.building + (devWorld ?? world).devices.solar} device clusters are following their routines. Drag a new load onto an empty lot.`;
  const over = loadNow > capacity + 0.05;

  return (
    <main ref={wrap} style={{ width: "100%", minHeight: "100vh", background: "#1D2320", display: "flex", justifyContent: "center", alignItems: "flex-start" }}>
      <div style={{ width: W * scale, height: H * scale, position: "relative" }}>
        <div ref={stage} style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transform: `scale(${scale})`, transformOrigin: "0 0", overflow: "hidden", background: "#B4D688", fontFamily: FB }}>
          <div onClick={(e) => { const p = toStage(e.clientX, e.clientY); const hit = ([["battery", ANCHORS.battery], ["ev", ANCHORS.ev], ["building", ANCHORS.building]] as [Group, [number, number]][]).find(([, a]) => Math.hypot(p.x - a[0], p.y - 30 - a[1]) < 90); if (hit) { setInspect(hit[0]); setDrawer(false); } }} style={{ position: "absolute", inset: 0 }} aria-hidden="true" />
          <IsoWorld season={season} night={night} phase={phase} active={active} loads={loads} dragging={!!drag} hoverLot={hoverLot} />

          {/* brand + provenance */}
          <Card t={t} x={24} y={24} w={352} h={104}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 34, height: 34, borderRadius: 10, background: AMB, display: "flex", alignItems: "center", justifyContent: "center" }}><svg width="22" height="22" viewBox="0 0 24 24" fill={AMB} stroke={INK} strokeWidth="2" strokeLinejoin="round" aria-hidden="true"><path d="M13 2 4 14h7l-1 8 9-12h-7z" /></svg></div>
              <div><div style={{ fontFamily: FD, fontWeight: 700, fontSize: 20, lineHeight: 1.1 }}>Waterloo Electric</div><div style={{ fontSize: 12, color: t.mut }}>Flexible-grid sandbox</div></div>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 12 }}>
              {([[TEAL, "Demand: real shape, derived"], [AMB, "Devices: synthetic"], ["#9AA0A6", "Capacity: assumed"]] as const).map(([c, l]) => <span key={l} style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 22, padding: "0 9px", borderRadius: 11, background: t.sub, fontSize: 11, color: t.mut }}><Dot c={c} />{l}</span>)}
            </div>
          </Card>

          {/* gauge */}
          <Card t={t} x={24} y={144} w={352} h={150}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: t.mut }}><span>{cap(season)} · {run ? run.dateUsed : world?.seasons[season].referenceDay ?? ""} · {hourLabel(hour)}</span><span>{devWorld ? devWorld.devices.battery + devWorld.devices.ev_fleet + devWorld.devices.building + devWorld.devices.solar : 0} device clusters</span></div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 6 }}><span style={{ fontFamily: FD, fontWeight: 700, fontSize: 46, lineHeight: 1, letterSpacing: -1, fontVariantNumeric: "tabular-nums" }}>{loadNow.toFixed(1)}</span><span style={{ fontSize: 14, color: t.mut }}>MW of {capacity} MW</span></div>
            <div style={{ position: "relative", height: 12, borderRadius: 6, background: t.sub, marginTop: 12 }}>
              <div style={{ position: "absolute", left: 0, top: 0, height: 12, width: `${Math.min(100, (loadNow / 120) * 100)}%`, borderRadius: 6, background: over ? CORAL : loadNow > capacity * 0.85 ? AMB : TEAL, transition: "width .5s" }} />
              <div style={{ position: "absolute", left: `${(capacity / 120) * 100}%`, top: -5, width: 3, height: 22, borderRadius: 2, background: t.fg }} />
            </div>
            <div style={{ marginTop: 12 }}>
              {busy ? <Pill bg="#FCE9C4" fg="#7A4B00">Working…</Pill> : over ? <Pill bg="#FBD9D2" fg="#8C2415">Over capacity +{(loadNow - capacity).toFixed(1)} MW</Pill> : phase === "balanced" ? <Pill bg="#CDEFE6" fg="#0B5C4C">Within capacity</Pill> : phase === "balancing" ? <Pill bg="#FCE9C4" fg="#7A4B00">Rebalancing</Pill> : loadNow > capacity * 0.85 ? <Pill bg="#FCE9C4" fg="#7A4B00">Near the peak</Pill> : <Pill bg="#CDEFE6" fg="#0B5C4C">Normal</Pill>}
            </div>
          </Card>

          {/* right column: tray -> steps -> result; drawer on top */}
          {inspect && !drawer && <Inspector t={t} world={world} which={inspect} run={run} fleet={params.fleetSizeX} close={() => setInspect(null)} />}
          {!inspect && !drawer && (trayOpen || (!run && !busy)) && <Tray t={t} world={devWorld ?? world} loads={loads} setLoads={setLoads} onInspect={setInspect} onStart={(e, k) => { setDragKind(k); setDrag(toStage(e.clientX, e.clientY)); }} onKey={(k) => setLoads((cur) => { const free = [0, 1, 2, 3].find((i) => !cur.some((x) => x.lot === i)); return free === undefined ? cur : [...cur, { id: `l${nextId.current++}`, kind: k, size: LOAD_META[k].def, lot: free }]; })} onEdit={() => setDrawer(true)} reset={reset} />}
          {!inspect && !trayOpen && (busy || (run && !finished)) && !drawer && <Steps t={t} run={run} visible={visible} busy={busy} skip={() => setProg(steps.length)} />}
          {!inspect && !trayOpen && !drawer && run && (finished || tab !== "result") && <Tabs t={t} tab={tab} setTab={setTab} count={history.length} />}
          {!inspect && !trayOpen && !drawer && tab === "seasons" && run && (finished || true) && <Seasons t={t} matrix={matrix && matrix.key === cfgKey ? matrix.data : null} busy={matrixBusy} capacity={capacity} onPick={(c) => { setSeason(c.season); setHour(c.peakHour); setTab("result"); }} />}
          {!inspect && !trayOpen && !drawer && tab === "history" && <History t={t} history={history} onRestore={(h) => { setLoads(h.loads.map((l) => ({ id: `l${nextId.current++}`, kind: l.kind, size: l.size, lot: l.lot }))); setParams(h.params); setProvider(h.provider); setSeason(h.season); setHour(h.hour); setTab("result"); }} />}
          {!inspect && !trayOpen && !drawer && tab === "result" && run && finished && <Result t={t} run={run} note={changeNote(prev, run)} onLoads={() => setTrayOpen(true)} onEdit={() => setDrawer(true)} onSeason={(s) => { setSeason(s); setHour(s === "winter" ? 18 : 14); }} reset={reset} />}
          {drawer && <Drawer t={t} params={params} setP={setP} provider={provider} setProvider={setProvider} world={devWorld ?? world} close={() => setDrawer(false)} defaults={world?.defaults ?? DEFAULTS} />}

          {/* owner speech bubbles anchored to the real device groups */}
          {run && !finished && (["battery", "ev", "building"] as Group[]).map((g, gi) => {
            const s = [...visible].reverse().find((x) => x.group === g && x.kind !== "dispatch"); if (!s) return null;
            const [ax, ay] = ANCHORS[g]; const grey = s.kind === "owner_decline"; const warn = s.kind === "validation_fail" || s.kind === "revision";
            const c = grey ? "#7A7F87" : warn ? "#B7791F" : GROUP_COLOR[g];
            return <div key={g} style={{ position: "absolute", left: ax - 118, top: ay - 132 - gi * 6, width: 236, boxSizing: "border-box", padding: "9px 12px", borderRadius: 12, background: PAPER, border: `1px solid ${LINE}`, color: INK, boxShadow: "0 6px 16px rgba(20,30,20,.18)", fontSize: 13, lineHeight: 1.35 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600, color: c }}><Dot c={c} />{s.ownerName}</div><div>{s.text.replace(`${s.ownerName}: `, "").replace(`Physical check: ${s.ownerName} `, "Physical check: ")}</div>
              <div style={{ position: "absolute", left: 111, bottom: -7, width: 14, height: 14, transform: "rotate(45deg)", background: PAPER, borderRight: `1px solid ${LINE}`, borderBottom: `1px solid ${LINE}` }} />
            </div>;
          })}
          {phase === "stress" && !busy && loads.length > 0 && <div style={{ position: "absolute", left: ANCHORS.substation[0] - 92, top: ANCHORS.substation[1] - 138, padding: "6px 12px", borderRadius: 10, background: CORAL, color: "#fff", fontSize: 13, fontWeight: 600 }}>Substation overloaded</div>}

          {/* dock: always available, so more loads can be dropped at any time */}
          {loads.length < 4 && <div style={{ position: "absolute", left: 24, top: 712, height: 64, padding: "0 12px", borderRadius: 16, background: t.bg, border: `1px solid ${t.ln}`, color: t.fg, display: "flex", alignItems: "center", gap: 10, fontFamily: FB }}>
            <span style={{ fontSize: 12, color: t.mut }}>Drop a load</span>
            {(Object.keys(LOAD_META) as LoadKind[]).map((k) => <div key={k} role="button" tabIndex={0} aria-label={`Dock: ${LOAD_META[k].label}`} onPointerDown={(e) => { e.preventDefault(); setDragKind(k); setDrag(toStage(e.clientX, e.clientY)); }} style={{ padding: "6px 12px", borderRadius: 10, border: `2px dashed ${AMB}`, background: "rgba(242,167,46,.12)", cursor: "grab", fontSize: 13, fontWeight: 600, userSelect: "none", touchAction: "none" }}>{LOAD_META[k].label}</div>)}
          </div>}

          {/* bottom bar: caption + conditions */}
          <Card t={t} x={24} y={792} w={1392} h={84} pad={14}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", height: "100%" }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center", width: 760 }}>
                <button onClick={() => setSpeak((s) => !s)} aria-pressed={speak} aria-label="Read captions aloud" style={{ width: 40, height: 40, borderRadius: 12, border: 0, background: speak ? AMB : t.sub, cursor: "pointer", flex: "none" }}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={speak ? INK : t.fg} strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9z" /><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" /></svg></button>
                <div role="status" aria-live="polite" style={{ fontSize: 16, lineHeight: 1.4 }}>{caption}</div>
              </div>
              <div style={{ width: 520 }}>
                <div style={{ display: "flex", gap: 6 }} role="group" aria-label="Season">
                  {SEASONS.map((s) => <button key={s} onClick={() => setSeason(s)} aria-pressed={s === season} style={{ height: 30, padding: "0 12px", borderRadius: 15, fontSize: 13, fontWeight: 600, cursor: "pointer", background: s === season ? t.fg : "transparent", color: s === season ? (t.dark ? INK : PAPER) : t.fg, border: `1px solid ${s === season ? "transparent" : t.ln}` }}>{cap(s)}</button>)}
                  <span style={{ marginLeft: "auto", fontSize: 12, color: t.mut, alignSelf: "center" }}>{hourLabel(hour)}</span>
                </div>
                <div style={{ position: "relative", height: 26, marginTop: 6 }}>
                  <div style={{ position: "absolute", left: 0, right: 0, top: 10, height: 6, borderRadius: 3, background: "linear-gradient(90deg,#26305E 0%,#26305E 22%,#F7C97B 30%,#BFE3F5 45%,#BFE3F5 70%,#F2A25A 80%,#26305E 90%,#26305E 100%)" }} />
                  <input type="range" min={0} max={23} value={hour} onChange={(e) => setHour(+e.target.value)} aria-label="Hour of day" style={{ position: "absolute", left: 0, top: 3, width: "100%", accentColor: AMB, background: "transparent" }} />
                </div>
              </div>
            </div>
          </Card>

          {drag && <div style={{ position: "absolute", left: drag.x + 10, top: drag.y + 10, padding: "6px 10px", borderRadius: 8, background: "#2C2C2A", color: "#F1EFE8", fontSize: 12, pointerEvents: "none" }}>{LOAD_META[dragKind].label} · {LOAD_META[dragKind].def.toLocaleString()} {LOAD_META[dragKind].unit}</div>}
          {err && world && <div role="alert" style={{ position: "absolute", left: 400, top: 24, padding: "10px 14px", borderRadius: 10, background: CORAL, color: "#fff", fontSize: 13, display: "flex", gap: 12, alignItems: "center" }}>{err}<button onClick={() => { setErr(null); setRetry((n) => n + 1); }} style={{ height: 28, padding: "0 12px", borderRadius: 14, border: 0, background: "#fff", color: CORAL, fontWeight: 600, cursor: "pointer" }}>Try again</button></div>}
          {!world && <div role="status" style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(251,247,238,.75)", fontFamily: FD, fontSize: 22, fontWeight: 700 }}>Waking up the town…</div>}
        </div>
      </div>
    </main>
  );
}

function Tray({ t, world, loads, setLoads, onStart, onKey, onEdit, reset, onInspect }: { onInspect: (g: Group | "solar") => void; t: T; world: SandboxWorldInfo | null; loads: Load[]; setLoads: React.Dispatch<React.SetStateAction<Load[]>>; onStart: (e: React.PointerEvent, k: LoadKind) => void; onKey: (k: LoadKind) => void; onEdit: () => void; reset: () => void }) {
  const d = world?.devices; const rows: [string, string, number, Group | "solar"][] = [[BLUE, "Batteries", d?.battery ?? 0, "battery"], [TEAL, "EV fleets", d?.ev_fleet ?? 0, "ev"], [VIO, "Buildings", d?.building ?? 0, "building"], ["#22345A", "Solar", d?.solar ?? 0, "solar"]];
  const icon: Record<LoadKind, string> = { data_centre: "M4 3h16v18H4zM8 8h8M8 12h8M8 16h8", housing: "M3 11l9-7 9 7v9H3zM9 20v-6h6v6", ev_depot: "M13 2L4 14h7l-1 8 9-12h-7z" };
  return (
    <Card t={t} x={1096} y={24} w={320} h={loads.length > 2 ? 640 : 560}>
      <div style={{ fontFamily: FD, fontWeight: 700, fontSize: 17, marginBottom: 8 }}>Add new loads</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
        {(Object.keys(LOAD_META) as LoadKind[]).map((k) => (
          <div key={k} role="button" tabIndex={0} aria-label={`${LOAD_META[k].label}. Drag onto an empty lot, or press Enter to place it`} onPointerDown={(e) => { e.preventDefault(); onStart(e, k); }} onKeyDown={(e) => e.key === "Enter" && onKey(k)}
            style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, padding: "10px 4px", borderRadius: 12, border: `2px dashed ${AMB}`, background: "rgba(242,167,46,.12)", cursor: "grab", touchAction: "none", userSelect: "none", textAlign: "center" }}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke={t.fg} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={icon[k]} /></svg>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{LOAD_META[k].label}</div><div style={{ fontSize: 11, color: t.mut }}>{LOAD_META[k].def.toLocaleString()} {LOAD_META[k].unit}</div>
          </div>))}
      </div>
      <div style={{ fontSize: 12, color: t.mut, marginTop: 8 }}>Drag onto a highlighted empty lot (4 lots).</div>
      {loads.length > 0 && <div style={{ marginTop: 8 }}>
        <div style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: t.mut }}>Your loads</div>
        {loads.map((l) => { const m = LOAD_META[l.kind]; return (
          <div key={l.id} style={{ padding: "6px 0", borderTop: `1px solid ${t.ln}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}><span>{m.label} <b style={{ fontWeight: 600 }}>{l.size.toLocaleString()} {m.unit}</b></span>
              <button onClick={() => setLoads((cur) => cur.filter((x) => x.id !== l.id))} aria-label={`Remove ${m.label}`} style={{ border: 0, background: t.sub, color: t.fg, width: 24, height: 24, borderRadius: 12, cursor: "pointer" }}>×</button></div>
            <input type="range" min={m.min} max={m.max} step={m.step} value={l.size} aria-label={`${m.label} size`} onChange={(e) => setLoads((cur) => cur.map((x) => x.id === l.id ? { ...x, size: +e.target.value } : x))} style={{ width: "100%", accentColor: TEAL }} />
          </div>); })}
      </div>}
      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <button onClick={onEdit} style={{ height: 34, padding: "0 14px", borderRadius: 17, border: `1px solid ${t.ln}`, background: "transparent", color: t.fg, fontWeight: 600, fontSize: 13, cursor: "pointer" }}>Edit the devices</button>
        {loads.length > 0 && <button onClick={reset} style={{ height: 34, padding: "0 14px", borderRadius: 17, border: `1px solid ${t.ln}`, background: "transparent", color: t.fg, fontSize: 13, cursor: "pointer" }}>Reset</button>}
      </div>
      <div style={{ height: 1, background: t.ln, margin: "12px 0" }} />
      <div style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: t.mut, marginBottom: 4 }}>Device clusters (modeled)</div>
      {rows.map(([c, n, v, g]) => <button key={n} onClick={() => onInspect(g)} aria-label={`Inspect ${n}`} style={{ display: "flex", alignItems: "center", gap: 8, height: 26, fontSize: 13, width: "100%", border: 0, background: "transparent", color: t.fg, cursor: "pointer", padding: 0, textAlign: "left" }}><span style={{ width: 10, height: 10, borderRadius: 3, background: c }} /><span style={{ flexGrow: 1 }}>{n}</span><span style={{ color: t.mut }}>{v} ›</span></button>)}
      <div style={{ fontSize: 11, color: t.mut, marginTop: 6, lineHeight: 1.4 }}>Each is a seeded model with its own size and limits. {world?.ownerCount ?? 18} modeled owners control them. Change the counts in the editor.</div>
    </Card>
  );
}

function Steps({ t, run, visible, busy, skip }: { t: T; run: SandboxRun | null; visible: ScriptStep[]; busy: boolean; skip: () => void }) {
  const disp = (run?.script ?? []).filter((s) => s.kind === "dispatch");
  const shown = new Set(visible.filter((s) => s.kind === "dispatch").map((s) => s.i));
  const nextI = disp.find((s) => !shown.has(s.i))?.i;
  const fail = [...visible].reverse().find((s) => s.kind === "validation_fail");
  const offers = visible.filter((s) => s.kind === "accepted").length;
  return (
    <Card t={t} x={1096} y={24} w={320} h={420}>
      <div style={{ fontFamily: FD, fontWeight: 700, fontSize: 17 }}>{busy ? "Asking the devices…" : "The grid is rebalancing"}</div>
      <div style={{ fontSize: 12, color: t.mut, margin: "2px 0 10px" }}>Owners offer, a physics check validates, the optimizer decides</div>
      {disp.map((s) => { const done = shown.has(s.i), now = s.i === nextI && visible.some((v) => v.kind === "clearing"); const c = s.group ? GROUP_COLOR[s.group] : INK;
        return <div key={s.i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderTop: `1px solid ${t.ln}`, opacity: done || now ? 1 : 0.5 }}>
          <span style={{ width: 22, height: 22, borderRadius: "50%", boxSizing: "border-box", background: done ? TEAL : "transparent", border: done ? "none" : `${now ? 3 : 2}px solid ${now ? AMB : t.ln}`, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 12 }}>{done ? "✓" : ""}</span>
          <div style={{ flexGrow: 1, fontSize: 14 }}>{s.group ? STEP_LABEL[s.group] : s.text}</div><b style={{ fontVariantNumeric: "tabular-nums", color: done ? c : t.mut }}>{done ? ((s.mw ?? 0) > 0.005 ? `-${(s.mw ?? 0).toFixed(1)} MW` : "0.0") : ""}</b>
        </div>; })}
      {fail && <div style={{ marginTop: 12, padding: "10px 12px", borderRadius: 12, background: "#FCE9C4", color: "#5C3A00", fontSize: 13, lineHeight: 1.4 }}><b style={{ fontWeight: 600 }}>Physical check</b><br />{fail.text.replace("Physical check: ", "")}</div>}
      <div style={{ marginTop: 12, fontSize: 12, color: t.mut }}>{run ? `${run.ownersTotal} owners asked · ${offers} accepted so far` : ""}</div>
      {run && <button onClick={skip} style={{ marginTop: 10, height: 30, padding: "0 12px", borderRadius: 15, border: `1px solid ${t.ln}`, background: "transparent", color: t.fg, fontSize: 12, cursor: "pointer" }}>Skip to result</button>}
    </Card>
  );
}

function Result({ t, run, note, onEdit, onLoads, onSeason, reset }: { onLoads: () => void; note: string | null; t: T; run: SandboxRun; onEdit: () => void; onSeason: (s: Season) => void; reset: () => void }) {
  const groups: [Group, string][] = [["battery", "Batteries"], ["ev", "EV charging shifted"], ["building", "Buildings and homes"]];
  const vals = groups.map(([g, n]) => ({ g, n, v: Math.max(0, run.dispatchByGroup[g] ?? 0) }));
  const tot = Math.max(run.overloadMw, 0.001);
  const chip = { holds: ["Holds", "#CDEFE6", "#0B5C4C"], partly_holds: ["Partly holds", "#FCE9C4", "#7A4B00"], breaks: ["Breaks", "#FBD9D2", "#8C2415"], no_overload: ["Within capacity", "#CDEFE6", "#0B5C4C"] }[run.outcome];
  const lo = 50, hi = Math.max(110, ...run.curve.before), y = (v: number) => 150 - ((v - lo) / (hi - lo)) * 130, x = (h: number) => 20 + h * 12.2;
  const line = (a: number[]) => a.map((v, h) => `${x(h).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <Card t={t} x={1096} y={66} w={320} h={702}>
      <div style={{ fontFamily: FD, fontWeight: 700, fontSize: 17 }}>What the flexible grid did</div>
      <div style={{ fontSize: 12, color: t.mut, marginTop: 2 }}>{run.loads.map((l) => `${LOAD_META[l.kind].label} ${l.size.toLocaleString()} ${LOAD_META[l.kind].unit}`).join(" + ")}</div>
      {run.hasOverload ? <>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 10 }}><span style={{ fontFamily: FD, fontWeight: 700, fontSize: 40, lineHeight: 1 }}>{run.absorbedMw.toFixed(1)}</span><span style={{ fontSize: 14, color: t.mut }}>of {run.overloadMw.toFixed(1)} MW overload absorbed</span></div>
        <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}><Pill bg={chip[1]} fg={chip[2]}>{chip[0]}</Pill>{note && <span style={{ fontSize: 12, color: t.mut }}>{note}</span>}</div>
        <div style={{ display: "flex", borderRadius: 7, overflow: "hidden", marginTop: 14, height: 14, background: t.sub }}>{vals.map((x2) => <div key={x2.g} style={{ width: `${(x2.v / tot) * 100}%`, background: GROUP_COLOR[x2.g] }} />)}<div style={{ width: `${(run.remainingMw / tot) * 100}%`, background: CORAL }} /></div>
        <div style={{ marginTop: 8 }}>{vals.map((x2) => <div key={x2.g} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, height: 26 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: GROUP_COLOR[x2.g] }} /><span style={{ flexGrow: 1 }}>{x2.n}</span><b style={{ fontWeight: 600 }}>{x2.v.toFixed(1)} MW</b></div>)}
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, height: 26 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: CORAL }} /><span style={{ flexGrow: 1 }}>Still over capacity</span><b style={{ fontWeight: 600, color: CORAL }}>{run.remainingMw.toFixed(1)} MW</b></div></div>
      </> : <div style={{ marginTop: 10, fontSize: 14, lineHeight: 1.45 }}>{run.outcomeText}</div>}
      <div style={{ height: 1, background: t.ln, margin: "12px 0" }} />
      <div style={{ fontSize: 12, color: t.mut, marginBottom: 4 }}>The day, before (red) and after (green) · {run.dateUsed}</div>
      <svg width="288" height="170" viewBox="0 0 320 170" role="img" aria-label="Load across the day before and after the flexible grid acts, against the capacity line">
        <line x1="20" x2="322" y1={y(run.capacityMw)} y2={y(run.capacityMw)} stroke={t.fg} strokeWidth="1.4" strokeDasharray="5 4" />
        <text x="24" y={y(run.capacityMw) - 5} fontSize="10" fill={t.mut}>capacity {run.capacityMw} MW</text>
        <polyline points={line(run.curve.before)} fill="none" stroke={CORAL} strokeWidth="2.2" /><polyline points={line(run.curve.after)} fill="none" stroke={TEAL} strokeWidth="2.6" />
        <line x1={x(run.hour)} x2={x(run.hour)} y1="14" y2="152" stroke={t.mut} strokeDasharray="2 3" />
        <text x="20" y="166" fontSize="10" fill={t.mut}>12 am</text><text x="150" y="166" fontSize="10" fill={t.mut}>noon</text><text x="290" y="166" fontSize="10" fill={t.mut}>12 am</text>
      </svg>
      {run.hasOverload && <div style={{ fontSize: 12, color: t.mut, marginTop: 6, lineHeight: 1.4 }}>{run.outcomeText}</div>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        {([["Edit loads", onLoads, true], ["Edit the devices", onEdit, false], [run.season === "winter" ? "Try summer" : "Try winter", () => onSeason(run.season === "winter" ? "summer" : "winter"), false], ["Reset", reset, false]] as const).map(([l, f, p]) => <button key={l} onClick={f} style={{ height: 38, padding: "0 14px", borderRadius: 19, fontSize: 13, fontWeight: 600, cursor: "pointer", background: p ? t.fg : "transparent", color: p ? (t.dark ? INK : PAPER) : t.fg, border: `1px solid ${p ? t.fg : t.ln}` }}>{l}</button>)}
      </div>
      <div style={{ fontSize: 11, color: t.mut, marginTop: 10, lineHeight: 1.4 }}>Owner decisions: {run.decisionSource.replace(/_/g, " ")} · physical checks {run.checksPassed ? "passed" : "FAILED"}. Simulation on the real demand shape with synthetic devices. Not a forecast or an engineering study.</div>
    </Card>
  );
}

function Slider({ t, label, value, min, max, step, unit, set, note }: { t: T; label: string; value: number; min: number; max: number; step: number; unit: string; set: (n: number) => void; note?: string }) {
  return <label style={{ display: "block", marginTop: 8 }}><div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}><span>{label}</span><b style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{value}{unit}</b></div>
    <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => set(+e.target.value)} style={{ width: "100%", accentColor: TEAL, margin: "4px 0 0" }} aria-label={label} />{note && <div style={{ fontSize: 11, color: t.mut }}>{note}</div>}</label>;
}
function Drawer({ t, params: p, setP, provider, setProvider, world, close, defaults }: { t: T; params: DeviceParams; setP: (k: keyof DeviceParams, v: number) => void; provider: "stub" | "openai"; setProvider: (v: "stub" | "openai") => void; world: SandboxWorldInfo | null; close: () => void; defaults: DeviceParams }) {
  const sec = (title: string, sub: string) => <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 14, paddingTop: 10, borderTop: `1px solid ${t.ln}` }}><b style={{ fontFamily: FD, fontSize: 15 }}>{title}</b><span style={{ fontSize: 11, color: t.mut }}>{sub}</span></div>;
  const dd = world?.deviceDetails;
  return (
    <Card t={t} x={1096} y={24} w={320} h={744} pad={16}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><div style={{ fontFamily: FD, fontWeight: 700, fontSize: 17 }}>Edit the devices</div><button onClick={close} aria-label="Close editor" style={{ border: 0, background: t.sub, color: t.fg, width: 28, height: 28, borderRadius: 14, cursor: "pointer" }}>×</button></div>
      <div style={{ fontSize: 12, color: t.mut, marginTop: 2 }}>Applies on the next run. Assumptions, not measurements.</div>
      {sec("How many", "modeled clusters")}
      <Slider t={t} label="Batteries" value={p.batteryCount} min={0} max={200} step={5} unit="" set={(v) => setP("batteryCount", v)} note={dd ? `${dd.battery.totalMw} MW · ${dd.battery.totalMwh} MWh` : undefined} />
      <Slider t={t} label="EV charging fleets" value={p.evFleetCount} min={0} max={150} step={2} unit="" set={(v) => setP("evFleetCount", v)} note={dd ? `${dd.ev.totalMw} MW chargers · ${(dd.ev.vehicles ?? 0).toLocaleString()} vehicles` : undefined} />
      <Slider t={t} label="Buildings and homes" value={p.buildingCount} min={0} max={300} step={6} unit="" set={(v) => setP("buildingCount", v)} note={dd ? `${dd.building.totalMw} MW controllable load` : undefined} />
      <Slider t={t} label="Solar" value={p.solarCount} min={0} max={80} step={2} unit="" set={(v) => setP("solarCount", v)} note="context only, never dispatched" />
      {sec("Owners", "who decides")}
      <Slider t={t} label="Owners enrolled" value={p.ownersEnrolledPct} min={10} max={100} step={10} unit="%" set={(v) => setP("ownersEnrolledPct", v)} />
      <Slider t={t} label="Owners' minimum price" value={p.minPriceScale} min={0.5} max={2} step={0.25} unit="×" set={(v) => setP("minPriceScale", v)} />
      {sec("Batteries", "reserve")}
      <Slider t={t} label="Reserve kept" value={p.batteryReservePct} min={5} max={70} step={5} unit="%" set={(v) => setP("batteryReservePct", v)} />
      {sec("EV charging", "shiftable")}
      <Slider t={t} label="Charging that can move" value={p.evShiftablePct} min={10} max={100} step={10} unit="%" set={(v) => setP("evShiftablePct", v)} />
      {sec("Buildings and homes", "comfort")}
      <Slider t={t} label="Temperature offset allowed" value={p.buildingOffsetC} min={0.5} max={4} step={0.5} unit="°C" set={(v) => setP("buildingOffsetC", v)} />
      <Slider t={t} label="Longest curtailment" value={p.buildingMaxHours} min={1} max={6} step={1} unit=" h" set={(v) => setP("buildingMaxHours", v)} />
      <Slider t={t} label="Rebound afterwards" value={p.reboundPct} min={30} max={100} step={10} unit="%" set={(v) => setP("reboundPct", v)} />
      <div style={{ fontSize: 12, color: t.mut, marginTop: 10 }}>Load sizes are set on each load in the tray. A data centre&apos;s own flexible compute: next.</div>
      {sec("Owner agents", "who decides")}
      <select value={provider} onChange={(e) => setProvider(e.target.value as "stub" | "openai")} aria-label="Owner agent provider" style={{ width: "100%", height: 34, borderRadius: 8, border: `1px solid ${t.ln}`, background: t.sub, color: t.fg, marginTop: 8, padding: "0 8px" }}>
        <option value="stub">Deterministic stub (no API)</option><option value="openai">Real LLM owners (OpenAI, needs a key)</option>
      </select>
      <button onClick={() => (Object.keys(defaults) as (keyof DeviceParams)[]).forEach((k) => setP(k, defaults[k]))} style={{ marginTop: 12, height: 34, padding: "0 14px", borderRadius: 17, border: `1px solid ${t.ln}`, background: "transparent", color: t.fg, fontSize: 13, cursor: "pointer" }}>Reset to defaults</button>
    </Card>
  );
}

function Inspector({ t, world, which, run, fleet, close }: { t: T; world: SandboxWorldInfo | null; which: Group | "solar"; run: SandboxRun | null; fleet: number; close: () => void }) {
  const d = world?.deviceDetails[which]; const c = which === "solar" ? "#22345A" : GROUP_COLOR[which];
  if (!d) return null;
  const scaled = which === "solar" ? d.totalMw : d.totalMw * fleet;
  const now = which !== "solar" && run ? run.dispatchByGroup[which] : null;
  const row = (k: string, v: string) => <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "6px 0", borderTop: `1px solid ${t.ln}` }}><span style={{ color: t.mut }}>{k}</span><b style={{ fontWeight: 600 }}>{v}</b></div>;
  return (
    <Card t={t} x={1096} y={24} w={320} h={420}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><div style={{ display: "flex", alignItems: "center", gap: 8 }}><span style={{ width: 12, height: 12, borderRadius: 3, background: c }} /><span style={{ fontFamily: FD, fontWeight: 700, fontSize: 17 }}>{d.label}</span></div><button onClick={close} aria-label="Close inspector" style={{ border: 0, background: t.sub, color: t.fg, width: 28, height: 28, borderRadius: 14, cursor: "pointer" }}>×</button></div>
      <div style={{ fontSize: 13, margin: "10px 0", lineHeight: 1.45 }}>{d.does}</div>
      {row("Clusters (modeled)", `${d.clusters}`)}
      {row(which === "battery" ? "Power at this fleet size" : which === "ev" ? "Charger capacity" : which === "building" ? "Controllable load" : "Installed", `${scaled.toFixed(1)} MW`)}
      {d.totalMwh != null && row("Storage", `${(d.totalMwh * fleet).toFixed(1)} MWh`)}
      {d.vehicles != null && row("Vehicles", `${Math.round(d.vehicles * fleet).toLocaleString()}`)}
      {row("Controlled by", d.owners ? `${d.owners} owners` : "no owner (context only)")}
      {now != null && row("This run, at the chosen hour", `${now > 0.005 ? "-" : ""}${Math.abs(now).toFixed(1)} MW`)}
      <div style={{ fontSize: 12, color: t.mut, marginTop: 10, lineHeight: 1.45 }}><b style={{ fontWeight: 600 }}>Limits.</b> {d.limits}</div>
      <div style={{ fontSize: 11, color: t.mut, marginTop: 8 }}>Synthetic and seeded. A cluster stands for many units.</div>
    </Card>
  );
}

function Tabs({ t, tab, setTab, count }: { t: T; tab: "result" | "seasons" | "history"; setTab: (x: "result" | "seasons" | "history") => void; count: number }) {
  const items: ["result" | "seasons" | "history", string][] = [["result", "Result"], ["seasons", "Seasons"], ["history", `Runs (${count})`]];
  return <div role="tablist" style={{ position: "absolute", left: 1096, top: 24, width: 320, display: "flex", gap: 6 }}>
    {items.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} style={{ flex: 1, height: 34, borderRadius: 17, fontSize: 13, fontWeight: 600, cursor: "pointer", border: `1px solid ${tab === k ? "transparent" : t.ln}`, background: tab === k ? t.fg : t.bg, color: tab === k ? (t.dark ? INK : PAPER) : t.fg }}>{l}</button>)}
  </div>;
}

const CELL_COLOR: Record<CellState, string> = { within: "#B9D9CE", absorbed: TEAL, over: CORAL };
const OUT_CHIP: Record<string, [string, string, string]> = { holds: ["Holds", "#CDEFE6", "#0B5C4C"], partly_holds: ["Partly holds", "#FCE9C4", "#7A4B00"], breaks: ["Breaks", "#FBD9D2", "#8C2415"], no_overload: ["No overload", "#E4EBE6", "#3B4A40"] };
const PERIOD_MARK: Record<CellState, string> = { within: "✓ ok", absorbed: "✓ absorbed", over: "✕ over" };

function Seasons({ t, matrix, busy, capacity, onPick }: { t: T; matrix: Matrix | null; busy: boolean; capacity: number; onPick: (c: SeasonCell) => void }) {
  return (
    <Card t={t} x={1096} y={66} w={320} h={702}>
      <div style={{ fontFamily: FD, fontWeight: 700, fontSize: 17 }}>Does it hold in every season?</div>
      <div style={{ fontSize: 12, color: t.mut, margin: "2px 0 8px" }}>Your loads and device settings against each season&apos;s real worst day (2021–2025), capacity {capacity} MW.</div>
      {!matrix && <div role="status" style={{ padding: 20, fontSize: 14, color: t.mut }}>{busy ? "Testing all four seasons…" : "Preparing the season test…"}</div>}
      <div style={{ maxHeight: 548, overflowY: "auto", paddingRight: 2 }}>
      {matrix && matrix.cells.map((c) => { const chip = OUT_CHIP[c.outcome]; return (
        <button key={c.season} onClick={() => onPick(c)} aria-label={`${c.season}: ${chip[0]}. Open this season`} style={{ display: "block", width: "100%", textAlign: "left", padding: "10px 12px", marginBottom: 8, borderRadius: 12, border: `1px solid ${t.ln}`, background: t.sub, color: t.fg, cursor: "pointer" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><b style={{ fontFamily: FD, fontSize: 15 }}>{cap(c.season)}</b><Pill bg={chip[1]} fg={chip[2]}>{chip[0]}</Pill></div>
          <div style={{ fontSize: 12, color: t.mut, marginTop: 2 }}>{c.dateUsed} · peak {hourLabel(c.peakHour)}</div>
          <div style={{ fontSize: 13, marginTop: 6, fontVariantNumeric: "tabular-nums" }}>{c.overloadMw > 0 ? <>Overload {c.overloadMw.toFixed(1)} MW · absorbed <b style={{ fontWeight: 600 }}>{c.absorbedMw.toFixed(1)}</b> · still over <b style={{ fontWeight: 600, color: c.remainingMw > 0.05 ? CORAL : t.fg }}>{c.remainingMw.toFixed(1)}</b> MW</> : <>Peak {c.peakLoadMw.toFixed(1)} MW, within capacity all day</>}</div>
          <div style={{ display: "flex", gap: 2, marginTop: 8 }} aria-hidden="true">{c.hourStates.map((st, i) => <span key={i} title={`${hourLabel(i)}: ${st}`} style={{ flex: 1, height: 12, borderRadius: 2, background: CELL_COLOR[st] }} />)}</div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: t.mut, marginTop: 2 }}><span>12 am</span><span>noon</span><span>12 am</span></div>
          <div style={{ display: "flex", gap: 6, marginTop: 6, fontSize: 11 }}>{(["morning", "afternoon", "evening"] as const).map((k) => <span key={k} title={`${cap(k)}: ${PERIOD_MARK[c.periods[k]]}`} style={{ flex: 1, padding: "2px 6px", borderRadius: 8, background: t.bg, border: `1px solid ${t.ln}`, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}><span style={{ color: CELL_COLOR[c.periods[k]] }}>●</span> {cap(k).slice(0, 4)}. {c.periods[k] === "over" ? "over" : "ok"}</span>)}</div>
          {c.hoursOverBefore > 0 && <div style={{ fontSize: 11, color: t.mut, marginTop: 4 }}>Hours over capacity: {c.hoursOverBefore} → {c.hoursOverAfter}</div>}
        </button>); })}
      </div>
      {matrix && <div style={{ fontSize: 11, color: t.mut, lineHeight: 1.4, marginTop: 6 }}><span style={{ color: CELL_COLOR.within }}>■</span> within capacity &nbsp;<span style={{ color: TEAL }}>■</span> overload absorbed &nbsp;<span style={{ color: CORAL }}>■</span> still over. Owner decisions: {matrix.cells[0]?.decisionSource.replace(/_/g, " ")}. A stress test on history, not a forecast.</div>}
    </Card>
  );
}

function History({ t, history, onRestore }: { t: T; history: HistoryEntry[]; onRestore: (h: HistoryEntry) => void }) {
  const D = DEFAULTS;
  const changed = (p: DeviceParams) => [p.batteryCount !== D.batteryCount && `${p.batteryCount} batteries`, p.evFleetCount !== D.evFleetCount && `${p.evFleetCount} EV fleets`, p.buildingCount !== D.buildingCount && `${p.buildingCount} buildings`, p.batteryReservePct !== D.batteryReservePct && `reserve ${p.batteryReservePct}%`, p.evShiftablePct !== D.evShiftablePct && `EV movable ${p.evShiftablePct}%`, p.ownersEnrolledPct !== D.ownersEnrolledPct && `${p.ownersEnrolledPct}% enrolled`, p.minPriceScale !== D.minPriceScale && `price ×${p.minPriceScale}`, p.buildingOffsetC !== D.buildingOffsetC && `${p.buildingOffsetC}°C offset`].filter(Boolean).join(" · ") || "default devices";
  return (
    <Card t={t} x={1096} y={66} w={320} h={702}>
      <div style={{ fontFamily: FD, fontWeight: 700, fontSize: 17 }}>Runs</div>
      <div style={{ fontSize: 12, color: t.mut, margin: "2px 0 8px" }}>Every run in this session. Load one to restore its loads, devices and conditions.</div>
      <div style={{ maxHeight: 610, overflowY: "auto" }}>
        {history.length === 0 && <div style={{ fontSize: 13, color: t.mut }}>No runs yet.</div>}
        {[...history].reverse().map((h) => { const chip = OUT_CHIP[h.outcome]; return (
          <div key={h.n} style={{ padding: "10px 0", borderTop: `1px solid ${t.ln}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><b style={{ fontFamily: FD, fontSize: 14 }}>Run {String(h.n).padStart(2, "0")} · {cap(h.season)} {hourLabel(h.hour)}</b><Pill bg={chip[1]} fg={chip[2]}>{chip[0]}</Pill></div>
            <div style={{ fontSize: 12, marginTop: 4 }}>{h.loads.map((l) => `${LOAD_META[l.kind].label} ${l.size.toLocaleString()} ${LOAD_META[l.kind].unit}`).join(" + ")}</div>
            <div style={{ fontSize: 11, color: t.mut, marginTop: 2 }}>{changed(h.params)}</div>
            <div style={{ fontSize: 13, marginTop: 4, fontVariantNumeric: "tabular-nums" }}>{h.overloadMw > 0 ? `absorbed ${h.absorbedMw.toFixed(1)} of ${h.overloadMw.toFixed(1)} MW` : "within capacity"}</div>
            <button onClick={() => onRestore(h)} style={{ marginTop: 6, height: 28, padding: "0 12px", borderRadius: 14, border: `1px solid ${t.ln}`, background: "transparent", color: t.fg, fontSize: 12, cursor: "pointer" }}>Load this setup</button>
          </div>); })}
      </div>
    </Card>
  );
}
