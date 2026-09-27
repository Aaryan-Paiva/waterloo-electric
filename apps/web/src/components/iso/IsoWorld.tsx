"use client";
import { useEffect, useMemo, useRef } from "react";
import { H, W, buildScene, drawFrame, type Look, type SimState } from "./scene";

interface Props { season: Look["season"]; night: number; phase: SimState["phase"]; active: SimState["active"]; dc: SimState["dc"]; dragging: boolean; hoverLot: number | null }

/** The isometric town. Canvas 2D at 1440x900 logical pixels (CSS-scaled by the stage). Effects are bound to props only. */
export function IsoWorld({ season, night, phase, active, dc, dragging, hoverLot }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const scene = useMemo(() => buildScene(season), [season]);
  const live = useRef({ season, night, phase, active, dc, dragging, hoverLot });
  useEffect(() => { live.current = { season, night, phase, active, dc, dragging, hoverLot }; }, [season, night, phase, active, dc, dragging, hoverLot]);
  const rise = useRef(0);
  const lastDc = useRef<string>("");
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const c = cv.getContext("2d"); if (!c) return;
    let raf = 0, t = 0;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const loop = () => {
      const l = live.current;
      const key = l.dc ? `${l.dc.x},${l.dc.y}` : "";
      if (key !== lastDc.current) { lastDc.current = key; rise.current = reduced || !l.dc ? (l.dc ? 1 : 0) : 0; }
      if (l.dc && rise.current < 1) rise.current = Math.min(1, rise.current + 0.035);
      t += reduced ? 0 : 1;
      drawFrame(c, scene, { phase: l.phase, active: l.active, dc: l.dc, rise: rise.current, t, dragging: l.dragging, hoverLot: l.hoverLot }, { season: l.season, night: l.night });
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [scene]);
  return <canvas ref={ref} width={W} height={H} style={{ position: "absolute", left: 0, top: 0, width: W, height: H, display: "block" }} role="img" aria-label="Isometric town map of the Waterloo demo zone with homes, offices, a depot, batteries and a substation" />;
}
