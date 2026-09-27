// Mirrors apps/api/src/schemas (camelCase). Keep in sync with CLAUDE.md §12.
export type ProvenanceType = "observed" | "modeled" | "hypothetical" | "derived";

export interface Provenance {
  type: ProvenanceType;
  sourceName?: string | null;
  sourceUrl?: string | null;
  retrievedAt?: string | null;
  notes?: string | null;
}

export interface Zone {
  id: string;
  name: string;
  timezone: string;
  capacityMw: number;
  capacityProvenance: "observed" | "modeled" | "user_assumption";
  historicalStart: string;
  historicalEnd: string;
  worldSeed: number;
}

export interface HistoricalLoadPoint {
  timestamp: string;
  loadMw: number;
  observedZoneMw?: number | null;
  sourceId: string;
  provenance: "observed" | "derived";
  qualityFlag?: string | null;
  meanMw?: number | null; // daily resolution
  minMw?: number | null; // daily resolution
}

export interface LoadResponse {
  zoneId: string;
  mode: "full" | "fixture";
  resolution: "hourly" | "daily";
  capacityMw: number;
  capacityProvenance: string;
  provenance: Provenance;
  points: HistoricalLoadPoint[];
  truncated: boolean;
}

export interface LoadSummary {
  hours: number;
  start: string;
  end: string;
  peakMw: number;
  peakTimestamp: string;
  meanMw: number;
  minMw: number;
  loadFactor: number;
  headroomAtPeakMw: number;
  hoursAboveCapacity: number;
  interpolatedHours: number;
}

export interface WorldState {
  id: string;
  name: string;
  label: string;
  mode: "full" | "fixture";
  zone: Zone;
  loadSummary: LoadSummary;
  provenance: Record<"historicalDemand" | "derPopulation" | "zoneCapacity" | "newProject", Provenance>;
  derAssumptions: Record<string, number>;
}

export interface Project {
  id: string;
  type: "data_center" | "housing" | "ev_depot";
  name: string;
  provenance: "hypothetical";
  nominalLoadMw: number;
  hourlyProfile: number[];
  flexibilityFraction: number;
  metadata: Record<string, unknown>;
}

export interface Scenario {
  id: string;
  zoneId: string;
  name: string;
  createdAt: string;
  seed: number;
  projects: Project[];
  assumptionOverrides: Record<string, unknown>;
  parentScenarioId?: string | null;
}

export interface EventWindow {
  id: string;
  start: string;
  end: string; // exclusive
  hours: number;
  peakDeficitMw: number;
  peakTimestamp: string;
  meanDeficitMw: number;
  energyOverMwh: number;
  days: number;
}

export interface CapacityAnalysis {
  scenarioId: string;
  zoneId: string;
  mode: "full" | "fixture";
  historicalStart: string;
  historicalEnd: string;
  hoursTested: number;
  capacityMw: number;
  capacityProvenance: string;
  baselinePeakMw: number;
  baselinePeakTimestamp: string;
  projectedPeakMw: number;
  projectedPeakTimestamp: string;
  minHeadroomMw: number;
  constrainedHours: number;
  percentWithinCapacity: number;
  affectedDays: number;
  worstDeficitMw: number;
  worstDeficitTimestamp?: string | null;
  windowCount: number;
  windows: EventWindow[];
  byYear: Record<string, { constrainedHours: number; affectedDays: number }>;
  feasibility: "feasible_as_is" | "constraints_detected";
  flexibilityEvaluated: boolean;
  provenance: Record<string, Provenance>;
  note: string;
}

export interface ScenarioLoadPoint {
  timestamp: string;
  baselineLoadMw: number;
  projectLoadMw: number;
  netLoadMw: number;
  deficitMw: number;
  constrainedHours?: number | null;
  qualityFlag?: string | null;
}

export interface ScenarioLoadResponse {
  scenarioId: string;
  zoneId: string;
  mode: "full" | "fixture";
  resolution: "hourly" | "daily";
  capacityMw: number;
  capacityProvenance: string;
  points: ScenarioLoadPoint[];
  truncated: boolean;
}

export type AgentType = "battery" | "ev_fleet" | "building" | "solar";

export interface AgentSummary {
  id: string;
  type: AgentType;
  name: string;
  participating: boolean;
  participationDraw: number;
  dispatchable: boolean;
  provenance: "modeled";
  params: Record<string, string | number | boolean>;
}

export interface AgentStateOut {
  timestamp: string;
  available: boolean;
  unavailableReason?: string | null;
  values: Record<string, string | number | boolean | null>;
}

export interface PotentialOut {
  agentId: string;
  type: AgentType;
  participating: boolean;
  available: boolean;
  potentialMw: number;
  potentialIfEnrolledMw: number;
  sustainedHours: number;
  limitingFactor: string;
  declineReason?: string | null;
}

export interface AgentDetail extends AgentSummary {
  state: AgentStateOut;
  daySeries: AgentStateOut[];
  potential: PotentialOut;
}

export interface TypePotential {
  agents: number;
  participating: number;
  available: number;
  potentialMw: number;
  potentialIfAllEnrolledMw: number;
}

export interface PopulationPotential {
  worldId: string;
  timestamp: string;
  windowHours: number;
  rates: Record<string, number>;
  byType: Record<AgentType, TypePotential>;
  totalPotentialMw: number;
  totalIfAllEnrolledMw: number;
  deficitMw?: number | null;
  coversDeficitPct?: number | null;
  agents: PotentialOut[];
  provenance: "modeled";
  note: string;
}

export interface TypeSummary {
  count: number;
  participating: number;
  participationRateEffective: number;
  capacity: Record<string, number>;
}

export interface PopulationSummary {
  worldId: string;
  seed: number;
  calibrationScale: number;
  participationRates: Record<string, number>;
  byType: Record<AgentType, TypeSummary>;
  totalAgents: number;
  provenance: "modeled";
  notes: string[];
}

export type CoordStatus = "resolved" | "partially_resolved" | "unresolved";

export interface HourRow {
  timestamp: string;
  inWindow: boolean;
  baselineLoadMw: number;
  projectLoadMw: number;
  preDispatchNetMw: number;
  batteryReductionMw: number;
  evReductionMw: number;
  buildingReductionMw: number;
  totalReductionMw: number;
  optimizedNetMw: number;
  capacityMw: number;
  preDeficitMw: number;
  remainingDeficitMw: number;
  violationBefore: boolean;
  violationAfter: boolean;
  solarInformationalMw: number;
}

export interface AgentDispatch {
  agentId: string;
  type: "battery" | "ev_fleet" | "building";
  name: string;
  participating: boolean;
  included: boolean;
  excludedReason?: string | null;
  dispatchMw: number[];
  mode: string[];
  peakMw: number;
  energyMwh: number;
  series: Record<string, number[]>;
  provenance: "modeled";
  ownerId?: string | null;
  pricePerMwh?: number | null;
  deliveredMwh?: number | null;
  cost?: number | null;
}

export interface WindowMetrics {
  hours: number;
  violationHoursBefore: number;
  violationHoursAfter: number;
  energyAboveCapacityBeforeMwh: number;
  energyAboveCapacityAfterMwh: number;
  worstDeficitBeforeMw: number;
  worstDeficitAfterMw: number;
}

export interface CoordinationResult {
  scenarioId: string;
  zoneId: string;
  provenance: "derived";
  status: CoordStatus;
  statusReason: string;
  windowStart: string;
  windowEnd: string;
  horizonEnd: string;
  tailHours: number;
  capacityMw: number;
  window: WindowMetrics;
  tail: WindowMetrics;
  horizon: WindowMetrics;
  peakDispatchMw: number;
  dispatchedEnergyMwh: Record<string, number>;
  participatingAgents: number;
  includedAgents: number;
  hourly: HourRow[];
  agents: AgentDispatch[];
  checks: { name: string; passed: boolean; maxViolation: number }[];
  checksPassed: boolean;
  reconciled: boolean;
  solver: Record<string, string | number | boolean>;
  participationRates: Record<string, number>;
  objectiveWeights: Record<string, number>;
  note: string;
  resourcesProvenance: "modeled";
  mode: "manual" | "agentic";
  clearingCost?: number | null;
}

// ---- Phase 5-6: owner/operator agents (Modeled behavior) and agentic runs (Derived) ----
export type OwnerType = "battery_operator" | "ev_aggregator" | "building_portfolio";
export interface OwnerAgent {
  id: string; name: string; ownerType: OwnerType; controlledAssetIds: string[]; provenance: "modeled";
  economic: { minCompensationPerMwh: number; targetMargin: number; priceSensitivity: number };
  operational: { reservePreference: number; comfortPriority: number; driverSatisfactionPriority: number; degradationSensitivity: number; maxEventHours: number; maxEventsPerMonth: number; deadlineStrictness: number };
  behavioral: { riskTolerance: number; participationTendency: number };
}
export interface OwnerAgentsResponse { zoneId: string; owners: OwnerAgent[]; flexibleAssets: number; unownedAssets: string[]; note: string }
export interface AgenticConfig { default: string; stubAvailable: boolean; openaiAvailable: boolean; openaiKeyConfigured: boolean; openaiSdkInstalled: boolean; model: string; timeoutSeconds: number }
export interface Block { startHour: number; endHour: number; mw: number }
export interface AssetValidation { assetId: string; status: "valid" | "invalid"; violation?: string | null; requested: Block[]; feasibleEnvelope: Block[]; explanation: string }
export interface OfferRecord {
  id: string; ownerId: string; revision: number; status: "accepted" | "rejected" | "revised" | "priced_out"; counteroffer: boolean; offeredMwh: number; peakMw: number;
  body: { assetOffers: { assetId: string; blocks: Block[] }[]; pricePerMwh: number; conditions: string[]; explanation: string };
  validation: { status: "valid" | "invalid"; lines: AssetValidation[]; violation?: string | null; explanation: string };
}
export type OwnerStatus = "idle" | "evaluating" | "offered" | "declined" | "revising" | "validation_failed" | "accepted" | "rejected" | "priced_out" | "fallback";
export interface OwnerRecord {
  ownerId: string; status: OwnerStatus; declineCode?: string | null; decisionExplanation: string; offers: OfferRecord[]; providerUsed: string; fallbackReason?: string | null;
  agentCalls: number; durationMs: number; dispatchedMwh: number; cost: number;
}
export interface TraceEvent { seq: number; type: string; ownerId?: string | null; payload: Record<string, unknown> }
export interface MarketSummary {
  requestedPeakMw: number; requestedMwh: number; offeredPeakMw: number; offeredMwh: number; validatedPeakMw: number; validatedMwh: number; pricedOutMwh: number;
  dispatchedPeakMw: number; dispatchedMwh: number; remainingWorstDeficitMw: number; remainingEnergyAboveCapacityMwh: number; clearingCost: number; incentivePricePerMwh: number;
  ownersTotal: number; ownersOffered: number; ownersDeclined: number; ownersRejected: number; ownersPricedOut: number; ownersAccepted: number;
}
export interface FlexibilityRequest {
  id: string; scenarioId: string; zoneId: string; eventWindowId?: string | null; start: string; end: string; hours: string[]; requestedMwByHour: number[];
  peakRequestedMw: number; requestedMwh: number; incentivePricePerMwh: number; capacityMw: number; createdAt: string; provenance: "derived";
}
export interface AgenticRun {
  id: string; replayOf?: string | null; scenarioId: string; mode: "agentic";
  provider: { requested: string; used: string; model?: string | null; fallbackReason?: string | null };
  request: FlexibilityRequest; owners: OwnerAgent[]; records: OwnerRecord[]; trace: TraceEvent[]; market: MarketSummary; coordination: CoordinationResult;
  diagnostics: { agentCalls: number; failedCalls: number; timeouts: number; fallbacks: number; durationMs: number; inputTokens?: number | null; outputTokens?: number | null };
  resultHash: string; note: string;
  decisionSource: "llm_openai" | "mixed_llm_and_stub" | "deterministic_stub" | "replay"; llmOwnerCount: number;
}

// ---- Phase 7: historical coordination (deterministic owner policy, 0 LLM calls) ----
export type Season = "winter" | "spring" | "summer" | "fall";
export type Severity = "minor" | "moderate" | "major" | "severe";
export interface ByType { battery: number; evFleet: number; building: number }
export interface HistEvent {
  windowId: string; clusterId: string; start: string; end: string; hours: number; year: number; season: Season; severity: Severity; status: CoordStatus;
  requestedPeakMw: number; requestedMwh: number; ownersOffering: number; offeredMwh: number; validatedMwh: number; pricedOutMwh: number; dispatchedMwh: number; dispatchedPeakMw: number;
  clearingCost: number; byTypeMwh: ByType; violationHoursBefore: number; violationHoursAfter: number; energyAboveCapacityBeforeMwh: number; energyAboveCapacityAfterMwh: number;
  worstDeficitBeforeMw: number; worstDeficitAfterMw: number;
}
export interface HistCluster {
  id: string; windowIds: string[]; start: string; end: string; horizonEnd: string; horizonHours: number; carryInBatteryMwh: number; carryOutBatteryMwh: number; gapRecoveredMwh: number;
  ownersAccepted: number; ownersDeclined: number; ownersRejected: number; ownersPricedOut: number; solverStatus: string; checksPassed: boolean; reconciled: boolean;
}
export interface Agg {
  events: number; resolved: number; partiallyResolved: number; unresolved: number; violationHoursBefore: number; violationHoursAfter: number;
  energyAboveCapacityBeforeMwh: number; energyAboveCapacityAfterMwh: number; worstDeficitBeforeMw: number; worstDeficitAfterMw: number;
  requestedMwh: number; offeredMwh: number; validatedMwh: number; dispatchedMwh: number; clearingCost: number; byTypeMwh: ByType;
}
export interface HistHour { timestamp: string; inWindow: boolean; preNetMw: number; optimizedNetMw: number; batteryMw: number; evMw: number; buildingMw: number }
export interface HistoricalResult {
  id: string; scenarioId: string; zoneId: string; provenance: "derived"; ownerBehaviorProvenance: "modeled"; decisionSource: "deterministic_owner_policy"; llmCalls: number;
  policyVersion: string; incentivePricePerMwh: number; tailHours: number; mergeGapHours: number; capacityMw: number; hoursTested: number; periodStart: string; periodEnd: string;
  totals: Agg; byYear: Record<string, Agg>; bySeason: Record<string, Agg>; bySeverity: Record<string, Agg>;
  byDerType: { type: "battery" | "ev_fleet" | "building"; dispatchedMwh: number; share: number; eventsServed: number; clearingCost: number }[];
  events: HistEvent[]; clusters: HistCluster[]; hourly: HistHour[]; checks: { name: string; passed: boolean; detail: string }[]; checksPassed: boolean;
  resultHash: string; durationMs: number; cached: boolean; note: string;
}
