"use client";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { HistoricalPanel } from "@/components/historical/HistoricalPanel";
import { AgenticPanel } from "@/components/agentic/AgenticPanel";
import { CoordinationPanel } from "@/components/coordination/CoordinationPanel";
import { ModeSelector, type CoordMode } from "@/components/coordination/ModeSelector";
import { AnalysisPanel } from "@/components/feasibility/AnalysisPanel";
import { AgentsPanel, TYPE_LABEL } from "@/components/agents/AgentsPanel";
import { ProjectPanel } from "@/components/projects/ProjectPanel";
import { ProvenanceBadge, ProvenanceRow } from "@/components/world/ProvenanceBadges";
import { WorldCanvas } from "@/components/world/WorldCanvas";
import { PlaybackControls } from "@/components/simulation/PlaybackControls";
import { DetailTimeline, OverviewTimeline, dayLabel, hourLabel, type DayRow, type Row } from "@/components/simulation/LoadTimeline";
import { usePlayback } from "@/hooks/usePlayback";
import { useAgents } from "@/hooks/useAgents";
import { useAgentic } from "@/hooks/useAgentic";
import { useHistorical } from "@/hooks/useHistorical";
import { useCoordination } from "@/hooks/useCoordination";
import { useScenario } from "@/hooks/useScenario";
import { API_URL, fetchScenarioLoad, fetchWorld } from "@/lib/api";
import { nextWindow } from "@/lib/events";
import { PRESSURE_COLOR, PRESSURE_GLYPH, PRESSURE_LABEL, dayProfile, formatEst, pressureState } from "@/lib/pressure";
import type { ScenarioLoadPoint, WorldState } from "@/types/api";

const yearOf = (iso: string) => Number(iso.slice(0, 4));
type Landing = { kind: "peak" } | { kind: "ts"; ts: string } | null;

export default function WorldPage() {
  const { worldId } = useParams<{ worldId: string }>();
  const sc = useScenario(worldId);
  const [world, setWorld] = useState<WorldState | null>(null);
  const [daily, setDaily] = useState<ScenarioLoadPoint[]>([]);
  const [hourly, setHourly] = useState<ScenarioLoadPoint[]>([]);
  const [year, setYear] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const landing = useRef<Landing>({ kind: "peak" });
  const pb = usePlayback(hourly.length);
  const [windowHours, setWindowHours] = useState(1);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [pickedWindow, setPickedWindow] = useState<string | null>(null);
  const [mode, setMode] = useState<CoordMode>("manual");

  useEffect(() => {
    let live = true;
    fetchWorld(worldId).then((w) => { if (live) { setWorld(w); setYear(yearOf(w.loadSummary.peakTimestamp)); } }).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [worldId]);

  const scenarioId = sc.scenario?.id;
  useEffect(() => {
    if (!scenarioId) return;
    let live = true;
    fetchScenarioLoad(scenarioId, { resolution: "daily" }).then((r) => live && setDaily(r.points)).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [scenarioId, sc.version]);

  useEffect(() => {
    if (!world || year == null || !scenarioId) return;
    let live = true;
    const opts = world.mode === "fixture" ? {} : { start: `${year}-01-01T00:00:00-05:00`, end: `${year + 1}-01-01T00:00:00-05:00` };
    fetchScenarioLoad(scenarioId, { resolution: "hourly", ...opts }).then((r) => live && setHourly(r.points)).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [world, scenarioId, sc.version, year]);

  // Land on the peak (or a picked timestamp) only when the year/world changes; scenario edits keep the cursor where it is.
  useEffect(() => {
    const l = landing.current;
    if (!hourly.length || !l) return;
    pb.setPlaying(false);
    if (l.kind === "peak") pb.seek(peakIndex(hourly));
    else { const i = hourly.findIndex((p) => p.timestamp === l.ts); pb.seek(i >= 0 ? i : Math.max(0, hourly.findIndex((p) => p.timestamp.slice(0, 10) === l.ts.slice(0, 10)) + 12)); }
    landing.current = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hourly]);

  const years = useMemo(() => {
    if (!world) return [];
    const a = yearOf(world.loadSummary.start), b = yearOf(world.loadSummary.end);
    return Array.from({ length: b - a + 1 }, (_, i) => a + i);
  }, [world]);

  const capacity = world?.zone.capacityMw ?? 0;
  const cursorTs = hourly[pb.index]?.timestamp;
  const ag = useAgents(worldId, sc.scenario?.id, cursorTs, windowHours, selectedAgent);
  const co = useCoordination(sc.scenario?.id);
  const coKey = `${sc.version}|${JSON.stringify(ag.population?.participationRates ?? {})}`;
  const coStale = !!co.result && co.key !== coKey;
  const agent = useAgentic(sc.scenario?.id, mode === "agentic");
  const agStale = !!agent.run && agent.key !== `${sc.version}`;
  const hist = useHistorical(sc.scenario?.id);
  const histStale = Object.keys(hist.results).length > 0 && hist.key !== `${sc.version}`;
  const hr = mode === "historical" && !histStale && hist.selected != null ? (hist.results[hist.selected] ?? null) : null;
  const histMap = useMemo(() => new Map((hr?.hourly ?? []).map((h) => [h.timestamp, h])), [hr]);
  const histHour = cursorTs ? histMap.get(cursorTs) : undefined;
  // The world always animates the DETERMINISTIC dispatch of whichever mode is active (agentic mode: the OR-Tools clearing of validated offers).
  const coLive = mode === "agentic" ? (agent.run && !agStale ? agent.run.coordination : null) : (co.result && !coStale ? co.result : null);
  const coHour = coLive && cursorTs ? coLive.hourly.find((h) => h.timestamp === cursorTs) : undefined;
  const activeWindow = cursorTs && sc.analysis ? (sc.analysis.windows.find((w) => w.start <= cursorTs && cursorTs < w.end) ?? sc.analysis.windows.find((w) => w.id === pickedWindow) ?? null) : null;
  const histDispatch = (type: string) => (!histHour ? 0 : type === "battery" ? histHour.batteryMw : type === "ev_fleet" ? histHour.evMw : histHour.buildingMw);
  const dispatchAt = (type: string) => (coLive && cursorTs ? coLive.agents.filter((a) => a.type === type && a.included) : []).map((a) => { const i = coLive!.hourly.findIndex((h) => h.timestamp === cursorTs); return i >= 0 ? a.dispatchMw[i] : 0; });
  const agentLayer = ag.population && ag.potential ? (["battery", "ev_fleet", "building", "solar"] as const).map((t) => ({
    type: t, label: TYPE_LABEL[t], count: ag.population!.byType[t].count, participating: t === "solar" ? null : (mode === "agentic" && coLive ? coLive.agents.filter((a) => a.type === t && a.included).length : ag.population!.byType[t].participating),
    potentialMw: ag.potential!.byType[t].potentialMw, note: t === "solar" ? "in baseline · 0 relief" : undefined,
    dispatchMw: t === "solar" ? 0 : hr ? Math.max(0, histDispatch(t)) : dispatchAt(t).reduce((x, y) => x + Math.max(0, y), 0),
    dispatching: t === "solar" || hr ? undefined : dispatchAt(t).filter((y) => y > 0.005).length })) : undefined;
  const hasProject = (sc.scenario?.projects.length ?? 0) > 0;
  const point = hourly[pb.index];
  const dispatchDay = useMemo(() => {
    if (!coLive && !hr) return undefined;
    const start = Math.floor(pb.index / 24) * 24;
    const m = coLive ? new Map(coLive.hourly.map((h) => [h.timestamp, h.totalReductionMw])) : new Map(hr!.hourly.map((h) => [h.timestamp, h.batteryMw + h.evMw + h.buildingMw]));
    return hourly.slice(start, start + 24).map((p) => Math.max(0, m.get(p.timestamp) ?? 0));
  }, [coLive, hr, hourly, pb.index]);
  const baseDay = useMemo(() => dayProfile(hourly.map((p) => p.baselineLoadMw), pb.index), [hourly, pb.index]);
  const projDay = useMemo(() => dayProfile(hourly.map((p) => p.projectLoadMw), pb.index), [hourly, pb.index]);
  const detail = useMemo<Row[]>(() => {
    const a = Math.max(0, pb.index - 84), b = Math.min(hourly.length, pb.index + 84);
    const opt = new Map(coLive ? coLive.hourly.map((h) => [h.timestamp, h.optimizedNetMw]) : (hr?.hourly ?? []).map((h) => [h.timestamp, h.optimizedNetMw]));
    return hourly.slice(a, b).map((p) => ({ label: hourLabel(p.timestamp), baseline: p.baselineLoadMw, net: p.netLoadMw, opt: opt.get(p.timestamp) }));
  }, [hourly, pb.index, coLive, hr]);
  const overview = useMemo<DayRow[]>(() => daily.map((p) => ({ ts: p.timestamp, label: dayLabel(p.timestamp), baseline: p.baselineLoadMw, net: p.netLoadMw, over: p.constrainedHours ?? 0 })), [daily]);

  const jumpTo = (ts: string) => {
    pb.setPlaying(false);
    const y = yearOf(ts);
    if (y !== year && world?.mode !== "fixture") { landing.current = { kind: "ts", ts }; setYear(y); return; }
    const i = hourly.findIndex((p) => p.timestamp === ts);
    pb.seek(i >= 0 ? i : Math.max(0, hourly.findIndex((p) => p.timestamp.slice(0, 10) === ts.slice(0, 10)) + 12));
  };
  const stepEvent = (dir: 1 | -1) => { const w = point && sc.analysis ? nextWindow(sc.analysis.windows, point.timestamp, dir) : null; if (w) jumpTo(w.peakTimestamp); };

  const err = error ?? sc.error;
  if (err) return <Shell><div className="panel p-6"><b>Can&apos;t reach the CapacityOS API.</b><p className="text-sm mt-2" style={{ color: "var(--muted)" }}>Tried {API_URL}. Start it with: <code>cd apps/api &amp;&amp; .venv/bin/uvicorn src.main:app --port 8000</code></p><p className="text-xs mt-2" style={{ color: "var(--bad)" }}>{err}</p></div></Shell>;
  if (!world || !point || !sc.scenario || !sc.analysis) return <Shell><div className="panel p-6" role="status">Loading the world…</div></Shell>;

  const state = pressureState(point.netLoadMw, capacity);
  const dc = sc.scenario.projects[0];
  return (
    <Shell>
      <header className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl font-semibold">CapacityOS <span style={{ color: "var(--muted)" }}>· {world.name}</span></h1>
          <p className="text-xs" style={{ color: "var(--muted)" }}>{world.label} · scenario “{sc.scenario.name}”</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs" aria-label="Data provenance summary">
          {world.mode === "fixture" && <span className="chip" style={{ borderColor: "var(--warn)", color: "var(--warn)" }}>▲ Demo mode: 30-day fixture</span>}
          <span>Demand</span><ProvenanceBadge type={world.provenance.historicalDemand.type} />
          <span>DERs</span><ProvenanceBadge type={world.provenance.derPopulation.type} />
          <span>Capacity</span><ProvenanceBadge type={world.provenance.zoneCapacity.type} />
          <span>Project</span><ProvenanceBadge type={world.provenance.newProject.type} />
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="flex flex-col gap-4">
          <WorldCanvas name={world.name} capacityMw={capacity} netMw={point.netLoadMw} baselineMw={point.baselineLoadMw} projectMw={point.projectLoadMw}
            baselineDay={baseDay} projectDay={projDay} hour={pb.index % 24} projectLabel={dc ? dc.name : null} agentLayer={agentLayer}
            optimizedNetMw={coHour ? coHour.optimizedNetMw : histHour ? histHour.optimizedNetMw : null} dispatchDay={dispatchDay} />
          <PlaybackControls playing={pb.playing} setPlaying={pb.setPlaying} speed={pb.speed} setSpeed={pb.setSpeed}
            index={pb.index} length={hourly.length} seek={pb.seek} years={years} year={year ?? years[0]}
            setYear={(y) => { pb.setPlaying(false); landing.current = { kind: "peak" }; setYear(y); }}
            onJumpPeak={() => pb.seek(peakIndex(hourly))} onJumpStart={() => pb.seek(0)}
            onPrevEvent={hasProject && sc.analysis.windowCount ? () => stepEvent(-1) : undefined}
            onNextEvent={hasProject && sc.analysis.windowCount ? () => stepEvent(1) : undefined} time={formatEst(point.timestamp)} />
          <DetailTimeline rows={detail} capacityMw={capacity} cursorLabel={hourLabel(point.timestamp)} hasProject={hasProject} />
          <OverviewTimeline rows={overview} capacityMw={capacity} cursorLabel={dayLabel(point.timestamp)} hasProject={hasProject} onPick={jumpTo} />
        </div>
        <aside className="flex flex-col gap-4">
          <ProjectPanel scenario={sc.scenario} busy={sc.busy} onAdd={(m) => void sc.addDc(m)} onSetMw={sc.setMw} onRemove={(id) => void sc.removeDc(id)} onReset={() => void sc.reset()} onGolden={() => void sc.goldenDemo()} />
          <section className="panel p-4" aria-label="Zone status">
            <div className="text-xs" style={{ color: "var(--muted)" }}>{formatEst(point.timestamp)}</div>
            <div className="text-3xl font-bold tabular-nums mt-1">{point.netLoadMw.toFixed(1)} <span className="text-base font-normal" style={{ color: "var(--muted)" }}>MW net</span></div>
            <div className="text-sm mt-1" style={{ color: PRESSURE_COLOR[state] }}>{PRESSURE_GLYPH[state]} {PRESSURE_LABEL[state]}{point.deficitMw > 0 ? ` · deficit ${point.deficitMw.toFixed(1)} MW` : ""}</div>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-sm mt-3">
              <Stat k="Baseline (derived)" v={`${point.baselineLoadMw.toFixed(1)} MW`} />
              <Stat k="Project (hypothetical)" v={`${point.projectLoadMw.toFixed(1)} MW`} />
              <Stat k="Modeled capacity" v={`${capacity} MW`} />
              <Stat k="Headroom now" v={`${(capacity - point.netLoadMw).toFixed(1)} MW`} />
            </dl>
          </section>
          <AnalysisPanel a={sc.analysis} hasProject={hasProject} onJump={(ts, wid) => { if (wid) setPickedWindow(wid); jumpTo(ts); }} />
          <ModeSelector mode={mode} setMode={setMode} />
          {mode === "historical" ? (
            <HistoricalPanel results={hist.results} selected={hist.selected} setSelected={hist.setSelected} busy={hist.busy} error={hist.error} stale={histStale} hasProject={hasProject}
              onRun={(inc) => void hist.run(inc, `${sc.version}`)} onClear={hist.clear} onJump={jumpTo} />
          ) : mode === "manual" ? (
            <CoordinationPanel result={co.result} stale={coStale} busy={co.busy} error={co.error} activeWindow={activeWindow} hasProject={hasProject} cursorTs={point.timestamp}
              onCoordinate={() => activeWindow && void co.run(activeWindow.id, coKey)} onClear={co.clear} />
          ) : (
            <AgenticPanel config={agent.config} owners={agent.owners} run={agent.run} stale={agStale} busy={agent.busy} error={agent.error} activeWindow={activeWindow} hasProject={hasProject}
              cursorTs={point.timestamp} peakDeficitMw={activeWindow?.peakDeficitMw ?? null}
              onRun={(inc, prov) => activeWindow && void agent.start(activeWindow.id, inc, prov, `${sc.version}`)} onReplay={() => void agent.replay()} onClear={agent.clear} />
          )}
          <AgentsPanel population={ag.population} potential={ag.potential} agents={ag.agents} detail={ag.detail} selectedId={selectedAgent} onSelect={setSelectedAgent}
            windowHours={windowHours} setWindowHours={setWindowHours} onRate={ag.setRate} timestamp={point.timestamp} />
          <section className="panel p-4" aria-label="Data provenance">
            <h2 className="text-sm font-semibold">Data provenance</h2>
            <ul>
              <ProvenanceRow label="Historical demand" p={world.provenance.historicalDemand} />
              <ProvenanceRow label="DER population" p={world.provenance.derPopulation} />
              <ProvenanceRow label="Zone capacity" p={world.provenance.zoneCapacity} />
              <ProvenanceRow label="New project" p={world.provenance.newProject} />
            </ul>
          </section>
        </aside>
      </div>
      <footer className="text-xs mt-6" style={{ color: "var(--muted)" }}>
        CapacityOS is a planning simulation and capacity-screening sandbox. It is not a utility-grade study or an interconnection approval. Historical replay is not a forecast.
      </footer>
    </Shell>
  );
}

function peakIndex(pts: ScenarioLoadPoint[]) {
  let b = 0;
  pts.forEach((p, i) => { if (p.netLoadMw > pts[b].netLoadMw) b = i; });
  return b;
}

function Stat({ k, v }: { k: string; v: string }) {
  return <div><dt className="text-xs" style={{ color: "var(--muted)" }}>{k}</dt><dd className="tabular-nums">{v}</dd></div>;
}

function Shell({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto w-full max-w-7xl p-4 md:p-6">{children}</main>;
}
