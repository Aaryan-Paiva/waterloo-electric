import { API_URL } from "@/lib/api";
import type { Season } from "@/components/iso/scene";

export interface DeviceParams {
  fleetSizeX: number; batteryReservePct: number; ownersEnrolledPct: number; minPriceScale: number; evShiftablePct: number; evMaxDelayH: number;
  buildingOffsetC: number; buildingMaxHours: number; reboundPct: number; dcFlexPct: number; dcMaxDeferH: number;
}
export type Group = "battery" | "ev" | "building";
export interface ScriptStep { i: number; kind: "request" | "owner_offer" | "owner_decline" | "validation_fail" | "revision" | "accepted" | "clearing" | "dispatch" | "done"; text: string; ownerId?: string | null; ownerName?: string | null; group?: Group | null; mw?: number | null; price?: number | null; loadAfterMw?: number | null }
export interface SandboxRun {
  season: Season; hour: number; dateUsed: string; focusTimestamp: string; dcMw: number; baseMw: number; loadBeforeMw: number; loadAfterMw: number; capacityMw: number; overloadMw: number; hasOverload: boolean;
  absorbedMw: number; remainingMw: number; outcome: "holds" | "partly_holds" | "breaks" | "no_overload"; outcomeText: string; dispatchByGroup: Record<Group, number>; script: ScriptStep[];
  curve: { hours: number[]; before: number[]; after: number[] }; ownersTotal: number; ownersAccepted: number; eventEnergyBeforeMwh: number; eventEnergyAfterMwh: number;
  decisionSource: string; checksPassed: boolean; paramsApplied: string[]; paramsPending: string[]; runId?: string | null; provenance: Record<string, string>; note: string;
}
export interface DeviceTypeInfo { label: string; clusters: number; totalMw: number; totalMwh?: number | null; vehicles?: number | null; owners: number; does: string; limits: string }
export interface SandboxWorldInfo {
  zoneId: string; zoneName: string; capacityMw: number; provenance: Record<string, string>; devices: Record<string, number>; deviceDetails: Record<"battery" | "ev" | "building" | "solar", DeviceTypeInfo>; ownerCount: number;
  seasons: Record<Season, { referenceDay: string; hourlyBaselineMw: number[]; peakMw: number }>; defaults: DeviceParams; note: string;
}
export async function fetchSandboxWorld(): Promise<SandboxWorldInfo> {
  const r = await fetch(`${API_URL}/api/sandbox/world`, { cache: "no-store" }); if (!r.ok) throw new Error(`world ${r.status}`); return r.json();
}
export async function postSandboxRun(body: { season: Season; hour: number; dcMw: number; provider: "stub" | "openai"; incentivePerMwh: number; deviceParams: DeviceParams }): Promise<SandboxRun> {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 30000);
  try {
    const r = await fetch(`${API_URL}/api/sandbox/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store", signal: ctl.signal });
    if (!r.ok) throw new Error(`The simulation returned an error (${r.status}).`);
    return await r.json();
  } catch (e) {
    throw new Error(e instanceof DOMException && e.name === "AbortError" ? "The simulation took too long (over 30 s)." : e instanceof Error ? e.message : "Could not reach the simulation.");
  } finally { clearTimeout(timer); }
}
