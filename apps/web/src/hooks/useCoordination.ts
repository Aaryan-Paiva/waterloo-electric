"use client";
import { useCallback, useState } from "react";
import { coordinateEvent } from "@/lib/api";
import type { CoordinationResult } from "@/types/api";

/** Runs the deterministic single-event optimizer. The result is derived and read-only; a `key` records the inputs
 *  it was computed for so the UI can mark it stale when the scenario or participation changes. */
export function useCoordination(scenarioId: string | undefined) {
  const [result, setResult] = useState<CoordinationResult | null>(null);
  const [key, setKey] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (windowId: string, inputKey: string) => {
    if (!scenarioId) return;
    setBusy(true);
    setError(null);
    try { setResult(await coordinateEvent(scenarioId, windowId)); setKey(inputKey); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }, [scenarioId]);

  const clear = useCallback(() => { setResult(null); setKey(""); setError(null); }, []);
  return { result, key, busy, error, run, clear };
}
