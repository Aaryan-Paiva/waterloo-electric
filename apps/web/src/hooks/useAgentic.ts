"use client";
import { useCallback, useEffect, useState } from "react";
import { fetchAgenticConfig, fetchOwnerAgents, replayAgentic, runAgentic } from "@/lib/api";
import type { AgenticConfig, AgenticRun, OwnerAgent } from "@/types/api";

/** Agentic Mode state. The run is a stored, derived record; the UI only replays its recorded trace (nothing here is simulated client-side).
 *  `key` records the scenario inputs the run was computed for so the UI can mark it stale. */
export function useAgentic(scenarioId: string | undefined, enabled: boolean) {
  const [config, setConfig] = useState<AgenticConfig | null>(null);
  const [owners, setOwners] = useState<OwnerAgent[]>([]);
  const [run, setRun] = useState<AgenticRun | null>(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let live = true;
    fetchAgenticConfig().then((c) => live && setConfig(c)).catch(() => undefined);
    return () => { live = false; };
  }, [enabled]);
  useEffect(() => {
    if (!enabled || !scenarioId) return;
    let live = true;
    fetchOwnerAgents(scenarioId).then((r) => live && setOwners(r.owners)).catch(() => undefined);
    return () => { live = false; };
  }, [enabled, scenarioId]);

  const start = useCallback(async (windowId: string, incentive: number, provider: "stub" | "openai", inputKey: string) => {
    if (!scenarioId) return;
    setBusy(true); setError(null);
    try { setRun(await runAgentic(scenarioId, windowId, incentive, provider)); setKey(inputKey); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }, [scenarioId]);
  const replay = useCallback(async () => {
    if (!run) return;
    setBusy(true); setError(null);
    try { setRun(await replayAgentic(run.id)); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }, [run]);
  const clear = useCallback(() => { setRun(null); setKey(""); setError(null); }, []);
  return { config, owners, run, key, busy, error, start, replay, clear };
}
