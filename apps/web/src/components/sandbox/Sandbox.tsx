"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { IsoWorld } from "@/components/iso/IsoWorld";
import { ANCHORS, H, LOTS, W, lotAt, type Phase, type Season } from "@/components/iso/scene";
import { fetchSandboxWorld, postSandboxRun, type DeviceParams, type Group, type SandboxRun, type SandboxWorldInfo, type ScriptStep } from "@/lib/sandbox";
import { changeNote, derivePhase, gaugeLoad, hourLabel, nightOf } from "@/lib/sandboxLogic";

const INK = "#1D2320", PAPER = "#FBF7EE", LINE = "#D9D1BE", AMB = "#F2A72E", TEAL = "#1F9E89", CORAL = "#E5533D", BLUE = "#3F86D8", VIO = "#8C7AE0";
const FD = "var(--font-display), 'Bricolage Grotesque', system-ui, sans-serif", FB = "var(--font-body), 'IBM Plex Sans', system-ui, sans-serif";
const GROUP_COLOR: Record<Group, string> = { battery: BLUE, ev: TEAL, building: VIO };
const DELAY: Record<ScriptStep["kind"], number> = { request: 1100, owner_offer: 130, owner_decline: 130, validation_fail: 520, revision: 200, accepted: 130, clearing: 1200, dispatch: 1500, done: 0 };
const STEP_LABEL: Record<Group, string> = { battery: "Batteries discharge", ev: "EV charging shifted later", building: "Buildings and homes trim" };
const SEASONS: Season[] = ["winter", "spring", "summer", "fall"];
const DEFAULTS: DeviceParams = { fleetSizeX: 3, batteryReservePct: 25, ownersEnrolledPct: 100, minPriceScale: 1, evShiftablePct: 60, evMaxDelayH: 4, buildingOffsetC: 2, buildingMaxHours: 3, reboundPct: 70, dcFlexPct: 0, dcMaxDeferH: 3 };
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
  const [dcMw, setDcMw] = useState(20);
  const [lot, setLot] = useState<number | null>(null);
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
    if (lot === null || !world) return;
    const id = ++reqId.current;
    const h = setTimeout(() => {
      setBusy(true); setRun(null); setProg(0);
      postSandboxRun({ season, hour, dcMw, provider, incentivePerMwh: 100, deviceParams: params })
        .then((r) => { if (id === reqId.current) { const o = lastDone.current; setPrev(o); setRun(r); setProg(0); setErr(null); } })
        .catch((e) => id === reqId.current && setErr(String(e)))
        .finally(() => id === reqId.current && setBusy(false));
    }, 350);
    return () => clearTimeout(h);
  }, [lot, season, hour, dcMw, params, provider, world, retry]);

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
  const loadNow = gaugeLoad({ run, placed: lot !== null, finished, lastDispatchLoad: lastDispatch?.loadAfterMw, base, dcMw });
  const phase: Phase = derivePhase({ run, placed: lot !== null, finished, cleared, capacity });
  const active = useMemo(() => {
    const a = { battery: false, ev: false, building: false };
    if (run && !finished) visible.forEach((s) => { if (s.kind === "dispatch" && s.group && (s.mw ?? 0) > 0.005) a[s.group] = true; });
    return a;
  }, [run, finished, visible]);
  const night = nightOf(hour), t = theme(night > 0.5);
  const dc = lot !== null ? { x: LOTS[lot].x, y: LOTS[lot].y } : null;

  // drag and drop from the tray
  const toStage = useCallback((cx: number, cy: number) => { const r = stage.current!.getBoundingClientRect(); return { x: (cx - r.left) / scale, y: (cy - r.top) / scale }; }, [scale]);
  useEffect(() => {
    if (!drag) return;
    const mv = (e: PointerEvent) => { const p = toStage(e.clientX, e.clientY); setDrag(p); setHoverLot(lotAt(p.x, p.y)); };
    const up = (e: PointerEvent) => { const p = toStage(e.clientX, e.clientY); const l = lotAt(p.x, p.y); setDrag(null); setHoverLot(null); if (l !== null) { setLot(l); setDrawer(false); } };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); };
  }, [drag, toStage]);

  const reset = () => { reqId.current++; setLot(null); setRun(null); setProg(0); setBusy(false); setPrev(null); lastDone.current = null; setErr(null); setInspect(null); };
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

  const caption = !world ? "Loading the world…" : busy ? "Asking the flexible devices for help…" : last ? last.text : lot !== null ? "Data centre added. Checking the grid…" : `${(world.devices.battery + world.devices.ev_fleet + world.devices.building + world.devices.solar)} device clusters are following their routines. Drag the data centre onto an empty lot.`;
  const over = loadNow > capacity + 0.05;

  return (
    <main ref={wrap} style={{ width: "100%", minHeight: "100vh", background: "#1D2320", display: "flex", justifyContent: "center", alignItems: "flex-start" }}>
      <div style={{ width: W * scale, height: H * scale, position: "relative" }}>
        <div ref={stage} style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transform: `scale(${scale})`, transformOrigin: "0 0", overflow: "hidden", background: "#B4D688", fontFamily: FB }}>
          <div onClick={(e) => { const p = toStage(e.clientX, e.clientY); const hit = ([["battery", ANCHORS.battery], ["ev", ANCHORS.ev], ["building", ANCHORS.building]] as [Group, [number, number]][]).find(([, a]) => Math.hypot(p.x - a[0], p.y - 30 - a[1]) < 90); if (hit) { setInspect(hit[0]); setDrawer(false); } }} style={{ position: "absolute", inset: 0 }} aria-hidden="true" />
          <IsoWorld season={season} night={night} phase={phase} active={active} dc={dc} dragging={!!drag} hoverLot={hoverLot} />

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
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: t.mut }}><span>{cap(season)} · {run ? run.dateUsed : world?.seasons[season].referenceDay ?? ""} · {hourLabel(hour)}</span><span>{world ? world.devices.battery + world.devices.ev_fleet + world.devices.building + world.devices.solar : 0} device clusters</span></div>
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
          {!inspect && !run && !busy && !drawer && <Tray t={t} world={world} dcMw={dcMw} setDcMw={setDcMw} placed={lot !== null} onInspect={setInspect} onStart={(e) => setDrag(toStage(e.clientX, e.clientY))} onKey={() => setLot(1)} onEdit={() => setDrawer(true)} reset={reset} />}
          {!inspect && (busy || (run && !finished)) && !drawer && <Steps t={t} run={run} visible={visible} busy={busy} skip={() => setProg(steps.length)} />}
          {!inspect && run && finished && !drawer && <Result t={t} run={run} note={changeNote(prev, run)} onEdit={() => setDrawer(true)} onSeason={(s) => { setSeason(s); setHour(s === "winter" ? 18 : 14); }} reset={reset} />}
          {drawer && <Drawer t={t} params={params} setP={setP} provider={provider} setProvider={setProvider} dcMw={dcMw} setDcMw={setDcMw} close={() => setDrawer(false)} defaults={world?.defaults ?? DEFAULTS} />}

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
          {phase === "stress" && !busy && lot !== null && <div style={{ position: "absolute", left: ANCHORS.substation[0] - 92, top: ANCHORS.substation[1] - 138, padding: "6px 12px", borderRadius: 10, background: CORAL, color: "#fff", fontSize: 13, fontWeight: 600 }}>Substation overloaded</div>}

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

          {drag && <div style={{ position: "absolute", left: drag.x + 10, top: drag.y + 10, padding: "6px 10px", borderRadius: 8, background: "#2C2C2A", color: "#F1EFE8", fontSize: 12, pointerEvents: "none" }}>Data centre · {dcMw} MW</div>}
          {err && world && <div role="alert" style={{ position: "absolute", left: 400, top: 24, padding: "10px 14px", borderRadius: 10, background: CORAL, color: "#fff", fontSize: 13, display: "flex", gap: 12, alignItems: "center" }}>{err}<button onClick={() => { setErr(null); setRetry((n) => n + 1); }} style={{ height: 28, padding: "0 12px", borderRadius: 14, border: 0, background: "#fff", color: CORAL, fontWeight: 600, cursor: "pointer" }}>Try again</button></div>}
          {!world && <div role="status" style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(251,247,238,.75)", fontFamily: FD, fontSize: 22, fontWeight: 700 }}>Waking up the town…</div>}
        </div>
      </div>
    </main>
  );
}

function Tray({ t, world, dcMw, setDcMw, placed, onStart, onKey, onEdit, reset, onInspect }: { onInspect: (g: Group | "solar") => void; t: T; world: SandboxWorldInfo | null; dcMw: number; setDcMw: (n: number) => void; placed: boolean; onStart: (e: React.PointerEvent) => void; onKey: () => void; onEdit: () => void; reset: () => void }) {
  const d = world?.devices; const rows: [string, string, number, Group | "solar"][] = [[BLUE, "Batteries", d?.battery ?? 0, "battery"], [TEAL, "EV fleets", d?.ev_fleet ?? 0, "ev"], [VIO, "Buildings", d?.building ?? 0, "building"], ["#22345A", "Solar", d?.solar ?? 0, "solar"]];
  return (
    <Card t={t} x={1096} y={24} w={320} h={420}>
      <div style={{ fontFamily: FD, fontWeight: 700, fontSize: 17, marginBottom: 10 }}>Add to the world</div>
      <div role="button" tabIndex={0} aria-label="Data centre. Drag onto an empty lot, or press Enter to place it" onPointerDown={(e) => { e.preventDefault(); onStart(e); }} onKeyDown={(e) => e.key === "Enter" && onKey()}
        style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 12, border: `2px dashed ${AMB}`, background: "rgba(242,167,46,.12)", cursor: "grab", touchAction: "none", userSelect: "none" }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: "#4F5666", display: "flex", alignItems: "center", justifyContent: "center" }}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#F4EFE2" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h8" /></svg></div>
        <div style={{ flexGrow: 1 }}><div style={{ fontWeight: 600, fontSize: 15 }}>Data centre</div><div style={{ fontSize: 12, color: t.mut }}>{dcMw} MW · runs 24/7</div></div>
      </div>
      <div style={{ fontSize: 12, color: t.mut, marginTop: 10 }}>{placed ? "Placed. Drag again to move it." : "Drag onto a highlighted empty lot"}</div>
      <label style={{ display: "block", marginTop: 12, fontSize: 13 }}>Size <b style={{ fontWeight: 600 }}>{dcMw} MW</b><input type="range" min={5} max={60} value={dcMw} onChange={(e) => setDcMw(+e.target.value)} style={{ width: "100%", accentColor: TEAL }} aria-label="Data centre size in megawatts" /></label>
      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <button onClick={onEdit} style={{ height: 34, padding: "0 14px", borderRadius: 17, border: `1px solid ${t.ln}`, background: "transparent", color: t.fg, fontWeight: 600, fontSize: 13, cursor: "pointer" }}>Edit the devices</button>
        {placed && <button onClick={reset} style={{ height: 34, padding: "0 14px", borderRadius: 17, border: `1px solid ${t.ln}`, background: "transparent", color: t.fg, fontSize: 13, cursor: "pointer" }}>Reset</button>}
      </div>
      <div style={{ height: 1, background: t.ln, margin: "14px 0" }} />
      <div style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: t.mut, marginBottom: 6 }}>Device fleets (synthetic)</div>
      {rows.map(([c, n, v, g]) => <button key={n} onClick={() => onInspect(g)} aria-label={`Inspect ${n}`} style={{ display: "flex", alignItems: "center", gap: 8, height: 26, fontSize: 13, width: "100%", border: 0, background: "transparent", color: t.fg, cursor: "pointer", padding: 0, textAlign: "left" }}><span style={{ width: 10, height: 10, borderRadius: 3, background: c }} /><span style={{ flexGrow: 1 }}>{n}</span><span style={{ color: t.mut }}>{v} clusters ›</span></button>)}
      <div style={{ fontSize: 11, color: t.mut, marginTop: 8, lineHeight: 1.4 }}>Each cluster stands for many real-world units. {world?.ownerCount ?? 18} modeled owners control them.</div>
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

function Result({ t, run, note, onEdit, onSeason, reset }: { note: string | null; t: T; run: SandboxRun; onEdit: () => void; onSeason: (s: Season) => void; reset: () => void }) {
  const groups: [Group, string][] = [["battery", "Batteries"], ["ev", "EV charging shifted"], ["building", "Buildings and homes"]];
  const vals = groups.map(([g, n]) => ({ g, n, v: Math.max(0, run.dispatchByGroup[g] ?? 0) }));
  const tot = Math.max(run.overloadMw, 0.001);
  const chip = { holds: ["Holds", "#CDEFE6", "#0B5C4C"], partly_holds: ["Partly holds", "#FCE9C4", "#7A4B00"], breaks: ["Breaks", "#FBD9D2", "#8C2415"], no_overload: ["Within capacity", "#CDEFE6", "#0B5C4C"] }[run.outcome];
  const lo = 50, hi = Math.max(110, ...run.curve.before), y = (v: number) => 150 - ((v - lo) / (hi - lo)) * 130, x = (h: number) => 20 + h * 12.2;
  const line = (a: number[]) => a.map((v, h) => `${x(h).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <Card t={t} x={1096} y={24} w={320} h={744}>
      <div style={{ fontFamily: FD, fontWeight: 700, fontSize: 17 }}>What the flexible grid did</div>
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
        {([["Edit the devices", onEdit, true], [run.season === "winter" ? "Try summer" : "Try winter", () => onSeason(run.season === "winter" ? "summer" : "winter"), false], ["Reset", reset, false]] as const).map(([l, f, p]) => <button key={l} onClick={f} style={{ height: 38, padding: "0 14px", borderRadius: 19, fontSize: 13, fontWeight: 600, cursor: "pointer", background: p ? t.fg : "transparent", color: p ? (t.dark ? INK : PAPER) : t.fg, border: `1px solid ${p ? t.fg : t.ln}` }}>{l}</button>)}
      </div>
      <div style={{ fontSize: 11, color: t.mut, marginTop: 10, lineHeight: 1.4 }}>Owner decisions: {run.decisionSource.replace(/_/g, " ")} · physical checks {run.checksPassed ? "passed" : "FAILED"}. Simulation on the real demand shape with synthetic devices. Not a forecast or an engineering study.</div>
    </Card>
  );
}

function Slider({ t, label, value, min, max, step, unit, set, note }: { t: T; label: string; value: number; min: number; max: number; step: number; unit: string; set: (n: number) => void; note?: string }) {
  return <label style={{ display: "block", marginTop: 8 }}><div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}><span>{label}</span><b style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{value}{unit}</b></div>
    <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => set(+e.target.value)} style={{ width: "100%", accentColor: TEAL, margin: "4px 0 0" }} aria-label={label} />{note && <div style={{ fontSize: 11, color: t.mut }}>{note}</div>}</label>;
}
function Drawer({ t, params: p, setP, provider, setProvider, dcMw, setDcMw, close, defaults }: { t: T; params: DeviceParams; setP: (k: keyof DeviceParams, v: number) => void; provider: "stub" | "openai"; setProvider: (v: "stub" | "openai") => void; dcMw: number; setDcMw: (n: number) => void; close: () => void; defaults: DeviceParams }) {
  const sec = (title: string, sub: string) => <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 14, paddingTop: 10, borderTop: `1px solid ${t.ln}` }}><b style={{ fontFamily: FD, fontSize: 15 }}>{title}</b><span style={{ fontSize: 11, color: t.mut }}>{sub}</span></div>;
  return (
    <Card t={t} x={1096} y={24} w={320} h={744} pad={16}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><div style={{ fontFamily: FD, fontWeight: 700, fontSize: 17 }}>Edit how devices behave</div><button onClick={close} aria-label="Close editor" style={{ border: 0, background: t.sub, color: t.fg, width: 28, height: 28, borderRadius: 14, cursor: "pointer" }}>×</button></div>
      <div style={{ fontSize: 12, color: t.mut, marginTop: 2 }}>Applies on the next rebalance. Assumptions, not measurements.</div>
      {sec("Flexible fleet", "how much can move")}
      <Slider t={t} label="Fleet size (× calibrated)" value={p.fleetSizeX} min={1} max={5} step={0.5} unit="×" set={(v) => setP("fleetSizeX", v)} note="1× = up to 25% of load is controllable" />
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
      {sec("Data centre", "hypothetical")}
      <Slider t={t} label="Size" value={dcMw} min={5} max={60} step={5} unit=" MW" set={setDcMw} />
      <div style={{ fontSize: 12, color: t.mut, marginTop: 8 }}>Flexible compute share: next (not modeled yet).</div>
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
