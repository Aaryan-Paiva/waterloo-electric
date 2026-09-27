"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchAgentDetail, fetchAgents, fetchPopulation, fetchPotential, patchAssumptions } from "@/lib/api";
import type { AgentDetail, AgentSummary, PopulationPotential, PopulationSummary } from "@/types/api";

type RateKey = "evParticipation" | "batteryParticipation" | "buildingParticipation";

/** Read-only view of the synthetic DER population at the playback timestamp. Nothing here dispatches or optimizes.
 *  Potential requests are debounced so scrubbing/playback never floods the API. */
export function useAgents(worldId: string, scenarioId: string | undefined, timestamp: string | undefined, windowHours: number, selectedId: string | null) {
  const [population, setPopulation] = useState<PopulationSummary | null>(null);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [potential, setPotential] = useState<PopulationPotential | null>(null);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [rev, setRev] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const rateTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!scenarioId) return;
    let live = true;
    Promise.all([fetchPopulation(worldId, scenarioId), fetchAgents(worldId, scenarioId)])
      .then(([p, a]) => { if (live) { setPopulation(p); setAgents(a); } })
      .catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [worldId, scenarioId, rev]);

  useEffect(() => {
    if (!scenarioId || !timestamp) return;
    let live = true;
    const t = setTimeout(() => {
      fetchPotential(worldId, timestamp, windowHours, scenarioId).then((r) => live && setPotential(r)).catch((e) => live && setError(String(e)));
    }, 280);
    return () => { live = false; clearTimeout(t); };
  }, [worldId, scenarioId, timestamp, windowHours, rev]);

  useEffect(() => {
    if (!selectedId || !timestamp) return;
    let live = true;
    const t = setTimeout(() => {
      fetchAgentDetail(worldId, selectedId, timestamp, windowHours, scenarioId).then((r) => live && setDetail(r)).catch((e) => live && setError(String(e)));
    }, 280);
    return () => { live = false; clearTimeout(t); };
  }, [worldId, selectedId, timestamp, windowHours, scenarioId, rev]);

  const setRate = useCallback((key: RateKey, value: number) => {
    if (!scenarioId) return;
    if (rateTimer.current) clearTimeout(rateTimer.current);
    rateTimer.current = setTimeout(() => { patchAssumptions(scenarioId, { [key]: value }).then(() => setRev((r) => r + 1)).catch((e) => setError(String(e))); }, 300);
  }, [scenarioId]);

  return { population, agents, potential, detail: selectedId ? detail : null, setRate, error };
}
