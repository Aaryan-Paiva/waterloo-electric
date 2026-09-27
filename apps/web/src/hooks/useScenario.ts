"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { addDataCentre, createScenario, fetchAnalysis, getScenario, removeProject, setProjectMw } from "@/lib/api";
import type { CapacityAnalysis, Scenario } from "@/types/api";

/** Owns the scenario for a world. The baseline world is never modified: every edit goes to the scenario.
 *  `version` increments after each change so load series can be refetched. */
export function useScenario(worldId: string) {
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [analysis, setAnalysis] = useState<CapacityAnalysis | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = `capacityos.scenario.${worldId}`;
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const apply = useCallback(async (s: Scenario) => {
    setScenario(s);
    localStorage.setItem(key, s.id);
    setAnalysis(await fetchAnalysis(s.id));
    setVersion((v) => v + 1);
  }, [key]);

  const run = useCallback(async (fn: () => Promise<Scenario>) => {
    setBusy(true);
    setError(null);
    try { await apply(await fn()); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }, [apply]);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const saved = localStorage.getItem(key);
        let s: Scenario | null = null;
        if (saved) { try { s = await getScenario(saved); } catch { s = null; } }
        s = s ?? (await createScenario(worldId, "Baseline"));
        if (!live) return;
        await apply(s);
      } catch (e) { if (live) setError(String(e)); }
    })();
    return () => { live = false; };
  }, [worldId, key, apply]);

  const reset = useCallback(() => run(() => createScenario(worldId, "Baseline")), [run, worldId]);
  const goldenDemo = useCallback(() => run(async () => {
    const s = await createScenario(worldId, "Golden demo: 20 MW data centre");
    return addDataCentre(s.id, 20);
  }), [run, worldId]);
  const addDc = useCallback((mw: number) => scenario && run(() => addDataCentre(scenario.id, mw)), [run, scenario]);
  const removeDc = useCallback((pid: string) => scenario && run(() => removeProject(scenario.id, pid)), [run, scenario]);
  const setMw = useCallback((pid: string, mw: number) => {
    if (!scenario) return;
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => { void run(() => setProjectMw(scenario.id, pid, mw)); }, 250);
  }, [run, scenario]);

  return { scenario, analysis, version, busy, error, reset, goldenDemo, addDc, removeDc, setMw };
}
