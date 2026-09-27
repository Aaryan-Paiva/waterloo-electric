"use client";
import { useEffect, useMemo, useState } from "react";
import { Result } from "@/components/coordination/CoordinationPanel";
import { ProvenanceBadge } from "@/components/world/ProvenanceBadges";
import { ownerLiveStatus, traceLine } from "@/lib/agentic";
import { formatEst } from "@/lib/pressure";
import type { AgenticConfig, AgenticRun, EventWindow, OfferRecord, OwnerAgent, OwnerRecord } from "@/types/api";

const TONE: Record<string, string> = { muted: "var(--muted)", ok: "var(--ok)", warn: "var(--warn)", bad: "var(--bad)", accent: "var(--accent)" };
const PRESETS = [40, 80, 120];
const hm = (iso: string) => formatEst(iso, { hour: "2-digit", minute: "2-digit", hour12: false }).replace(" EST", "");
const TYPE_ICON: Record<string, string> = { battery_operator: "▮", ev_aggregator: "⚡", building_portfolio: "▦" };

interface Props {
  config: AgenticConfig | null;
  owners: OwnerAgent[];
  run: AgenticRun | null;
  stale: boolean;
  busy: boolean;
  error: string | null;
  activeWindow: EventWindow | null;
  hasProject: boolean;
  cursorTs: string;
  peakDeficitMw: number | null;
  onRun: (incentive: number, provider: "stub" | "openai") => void;
  onReplay: () => void;
  onClear: () => void;
}

export function AgenticPanel({ config, owners, run, stale, busy, error, activeWindow, hasProject, cursorTs, peakDeficitMw, onRun, onReplay, onClear }: Props) {
  const [incentive, setIncentive] = useState(80);
  const [custom, setCustom] = useState("");
  const [provider, setProvider] = useState<"stub" | "openai">("stub");
  const openaiOk = !!config?.openaiAvailable;
  const value = custom !== "" ? Number(custom) : incentive;
  const valid = Number.isFinite(value) && value > 0 && value <= 1000;
  return (
    <section className="panel p-4" aria-label="Agentic DER coordination">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Agentic coordination <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· owner agents → validation → OR-Tools</span></h2>
        <div className="flex gap-1"><ProvenanceBadge type="modeled" /><ProvenanceBadge type="derived" /></div>
      </div>
      <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
        CapacityOS broadcasts a flexibility request. {owners.length || "~18"} modeled owner/operator agents decide whether, how much and at what price to offer the physical DERs they control.
        Every offer is physically validated before the optimizer sees it; the LLM never touches physics.
      </p>

      <div className="rounded-lg p-3 mt-3" style={{ border: "1px solid var(--line)", background: "var(--panel-2)" }}>
        <div className="text-[11px] font-semibold tracking-wide" style={{ color: "var(--muted)" }}>CAPACITYOS FLEXIBILITY REQUEST</div>
        {activeWindow ? (
          <dl className="grid grid-cols-3 gap-2 text-sm mt-1">
            <div><dt className="text-[11px]" style={{ color: "var(--muted)" }}>Need</dt><dd className="tabular-nums font-semibold">{(peakDeficitMw ?? activeWindow.peakDeficitMw).toFixed(1)} MW</dd></div>
            <div><dt className="text-[11px]" style={{ color: "var(--muted)" }}>Window</dt><dd className="tabular-nums">{hm(activeWindow.start)}–{hm(activeWindow.end)} <span style={{ color: "var(--muted)" }}>({activeWindow.hours} h)</span></dd></div>
            <div><dt className="text-[11px]" style={{ color: "var(--muted)" }}>Incentive</dt><dd className="tabular-nums font-semibold">${valid ? value : "—"}/MWh</dd></div>
          </dl>
        ) : <div className="text-xs mt-1" style={{ color: "var(--muted)" }}>{hasProject ? "Move the cursor into a capacity event, or pick one from the list." : "Add a project to create capacity events."}</div>}
        <div className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Flexibility compensation ($/MWh; a price ceiling — offers above it are counteroffers and are not cleared)</div>
        <div className="flex flex-wrap items-center gap-1.5 mt-1" role="group" aria-label="Flexibility compensation">
          {PRESETS.map((p) => <button key={p} className="btn" aria-pressed={custom === "" && incentive === p} onClick={() => { setCustom(""); setIncentive(p); }}>${p}</button>)}
          <input aria-label="Custom compensation ($/MWh)" inputMode="numeric" placeholder="custom" className="w-20 rounded-md px-2 py-1 text-xs" style={{ background: "var(--panel)", border: "1px solid var(--line)", color: "var(--text)" }}
            value={custom} onChange={(e) => setCustom(e.target.value.replace(/[^0-9.]/g, ""))} />
        </div>
        <div className="flex items-center gap-2 mt-2 text-xs">
          <label htmlFor="agent-provider" style={{ color: "var(--muted)" }}>Owner agents</label>
          <select id="agent-provider" className="rounded-md px-2 py-1" style={{ background: "var(--panel)", border: "1px solid var(--line)", color: "var(--text)" }} value={provider} onChange={(e) => setProvider(e.target.value as "stub" | "openai")}>
            <option value="stub">Deterministic stub (no API)</option>
            <option value="openai" disabled={!openaiOk}>OpenAI{openaiOk ? ` · ${config?.model}` : " (not configured)"}</option>
          </select>
        </div>
      </div>

      <button className="btn mt-3 w-full" style={{ borderColor: "var(--accent)" }} disabled={!activeWindow || busy || !hasProject || !valid} onClick={() => onRun(value, provider)}>
        {busy ? "Owner agents deciding…" : "📡 Broadcast flexibility request"}
      </button>
      {error && <p className="text-xs mt-2" style={{ color: "var(--bad)" }}>{error}</p>}
      {run && <RunView key={run.id} run={run} stale={stale} cursorTs={cursorTs} onReplay={onReplay} onClear={onClear} busy={busy} />}
    </section>
  );
}

function RunView({ run, stale, cursorTs, onReplay, onClear, busy }: { run: AgenticRun; stale: boolean; cursorTs: string; onReplay: () => void; onClear: () => void; busy: boolean }) {
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [n, setN] = useState(reduced ? run.trace.length : 0);
  const [sel, setSel] = useState<string | null>(null);
  useEffect(() => {
    if (n >= run.trace.length) return;
    const id = setInterval(() => setN((k) => Math.min(run.trace.length, k + 1)), 45);
    return () => clearInterval(id);
  }, [n, run.trace.length]);
  const done = n >= run.trace.length;
  const live = useMemo(() => ownerLiveStatus(run.trace, n), [run.trace, n]);
  const rec = useMemo(() => new Map(run.records.map((r) => [r.ownerId, r])), [run.records]);
  const m = run.market;
  const recent = run.trace.slice(Math.max(0, n - 6), n).reverse();
  return (
    <div className="mt-3">
      {stale && <div className="text-xs rounded p-2 mb-2" style={{ border: "1px solid var(--warn)", color: "var(--warn)" }}>▲ Scenario changed since this run: broadcast again.</div>}
      {run.provider.fallbackReason && <div className="text-xs rounded p-2 mb-2" style={{ border: "1px solid var(--warn)", color: "var(--warn)" }}>Requested provider “{run.provider.requested}” unavailable ({run.provider.fallbackReason}); ran the deterministic stub.</div>}

      <div className="mb-2 text-xs rounded-md p-2" style={{ border: `1px solid ${run.decisionSource === "llm_openai" ? "var(--accent)" : "var(--line)"}`, background: "var(--panel-2)" }}>
        {run.decisionSource === "llm_openai"
          ? <><b style={{ color: "var(--accent)" }}>Real LLM owner agents</b> · {run.llmOwnerCount}/{run.owners.length} decisions from {run.provider.model} (Modeled synthetic behavior; validated before use)</>
          : run.decisionSource === "mixed_llm_and_stub" ? <><b style={{ color: "var(--warn)" }}>Partial LLM</b> · {run.llmOwnerCount}/{run.owners.length} owners from {run.provider.model}, the rest fell back to the stub</>
          : run.decisionSource === "replay" ? <><b>Replay</b> of recorded owner actions · no model called</>
          : <><b>Deterministic stub policy</b> · not an LLM · same policy the Historical mode applies to every event</>}
      </div>
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold">Owner/operator agents · {run.provider.used}{run.provider.model ? ` (${run.provider.model})` : ""}</h3>
        <div className="flex gap-1">
          {!done && <button className="btn" onClick={() => setN(run.trace.length)}>Skip ▸▸</button>}
          {done && <button className="btn" onClick={() => setN(0)} aria-label="Replay the agent feed">↻ Feed</button>}
        </div>
      </div>
      <ul className="mt-1 grid gap-1" aria-label="Owner agents" aria-live="polite">
        {run.owners.map((o) => {
          const l = live[o.id];
          const r = rec.get(o.id);
          return (
            <li key={o.id}>
              <button className="w-full text-left rounded-md px-2 py-1 flex items-center gap-2 text-xs" onClick={() => setSel(sel === o.id ? null : o.id)} aria-expanded={sel === o.id}
                style={{ border: `1px solid ${sel === o.id ? "var(--accent)" : "var(--line)"}`, background: "var(--panel-2)" }}>
                <span aria-hidden>{TYPE_ICON[o.ownerType]}</span>
                <span className="truncate flex-1">{o.name}</span>
                <span className="tabular-nums shrink-0" style={{ color: TONE[l?.tone ?? "muted"] }}>{l ? l.label : "waiting"}{l?.detail ? ` · ${l.detail}` : ""}</span>
                {done && r && r.dispatchedMwh > 0.001 && <span className="tabular-nums shrink-0" style={{ color: "var(--ok)" }}>{r.dispatchedMwh.toFixed(1)} MWh</span>}
              </button>
              {sel === o.id && <OwnerInspector owner={o} rec={r} run={run} />}
            </li>
          );
        })}
      </ul>

      <div className="mt-2 rounded-md p-2 text-[11px]" style={{ background: "var(--panel-2)", border: "1px solid var(--line)", minHeight: 40 }} aria-label="Live event feed">
        {recent.map((e) => <div key={e.seq} style={{ color: e.type.includes("failed") || e.type.includes("rejected") ? "var(--warn)" : "var(--muted)" }}>{traceLine(e, run.owners)}</div>)}
        {!recent.length && <div style={{ color: "var(--muted)" }}>…</div>}
      </div>

      {done && (
        <>
          <h3 className="text-xs font-semibold mt-3 mb-1">Market summary <span className="font-normal" style={{ color: "var(--muted)" }}>· peak MW · modeled $</span></h3>
          <div className="grid grid-cols-5 gap-1 text-center" role="table" aria-label="Market summary">
            {[["Requested", m.requestedPeakMw, "var(--hypo)"], ["Offered", m.offeredPeakMw, "var(--accent)"], ["Validated", m.validatedPeakMw, "var(--accent)"], ["Dispatched", m.dispatchedPeakMw, "var(--ok)"], ["Remaining", m.remainingWorstDeficitMw, m.remainingWorstDeficitMw > 0.05 ? "var(--bad)" : "var(--ok)"]].map(([k, v, c]) => (
              <div key={String(k)} className="rounded-md py-1.5" style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}>
                <div className="text-[10px]" style={{ color: "var(--muted)" }}>{String(k).toUpperCase()}</div>
                <div className="tabular-nums font-semibold text-sm" style={{ color: String(c) }}>{Number(v).toFixed(1)}</div>
                <div className="text-[10px]" style={{ color: "var(--muted)" }}>MW</div>
              </div>
            ))}
          </div>
          <div className="text-[11px] mt-1 tabular-nums" style={{ color: "var(--muted)" }}>
            Energy: requested {m.requestedMwh.toFixed(1)} · offered {m.offeredMwh.toFixed(1)} · validated {m.validatedMwh.toFixed(1)} · priced out {m.pricedOutMwh.toFixed(1)} · dispatched {m.dispatchedMwh.toFixed(1)} MWh · modeled clearing cost ${m.clearingCost.toFixed(0)} @ ceiling ${m.incentivePricePerMwh}/MWh
            <br />Owners: {m.ownersAccepted} cleared · {m.ownersPricedOut} priced out · {m.ownersRejected} physically rejected · {m.ownersDeclined} declined · {run.diagnostics.agentCalls} agent calls · {(run.diagnostics.durationMs / 1000).toFixed(1)} s{run.diagnostics.fallbacks ? ` · ${run.diagnostics.fallbacks} fallback(s)` : ""}
          </div>
          <Result r={run.coordination} stale={stale} cursorTs={cursorTs} onClear={onClear} />
          <div className="flex gap-2 mt-2">
            <button className="btn" onClick={onReplay} disabled={busy} title="Re-run validation and clearing from the recorded owner actions (no model)">↻ Replay from record</button>
            <button className="btn" onClick={onClear}>Clear</button>
            <span className="text-[11px] self-center" style={{ color: "var(--muted)" }}>run {run.id}{run.replayOf ? ` (replay of ${run.replayOf})` : ""} · hash {run.resultHash}</span>
          </div>
          <p className="text-[11px] mt-2" style={{ color: "var(--muted)" }}>{run.note}</p>
        </>
      )}
    </div>
  );
}

function OwnerInspector({ owner: o, rec, run }: { owner: OwnerAgent; rec?: OwnerRecord; run: AgenticRun }) {
  const kv = (k: string, v: string | number) => <div><dt className="text-[10px]" style={{ color: "var(--muted)" }}>{k}</dt><dd className="tabular-nums">{v}</dd></div>;
  const assets = new Map(run.coordination.agents.map((a) => [a.agentId, a]));
  return (
    <div className="rounded-md p-2 mt-1 text-xs" style={{ border: "1px solid var(--line)", background: "var(--panel)" }}>
      <div className="flex items-center gap-2"><b>{o.name}</b><ProvenanceBadge type="modeled" /></div>
      <dl className="grid grid-cols-3 gap-x-3 gap-y-1 mt-2">
        {kv("Min compensation", `$${o.economic.minCompensationPerMwh}/MWh`)}{kv("Target margin", `${Math.round(o.economic.targetMargin * 100)}%`)}{kv("Price sensitivity", o.economic.priceSensitivity.toFixed(2))}
        {o.ownerType === "battery_operator" && <>{kv("Reserve preference", o.operational.reservePreference.toFixed(2))}{kv("Degradation sens.", o.operational.degradationSensitivity.toFixed(2))}</>}
        {o.ownerType === "building_portfolio" && kv("Comfort priority", o.operational.comfortPriority.toFixed(2))}
        {o.ownerType === "ev_aggregator" && <>{kv("Driver satisfaction", o.operational.driverSatisfactionPriority.toFixed(2))}{kv("Deadline strictness", o.operational.deadlineStrictness.toFixed(2))}</>}
        {kv("Max event hours", o.operational.maxEventHours)}{kv("Max events / mo", o.operational.maxEventsPerMonth)}
        {kv("Risk tolerance", o.behavioral.riskTolerance.toFixed(2))}{kv("Participation tendency", o.behavioral.participationTendency.toFixed(2))}
      </dl>
      <div className="mt-2" style={{ color: "var(--muted)" }}>Controls {o.controlledAssetIds.length} physical DER model(s):</div>
      <div className="flex flex-wrap gap-1 mt-1">
        {o.controlledAssetIds.map((id) => { const a = assets.get(id); return <span key={id} className="chip" title={a?.name} style={{ borderColor: a?.included ? "var(--ok)" : "var(--line)" }}>{id.replace(/_/g, " ")}{a?.included ? " ✓" : ""}</span>; })}
      </div>
      {rec && (
        <div className="mt-2">
          <div><b>Decision</b> · {rec.status.replace(/_/g, " ")}{rec.declineCode ? ` (${rec.declineCode.replace(/_/g, " ")})` : ""} · {rec.providerUsed}{rec.fallbackReason ? " · fallback" : ""}</div>
          {rec.decisionExplanation && <div style={{ color: "var(--muted)" }}>“{rec.decisionExplanation}”</div>}
          {rec.offers.map((of) => <OfferView key={of.id} of={of} hours={run.request.hours} />)}
          {rec.dispatchedMwh > 0 && <div className="mt-1">Dispatched {rec.dispatchedMwh.toFixed(2)} MWh · modeled cost ${rec.cost.toFixed(0)}</div>}
        </div>
      )}
    </div>
  );
}

const hrs = (bs: { startHour: number; endHour: number }[]) => bs.reduce((a, b) => a + b.endHour - b.startHour, 0);

function OfferView({ of, hours }: { of: OfferRecord; hours: string[] }) {
  const bad = of.validation.status === "invalid";
  return (
    <div className="mt-1 rounded p-1.5" style={{ border: `1px solid ${bad ? "var(--warn)" : "var(--line)"}` }}>
      <div>{of.revision === 0 ? "Offer" : "Revised offer"} · ${of.body.pricePerMwh.toFixed(0)}/MWh · {of.peakMw.toFixed(2)} MW peak · {of.offeredMwh.toFixed(2)} MWh · <b style={{ color: bad ? "var(--warn)" : of.status === "accepted" ? "var(--ok)" : "var(--muted)" }}>{bad ? "physical validation failed" : of.status.replace(/_/g, " ")}</b>{of.counteroffer ? " · counteroffer" : ""}</div>
      {of.validation.lines.filter((l) => l.status === "invalid").map((l) => (
        <div key={l.assetId} style={{ color: "var(--muted)" }}>
          {l.assetId}: {String(l.violation).replace(/_/g, " ")} — requested {Math.max(0, ...l.requested.map((b) => b.mw)).toFixed(2)} MW × {hrs(l.requested)} h, feasible {Math.max(0, ...l.feasibleEnvelope.map((b) => b.mw)).toFixed(2)} MW × {hrs(l.feasibleEnvelope)} h
        </div>
      ))}
      {of.body.assetOffers.slice(0, 4).map((a) => (
        <div key={a.assetId} className="tabular-nums" style={{ color: "var(--muted)" }}>{a.assetId}: {a.blocks.map((b) => `${hm(hours[b.startHour])} +${b.endHour - b.startHour} h @ ${b.mw.toFixed(2)} MW`).join(", ")}</div>
      ))}
    </div>
  );
}
