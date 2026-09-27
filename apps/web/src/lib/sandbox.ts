import { API_URL } from "@/lib/api";
import type { Season } from "@/components/iso/scene";

export type LoadKind = "data_centre" | "housing" | "ev_depot";
export interface LoadSpec { kind: LoadKind; size: number; lot?: number | null }
export interface DeviceParams {
  fleetSizeX: number; batteryCount: number; evFleetCount: number; buildingCount: number; solarCount: number; batteryReservePct: number; ownersEnrolledPct: number; minPriceScale: number; evShiftablePct: number; evMaxDelayH: number;
  buildingOffsetC: number; buildingMaxHours: number; reboundPct: number; dcFlexPct: number; dcMaxDeferH: number;
}
export type Group = "battery" | "ev" | "building";
export interface ScriptStep { i: number; kind: "request" | "owner_offer" | "owner_decline" | "validation_fail" | "revision" | "accepted" | "clearing" | "dispatch" | "done"; text: string; ownerId?: string | null; ownerName?: string | null; group?: Group | null; mw?: number | null; price?: number | null; loadAfterMw?: number | null }
export interface SandboxRun {
  season: Season; hour: number; dateUsed: string; focusTimestamp: string; dcMw: number; loads: LoadSpec[]; baseMw: number; loadBeforeMw: number; loadAfterMw: number; capacityMw: number; overloadMw: number; hasOverload: boolean;
  absorbedMw: number; remainingMw: number; outcome: "holds" | "partly_holds" | "breaks" | "no_overload"; outcomeText: string; dispatchByGroup: Record<Group, number>; script: ScriptStep[];
  curve: { hours: number[]; before: number[]; after: number[] }; ownersTotal: number; ownersAccepted: number; eventEnergyBeforeMwh: number; eventEnergyAfterMwh: number;
  decisionSource: string; checksPassed: boolean; paramsApplied: string[]; paramsPending: string[]; runId?: string | null; provenance: Record<string, string>; note: string;
  ownerLog: OwnerLog[]; market: MarketLog | null; cached: boolean;
}
export interface OwnerLog { ownerId: string; name: string; group: Group; assets: number; status: string; offeredMw: number; pricePerMwh: number | null; dispatchedMwh: number; cost: number; explanation: string; source: "openai" | "stub" }
export interface MarketLog { requestedPeakMw: number; requestedMwh: number; offeredMwh: number; validatedMwh: number; dispatchedMwh: number; pricedOutMwh: number; clearingCost: number; incentivePerMwh: number; ownersOffered: number; ownersDeclined: number; ownersRejected: number; ownersPricedOut: number; ownersAccepted: number; agentCalls: number; durationMs: number }
export interface OwnerProgress { ownerId: string; ownerName: string; status: "offered" | "declined" | "fallback"; done: number; total: number; ms: number }
export interface DeviceTypeInfo { label: string; clusters: number; totalMw: number; totalMwh?: number | null; vehicles?: number | null; owners: number; does: string; limits: string }
export interface SandboxWorldInfo {
  zoneId: string; zoneName: string; capacityMw: number; provenance: Record<string, string>; devices: Record<string, number>; deviceDetails: Record<"battery" | "ev" | "building" | "solar", DeviceTypeInfo>; ownerCount: number;
  seasons: Record<Season, { referenceDay: string; hourlyBaselineMw: number[]; peakMw: number }>; defaults: DeviceParams; llmAvailable: boolean; note: string;
}
export async function fetchSandboxWorld(): Promise<SandboxWorldInfo> {
  const r = await fetch(`${API_URL}/api/sandbox/world`, { cache: "no-store" }); if (!r.ok) throw new Error(`world ${r.status}`); return r.json();
}
type RunBody = { season: Season; hour: number; loads: LoadSpec[]; provider: "stub" | "openai"; incentivePerMwh: number; deviceParams: DeviceParams };
/** Streams the run: `onOwner` fires as each owner's decision returns (real LLM calls take seconds), then resolves with the full result. */
export async function postSandboxRunStream(body: RunBody, onOwner: (p: OwnerProgress) => void): Promise<SandboxRun> {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 120000);
  try {
    const r = await fetch(`${API_URL}/api/sandbox/run-stream`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store", signal: ctl.signal });
    if (!r.ok || !r.body) throw new Error(`The simulation returned an error (${r.status}).`);
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = "", out: SandboxRun | null = null;
    const line = (l: string) => { if (!l.trim()) return; const m = JSON.parse(l); if (m.type === "owner") onOwner(m as OwnerProgress); else if (m.type === "result") out = m.data as SandboxRun; else if (m.type === "error") throw new Error(m.message); };
    for (;;) { const { done, value } = await reader.read(); if (done) break; buf += dec.decode(value, { stream: true }); const parts = buf.split("\n"); buf = parts.pop() ?? ""; parts.forEach(line); }
    line(buf);
    if (!out) throw new Error("The simulation ended without a result.");
    return out;
  } catch (e) {
    throw new Error(e instanceof DOMException && e.name === "AbortError" ? "The simulation took too long (over 2 minutes)." : e instanceof Error ? e.message : "Could not reach the simulation.");
  } finally { clearTimeout(timer); }
}
export async function fetchWorldFor(params: DeviceParams): Promise<SandboxWorldInfo> {
  const r = await fetch(`${API_URL}/api/sandbox/world`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(params), cache: "no-store" });
  if (!r.ok) throw new Error(`world ${r.status}`); return r.json();
}

export type CellState = "within" | "absorbed" | "over";
export interface SeasonCell {
  season: Season; dateUsed: string; peakHour: number; outcome: SandboxRun["outcome"]; outcomeText: string; peakLoadMw: number; peakLoadAfterMw: number; overloadMw: number; absorbedMw: number;
  remainingMw: number; hoursOverBefore: number; hoursOverAfter: number; hourStates: CellState[]; periods: Record<"morning" | "afternoon" | "evening", CellState>; decisionSource: string; ownersAccepted: number; ownersTotal: number;
}
export interface Matrix { capacityMw: number; loads: LoadSpec[]; cells: SeasonCell[]; note: string }
export async function postMatrix(body: { loads: LoadSpec[]; provider: "stub" | "openai"; incentivePerMwh: number; deviceParams: DeviceParams }): Promise<Matrix> {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 120000);
  try {
    const r = await fetch(`${API_URL}/api/sandbox/matrix`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store", signal: ctl.signal });
    if (!r.ok) throw new Error(`The season test returned an error (${r.status}).`);
    return await r.json();
  } catch (e) {
    throw new Error(e instanceof DOMException && e.name === "AbortError" ? "The season test took too long." : e instanceof Error ? e.message : "Could not reach the simulation.");
  } finally { clearTimeout(timer); }
}
