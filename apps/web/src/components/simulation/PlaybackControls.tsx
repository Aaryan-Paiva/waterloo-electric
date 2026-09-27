"use client";
import { SPEEDS, type SpeedKey } from "@/hooks/usePlayback";

interface Props {
  playing: boolean;
  setPlaying: (p: boolean) => void;
  speed: SpeedKey;
  setSpeed: (s: SpeedKey) => void;
  index: number;
  length: number;
  seek: (i: number) => void;
  onJumpPeak: () => void;
  onJumpStart: () => void;
  onPrevEvent?: () => void;
  onNextEvent?: () => void;
  years: number[];
  year: number;
  setYear: (y: number) => void;
  time: string;
}

export function PlaybackControls(p: Props) {
  return (
    <div className="panel p-3 flex flex-wrap items-center gap-3" role="group" aria-label="Simulation playback controls">
      <button className="btn" onClick={() => p.setPlaying(!p.playing)} aria-label={p.playing ? "Pause" : "Play"}>
        {p.playing ? "❚❚ Pause" : "▶ Play"}
      </button>
      <div className="flex gap-1" role="group" aria-label="Playback speed">
        {(Object.keys(SPEEDS) as SpeedKey[]).map((k) => (
          <button key={k} className="btn" aria-pressed={p.speed === k} onClick={() => p.setSpeed(k)}>{k}</button>
        ))}
      </div>
      <button className="btn" onClick={p.onJumpStart}>⏮ Start of year</button>
      <button className="btn" onClick={p.onJumpPeak}>⚡ Jump to peak</button>
      {p.onPrevEvent && <button className="btn" onClick={p.onPrevEvent}>◀ Prev event</button>}
      {p.onNextEvent && <button className="btn" onClick={p.onNextEvent}>Next event ▶</button>}
      {p.years.length > 1 && (
        <label className="text-sm flex items-center gap-2" style={{ color: "var(--muted)" }}>
          Year
          <select className="btn" value={p.year} onChange={(e) => p.setYear(Number(e.target.value))}>
            {p.years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
      )}
      <input type="range" className="flex-1 min-w-48" min={0} max={Math.max(0, p.length - 1)} value={p.index}
        onChange={(e) => p.seek(Number(e.target.value))} aria-label="Timeline position" />
      <span className="text-sm tabular-nums" style={{ color: "var(--muted)" }} aria-live="off">{p.time}</span>
    </div>
  );
}
