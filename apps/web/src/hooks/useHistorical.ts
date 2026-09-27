"use client";
import { useCallback, useState } from "react";
import { runHistorical } from "@/lib/api";
import type { HistoricalResult } from "@/types/api";

/** Historical coordination results, kept per user-selected incentive so scenarios can be compared side by side. All results are derived and read-only;
 *  `key` records the scenario version they were computed for (stale results are hidden, not reused). */
export function useHistorical(scenarioId: string | undefined) {
  const [results, setResults] = useState<Record<number, HistoricalResult>>({});
  const [key, setKey] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (incentive: number, inputKey: string) => {
    if (!scenarioId) return;
    setBusy(incentive); setError(null);
    try {
      const r = await runHistorical(scenarioId, incentive);
      setResults((prev) => (key === inputKey ? { ...prev, [incentive]: r } : { [incentive]: r }));
      setKey(inputKey); setSelected(incentive);
    } catch (e) { setError(String(e)); } finally { setBusy(null); }
  }, [scenarioId, key]);
  const clear = useCallback(() => { setResults({}); setKey(""); setSelected(null); setError(null); }, []);
  return { results, key, selected, setSelected, busy, error, run, clear };
}
