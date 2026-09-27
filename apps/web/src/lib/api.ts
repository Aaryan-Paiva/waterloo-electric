import type { HistoricalResult, AgenticConfig, AgenticRun, OwnerAgentsResponse, AgentDetail, CoordinationResult, AgentSummary, CapacityAnalysis, PopulationPotential, PopulationSummary, LoadResponse, Scenario, ScenarioLoadResponse, WorldState } from "@/types/api";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json() as Promise<T>;
}

export const fetchWorld = (id: string) => get<WorldState>(`/api/worlds/${id}`);

export function fetchLoad(id: string, opts: { resolution: "hourly" | "daily"; start?: string; end?: string }) {
  const q = new URLSearchParams({ resolution: opts.resolution });
  if (opts.start) q.set("start", opts.start);
  if (opts.end) q.set("end", opts.end);
  return get<LoadResponse>(`/api/zones/${id}/load?${q}`);
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store" });
  if (!r.ok) throw new Error(`${method} ${path} -> ${r.status}`);
  return r.json() as Promise<T>;
}

export const createScenario = (zoneId: string, name?: string) => send<Scenario>("POST", "/api/scenarios", { zoneId, name });
export const getScenario = (id: string) => get<Scenario>(`/api/scenarios/${id}`);
export const addDataCentre = (id: string, nominalLoadMw: number) => send<Scenario>("POST", `/api/scenarios/${id}/projects`, { type: "data_center", nominalLoadMw });
export const setProjectMw = (id: string, pid: string, nominalLoadMw: number) => send<Scenario>("PATCH", `/api/scenarios/${id}/projects/${pid}`, { nominalLoadMw });
export const removeProject = (id: string, pid: string) => send<Scenario>("DELETE", `/api/scenarios/${id}/projects/${pid}`);
export const fetchAnalysis = (id: string) => get<CapacityAnalysis>(`/api/scenarios/${id}/analysis`);

export function fetchScenarioLoad(id: string, opts: { resolution: "hourly" | "daily"; start?: string; end?: string }) {
  const q = new URLSearchParams({ resolution: opts.resolution });
  if (opts.start) q.set("start", opts.start);
  if (opts.end) q.set("end", opts.end);
  return get<ScenarioLoadResponse>(`/api/scenarios/${id}/load?${q}`);
}

const qs = (o: Record<string, string | number | boolean | undefined>) => {
  const q = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => v !== undefined && q.set(k, String(v)));
  return q.toString();
};
export const fetchPopulation = (world: string, scenarioId?: string) => get<PopulationSummary>(`/api/worlds/${world}/population?${qs({ scenarioId })}`);
export const fetchAgents = (world: string, scenarioId?: string) => get<AgentSummary[]>(`/api/worlds/${world}/agents?${qs({ scenarioId })}`);
export const fetchPotential = (world: string, timestamp: string, windowHours: number, scenarioId?: string) =>
  get<PopulationPotential>(`/api/worlds/${world}/population/potential?${qs({ timestamp, windowHours, scenarioId, includeAgents: true })}`);
export const fetchAgentDetail = (world: string, id: string, timestamp: string, windowHours: number, scenarioId?: string) =>
  get<AgentDetail>(`/api/worlds/${world}/agents/${id}?${qs({ timestamp, windowHours, scenarioId })}`);
export const patchAssumptions = (scenarioId: string, body: Partial<Record<"evParticipation" | "batteryParticipation" | "buildingParticipation", number>>) =>
  send<Scenario>("PATCH", `/api/scenarios/${scenarioId}/assumptions`, body);

export const coordinateEvent = (scenarioId: string, windowId: string, tailHours = 8) =>
  send<CoordinationResult>("POST", `/api/scenarios/${scenarioId}/simulate/event`, { windowId, tailHours });

export const fetchAgenticConfig = () => get<AgenticConfig>("/api/agentic/config");
export const fetchOwnerAgents = (scenarioId: string) => get<OwnerAgentsResponse>(`/api/scenarios/${scenarioId}/owner-agents`);
export const runAgentic = (scenarioId: string, windowId: string, incentivePricePerMwh: number, provider?: "stub" | "openai", tailHours = 8) =>
  send<AgenticRun>("POST", `/api/scenarios/${scenarioId}/events/${windowId}/agentic-run`, { incentivePricePerMwh, provider, tailHours });
export const replayAgentic = (runId: string) => send<AgenticRun>("POST", `/api/agentic-runs/${runId}/replay`);

export const runHistorical = (scenarioId: string, incentivePricePerMwh: number) =>
  send<HistoricalResult>("POST", `/api/scenarios/${scenarioId}/historical-coordination`, { incentivePricePerMwh });
