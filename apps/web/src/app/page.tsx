import Link from "next/link";

const PAPER = "#FBF7EE", INK = "#1D2320", LINE = "#D9D1BE", AMB = "#F2A72E", TEAL = "#1F9E89", CORAL = "#E5533D";
const FD = "var(--font-display), 'Bricolage Grotesque', system-ui, sans-serif";

const STEPS: [string, string][] = [
  ["Drop in a new load", "A data centre, 1,000 homes, or an EV depot, onto a live isometric Waterloo."],
  ["Owner agents decide", "18 owner agents — real OpenAI agents, or a labelled deterministic policy — offer flexibility or decline, at their own price."],
  ["Physics checks every offer", "A validator cuts anything a battery, EV fleet or building cannot actually deliver, before it reaches the optimizer."],
  ["An optimizer clears it", "OR-Tools picks the dispatch. You get a plain result: holds, partly holds, or breaks, by how much."],
];

const PROVENANCE: [string, string][] = [
  ["Hourly demand shape", "Real IESO Southwest-zone data, derived"],
  ["Devices and owner agents", "Synthetic, seeded"],
  ["90 MW zone capacity", "Modeled assumption"],
  ["Loads you add", "Hypothetical"],
  ["Every result shown", "Derived from the above, never observed"],
];

export default function Home() {
  return (
    <main style={{ background: INK, color: PAPER, fontFamily: "var(--font-body), 'IBM Plex Sans', system-ui, sans-serif", minHeight: "100vh" }}>
      <div className="mx-auto max-w-3xl px-6 py-20 sm:py-28">
        <div className="flex items-center gap-2 text-sm" style={{ color: "#C9C2AE" }}>
          <span style={{ width: 10, height: 10, borderRadius: 3, background: AMB, display: "inline-block" }} />
          AF Hacks: Growing Canada
        </div>
        <h1 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-4 text-4xl sm:text-6xl leading-[1.05]">
          A testing ground for flexibility programs.
        </h1>
        <p className="mt-6 text-lg sm:text-xl" style={{ color: "#D8D3C4", lineHeight: 1.55 }}>
          Drop a new AI data centre, a housing development, or an EV depot onto a live Waterloo grid, and watch whether a flexibility program (a VPP) can absorb it — checked against real demand, real physics, and a real optimizer, in every season.
        </p>
        <div className="mt-9 flex flex-wrap gap-3">
          <Link href="/sandbox" style={{ background: AMB, color: INK }} className="rounded-full px-7 py-3 text-base font-semibold hover:opacity-90 transition">
            Open the sandbox →
          </Link>
          <a href="#how" style={{ border: `1px solid ${"#3A4038"}`, color: PAPER }} className="rounded-full px-7 py-3 text-base font-semibold hover:bg-white/5 transition">
            How it works
          </a>
        </div>
      </div>

      <div style={{ background: PAPER, color: INK }} className="rounded-t-[32px]">
        <div className="mx-auto max-w-3xl px-6 py-16 sm:py-20">
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="text-2xl sm:text-3xl">The problem</h2>
          <p className="mt-3 text-base sm:text-lg" style={{ color: "#4A4F45", lineHeight: 1.6 }}>
            Big new electrical loads, AI data centres especially, are hard to connect: physical grid upgrades take years. Flexibility is the alternative, and it&apos;s already real in Canada — Ontario&apos;s Peak Perks VPP has over 100,000 enrolled homes. But there&apos;s no quick way to test a flexibility program against a specific new load before committing to it. Waterloo Electric is that testing ground.
          </p>

          <h2 id="how" style={{ fontFamily: FD, fontWeight: 700 }} className="text-2xl sm:text-3xl mt-14">How it works</h2>
          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            {STEPS.map(([h, b], i) => (
              <div key={h} className="rounded-2xl p-5" style={{ border: `1px solid ${LINE}`, background: "rgba(29,35,32,.03)" }}>
                <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-sm">{String(i + 1).padStart(2, "0")}</div>
                <div style={{ fontFamily: FD, fontWeight: 700 }} className="mt-1 text-lg">{h}</div>
                <div className="mt-1 text-sm" style={{ color: "#4A4F45", lineHeight: 1.5 }}>{b}</div>
              </div>
            ))}
          </div>

          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="text-2xl sm:text-3xl mt-14">What it is not</h2>
          <p className="mt-3 text-base" style={{ color: "#4A4F45", lineHeight: 1.6 }}>
            Not a forecast, not a VPP operator, not a recommendation engine handing out a verdict, and not a claim about any real Waterloo customer or asset. It&apos;s a planning simulation: what would happen to a set of flexibility constraints, under real Waterloo-shaped conditions, if this load joined the grid.
          </p>

          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="text-2xl sm:text-3xl mt-14">What&apos;s real, what&apos;s modeled</h2>
          <div className="mt-5 overflow-hidden rounded-2xl" style={{ border: `1px solid ${LINE}` }}>
            {PROVENANCE.map(([k, v], i) => (
              <div key={k} className="flex items-center justify-between px-5 py-3 text-sm" style={{ borderTop: i ? `1px solid ${LINE}` : undefined }}>
                <span>{k}</span>
                <span style={{ color: "#6A6F66", fontWeight: 600 }}>{v}</span>
              </div>
            ))}
          </div>

          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="text-2xl sm:text-3xl mt-14">Who it&apos;s for</h2>
          <p className="mt-3 text-base" style={{ color: "#4A4F45", lineHeight: 1.6 }}>
            Utility and municipal planners, VPP and flexibility-program designers, and developers evaluating a site&apos;s electrical capacity. The next step after this hackathon is a pilot with a local distribution utility: real meter data, real device ratings, real enrolled participants, in place of the synthetic world — the simulator itself would not change.
          </p>

          <div className="mt-14 rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4" style={{ background: INK, color: PAPER }}>
            <div>
              <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-xl">Try it on a real Waterloo day.</div>
              <div className="text-sm mt-1" style={{ color: "#C9C2AE" }}>No sign-up. Drag a load in and watch it rebalance.</div>
            </div>
            <Link href="/sandbox" style={{ background: AMB, color: INK }} className="rounded-full px-7 py-3 text-base font-semibold hover:opacity-90 transition whitespace-nowrap">
              Open the sandbox →
            </Link>
          </div>

          <div className="mt-10 text-xs" style={{ color: "#8A8F82", lineHeight: 1.6 }}>
            Built for AF Hacks: Growing Canada. A planning simulation, not a forecast, a recommendation engine, a feasibility verdict, or a utility-grade engineering study.
            {" "}<span style={{ color: CORAL }}>●</span> hypothetical · <span style={{ color: AMB }}>●</span> modeled · <span style={{ color: TEAL }}>●</span> derived from real data.
          </div>
        </div>
      </div>
    </main>
  );
}
