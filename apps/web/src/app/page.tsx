import Link from "next/link";

const PAPER = "#FBF7EE", INK = "#1D2320", LINE = "#D9D1BE", AMB = "#F2A72E", TEAL = "#1F9E89", CORAL = "#E5533D";
const FD = "var(--font-display), 'Bricolage Grotesque', system-ui, sans-serif";
const MUT = "#4A4F45", MUT2 = "#8A8F82";

const PILLARS: [string, string, string][] = [
  ["Real demand", "Southwest-zone hourly load from IESO — the actual shape of a Waterloo day, in every season, not a synthetic curve.", TEAL],
  ["Real agents", "18 seeded owner agents, each backed by a real LLM call, decide whether to offer flexibility, at what price, or decline — not a fixed participation rate.", AMB],
  ["Real physics", "Every offer is checked against a deterministic model of what that battery, EV fleet, or building can actually deliver before anything is scheduled.", CORAL],
  ["Real optimization", "OR-Tools clears the market. The LLM proposes; it never sets a dispatch number, and it can't override the physics.", "#3F86D8"],
];

const STEPS: [string, string][] = [
  ["Drop in a new load", "A data centre, 1,000 homes, or an EV depot, onto a live isometric Waterloo."],
  ["Owner agents decide", "18 owner agents — real OpenAI agents, or a labelled deterministic policy — offer flexibility or decline, at their own price."],
  ["Physics checks every offer", "A validator cuts anything a battery, EV fleet or building cannot actually deliver, before it reaches the optimizer."],
  ["An optimizer clears it", "OR-Tools picks the dispatch. You get a plain result: holds, partly holds, or breaks, by how much."],
];

const WHO: [string, string][] = [
  ["Utility & municipal planners", "Screen a new interconnection request against a flexibility program before committing to a costly, months-long study."],
  ["VPP & flexibility-program designers", "Set an incentive and a participation target, then see the actual constrained hours it would need to cover."],
  ["Developers & site teams", "Test whether your data centre, depot, or housing project fits before you're locked into a capacity request."],
];

export default function Home() {
  return (
    <main style={{ background: INK, color: PAPER, fontFamily: "var(--font-body), 'IBM Plex Sans', system-ui, sans-serif" }}>
      {/* HERO */}
      <div className="mx-auto max-w-5xl px-6 pt-16 pb-20 sm:pt-24 sm:pb-28">
        <div className="flex items-center gap-2 text-sm" style={{ color: "#C9C2AE" }}>
          <span style={{ width: 10, height: 10, borderRadius: 3, background: AMB, display: "inline-block" }} />
          AF Hacks: Growing Canada · live demo, not a mockup
        </div>
        <h1 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-5 max-w-3xl text-4xl sm:text-6xl leading-[1.05]">
          Prove a flexibility program can carry the next load — before you commit to it.
        </h1>
        <p className="mt-6 max-w-2xl text-lg sm:text-xl" style={{ color: "#D8D3C4", lineHeight: 1.55 }}>
          Drop a new AI data centre, housing development, or EV depot onto a live Waterloo grid, and watch whether a specific flexibility program — a VPP, with its own incentive and enrolment — can absorb it. Checked against real demand, real physics, and a real optimizer, in every season.
        </p>
        <div className="mt-9 flex flex-wrap gap-3">
          <Link href="/sandbox" style={{ background: AMB, color: INK }} className="rounded-full px-7 py-3 text-base font-semibold hover:opacity-90 transition">
            Open the product →
          </Link>
          <Link href="/how-it-works" style={{ border: "1px solid #3A4038", color: PAPER }} className="rounded-full px-7 py-3 text-base font-semibold hover:bg-white/5 transition">
            How it works
          </Link>
        </div>
        <div className="mt-14 grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-5 max-w-3xl border-t pt-8" style={{ borderColor: "#2C332D" }}>
          {[["18", "owner agents deciding per run"], ["4", "real seasons stress-tested"], ["3", "load types you can drop in"], ["0", "made-up numbers — everything traces to a real run"]].map(([n, l]) => (
            <div key={l}>
              <div style={{ fontFamily: FD, fontWeight: 700, color: AMB }} className="text-3xl">{n}</div>
              <div className="mt-1 text-xs" style={{ color: "#9C9787", lineHeight: 1.4 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* PAPER BODY */}
      <div style={{ background: PAPER, color: INK }} className="rounded-t-[32px]">
        <div className="mx-auto max-w-5xl px-6 py-16 sm:py-20">

          {/* PROBLEM / WHY NOW */}
          <div className="grid gap-10 sm:grid-cols-2">
            <div>
              <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">The problem</div>
              <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-3xl">Big new loads are outrunning the grid&apos;s paperwork.</h2>
              <p className="mt-3 text-base" style={{ color: MUT, lineHeight: 1.6 }}>
                AI data centres, EV charging depots, and new housing are showing up faster than physical infrastructure upgrades can follow. A traditional interconnection study is slow, static, and answers only one scenario at a time.
              </p>
            </div>
            <div>
              <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">Why now</div>
              <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-3xl">Flexibility programs are already real money.</h2>
              <p className="mt-3 text-base" style={{ color: MUT, lineHeight: 1.6 }}>
                Ontario&apos;s Peak Perks VPP already has over 100,000 enrolled homes — flexibility isn&apos;t a theory, it&apos;s a live program. What&apos;s missing is a fast way to test whether a <em>specific</em> new load fits within a <em>specific</em> program&apos;s constraints, before anyone commits capital.
              </p>
            </div>
          </div>

          {/* PRODUCT PILLARS */}
          <div className="mt-20">
            <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">Why it holds up</div>
            <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-3xl">Four things keep this from being &quot;an LLM says it fits.&quot;</h2>
            <div className="mt-7 grid gap-5 sm:grid-cols-2">
              {PILLARS.map(([h, b, c]) => (
                <div key={h} className="rounded-2xl p-5" style={{ border: `1px solid ${LINE}` }}>
                  <div className="flex items-center gap-2">
                    <span style={{ width: 8, height: 8, borderRadius: 4, background: c, display: "inline-block" }} />
                    <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-base">{h}</div>
                  </div>
                  <div className="mt-2 text-sm" style={{ color: MUT, lineHeight: 1.55 }}>{b}</div>
                </div>
              ))}
            </div>
          </div>

          {/* HOW IT WORKS TEASER */}
          <div className="mt-20">
            <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">The loop</div>
            <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-3xl">From a dragged load to a verified answer.</h2>
            <div className="mt-7 grid gap-5 sm:grid-cols-4">
              {STEPS.map(([h, b], i) => (
                <div key={h}>
                  <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-sm">{String(i + 1).padStart(2, "0")}</div>
                  <div style={{ fontFamily: FD, fontWeight: 700 }} className="mt-1 text-base">{h}</div>
                  <div className="mt-1 text-sm" style={{ color: MUT, lineHeight: 1.5 }}>{b}</div>
                </div>
              ))}
            </div>
            <Link href="/how-it-works" style={{ color: TEAL }} className="mt-6 inline-block text-sm font-semibold hover:underline">
              See the full methodology, provenance, and FAQ →
            </Link>
          </div>

          {/* WHO IT'S FOR */}
          <div className="mt-20">
            <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">Who it&apos;s for</div>
            <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-3xl">Three teams that need this before a real study.</h2>
            <div className="mt-7 grid gap-5 sm:grid-cols-3">
              {WHO.map(([h, b]) => (
                <div key={h} className="rounded-2xl p-5" style={{ background: "rgba(29,35,32,.03)" }}>
                  <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-base">{h}</div>
                  <div className="mt-2 text-sm" style={{ color: MUT, lineHeight: 1.55 }}>{b}</div>
                </div>
              ))}
            </div>
          </div>

          {/* ROADMAP */}
          <div className="mt-20 rounded-2xl p-7" style={{ border: `1px solid ${LINE}` }}>
            <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">What&apos;s next</div>
            <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl">From synthetic world to real pilot.</h2>
            <p className="mt-3 text-base max-w-2xl" style={{ color: MUT, lineHeight: 1.6 }}>
              The simulator itself doesn&apos;t change for a real deployment — only its inputs do. The next step is a pilot with a local distribution utility: real meter data and real device ratings in place of the seeded synthetic population, and real enrolled participants in place of modeled owner agents. Every other layer — the physical validator, the optimizer, the provenance model — carries over unchanged.
            </p>
          </div>

          {/* CTA */}
          <div className="mt-20 rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4" style={{ background: INK, color: PAPER }}>
            <div>
              <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-xl">Try it on a real Waterloo day.</div>
              <div className="text-sm mt-1" style={{ color: "#C9C2AE" }}>No sign-up. Drag a load in and watch it rebalance.</div>
            </div>
            <Link href="/sandbox" style={{ background: AMB, color: INK }} className="rounded-full px-7 py-3 text-base font-semibold hover:opacity-90 transition whitespace-nowrap">
              Open the product →
            </Link>
          </div>

          <div className="mt-10 text-xs" style={{ color: MUT2, lineHeight: 1.6 }}>
            Built for AF Hacks: Growing Canada. A planning simulation, not a forecast, a feasibility verdict, or a utility-grade engineering study.
            {" "}<span style={{ color: CORAL }}>●</span> hypothetical · <span style={{ color: AMB }}>●</span> modeled · <span style={{ color: TEAL }}>●</span> derived from real data.
          </div>
        </div>
      </div>
    </main>
  );
}
