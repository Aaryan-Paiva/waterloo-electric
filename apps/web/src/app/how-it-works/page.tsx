import Link from "next/link";

const PAPER = "#FBF7EE", INK = "#1D2320", LINE = "#D9D1BE", AMB = "#F2A72E", TEAL = "#1F9E89", CORAL = "#E5533D";
const FD = "var(--font-display), 'Bricolage Grotesque', system-ui, sans-serif";
const MUT = "#4A4F45", MUT2 = "#8A8F82";

const PIPELINE: [string, string, string][] = [
  ["1", "A real day, a real zone", "Every run replays an actual historical hour from IESO's Southwest zone — the real shape of Waterloo demand for that season, not a synthetic curve. You add a hypothetical load on top of it."],
  ["2", "A seeded synthetic population", "234 device clusters — batteries, EV fleets, buildings, solar — are generated from a fixed seed so the same settings always produce the same world. 18 owner agents are grouped from those clusters, deterministically."],
  ["3", "Owner agents decide", "Each owner agent is backed by a real OpenAI call (or a labelled deterministic policy if no key is configured, or if a call fails). It sees its own devices' state and the zone's request, then offers a quantity and a price, or declines. Nothing here is scripted."],
  ["4", "A physical validator checks every offer", "Before anything reaches the optimizer, a deterministic model checks whether the battery, EV fleet, or building the offer came from could actually deliver it — SOC limits, deadlines, comfort bounds, duration caps. Owners get one bounded revision if their offer is rejected."],
  ["5", "OR-Tools clears the market", "A real mixed-integer optimizer selects the dispatch that resolves the overload at the lowest cost, from only the offers that survived validation. The LLM never sets a dispatch number and cannot override this step."],
  ["6", "A plain result — and a way to fix it", "Holds, partly holds, or breaks, with the exact MW absorbed and remaining. If it doesn't hold, \"Fix it\" searches verified changes to the program — enrolment, incentive, device counts — or the smallest zone-capacity increase that would work, and reruns the real day to confirm each one."],
];

const PROVENANCE: [string, string, string][] = [
  ["Hourly demand shape", "Real IESO Southwest-zone data, derived", TEAL],
  ["Devices and owner agents", "Synthetic, seeded from a fixed seed", AMB],
  ["90 MW zone capacity", "Modeled assumption — no public feeder-level limit was available", AMB],
  ["Loads you add", "Hypothetical — a scenario you're testing, not a real project", CORAL],
  ["Owner offers, dispatch, and results", "Derived from the above by a real run — never hand-tuned or hard-coded", TEAL],
];

const FAQ: [string, string][] = [
  ["Are these real Waterloo customers or devices?", "No. The device population is synthetic and seeded — it's built to be a plausible, reproducible stand-in for what could sit behind an aggregate demand curve, not a claim about any real household, business, or asset."],
  ["Does the LLM control the grid?", "No. LLM owner agents only ever propose an offer (quantity, price, decline). A deterministic physical validator checks every offer against real device limits, and a real optimizer (OR-Tools) makes the dispatch decision. The LLM's output can be discarded; it can never be executed directly."],
  ["What happens if OpenAI is down, rate-limited, or out of credits?", "Every owner falls back independently to a labelled deterministic policy — the run still completes and is still clearly marked (deterministic policy vs. real LLM agents) in the result. Nothing crashes or silently substitutes a fake answer."],
  ["Is the 90 MW capacity real?", "It's a modeled assumption, stated as such everywhere it appears. No public feeder- or station-level capacity figure for this area was available to source directly — this is exactly the kind of number a real pilot would replace with an actual utility-provided limit."],
  ["Does this generalize past Waterloo?", "Yes — the zone is defined by a \"world pack\": a historical demand file, a capacity assumption, and DER population assumptions. A different location needs a different world pack, not different simulation code."],
  ["What would change for a real utility pilot?", "The inputs, not the engine: real meter data in place of the historical fixture, real device ratings in place of the seeded population, and real enrolled participants in place of modeled owner agents. The physical validator, the optimizer, and the provenance model carry over unchanged."],
];

export default function HowItWorks() {
  return (
    <main style={{ background: PAPER, color: INK, fontFamily: "var(--font-body), 'IBM Plex Sans', system-ui, sans-serif" }}>
      <div className="mx-auto max-w-4xl px-6 py-16 sm:py-20">
        <div className="flex items-center gap-2 text-sm" style={{ color: MUT2 }}>
          <span style={{ width: 10, height: 10, borderRadius: 3, background: AMB, display: "inline-block" }} />
          Methodology
        </div>
        <h1 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-4 text-3xl sm:text-5xl leading-[1.08]">
          How a drag on the canvas becomes a verified result.
        </h1>
        <p className="mt-5 max-w-2xl text-lg" style={{ color: MUT, lineHeight: 1.55 }}>
          Six real steps, every one inspectable in the product&apos;s Log tab. No step is faked, randomized for effect, or hard-coded — a rerun of the same inputs produces the same physics and the same optimizer result every time.
        </p>

        {/* PIPELINE */}
        <div className="mt-14 flex flex-col gap-0">
          {PIPELINE.map(([n, h, b], i) => (
            <div key={n} className="flex gap-5 py-6" style={{ borderTop: i ? `1px solid ${LINE}` : undefined }}>
              <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-2xl w-8 shrink-0">{n}</div>
              <div>
                <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-lg sm:text-xl">{h}</div>
                <div className="mt-2 text-sm sm:text-base" style={{ color: MUT, lineHeight: 1.6 }}>{b}</div>
              </div>
            </div>
          ))}
        </div>

        {/* PROVENANCE TABLE */}
        <div className="mt-16">
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="text-2xl sm:text-3xl">What&apos;s real, what&apos;s modeled, what&apos;s yours to test.</h2>
          <p className="mt-3 text-base" style={{ color: MUT, lineHeight: 1.6 }}>Every number in the product carries one of these four labels, visibly, wherever it&apos;s shown.</p>
          <div className="mt-6 overflow-hidden rounded-2xl" style={{ border: `1px solid ${LINE}` }}>
            {PROVENANCE.map(([k, v, c], i) => (
              <div key={k} className="flex items-start justify-between gap-6 px-5 py-4 text-sm" style={{ borderTop: i ? `1px solid ${LINE}` : undefined }}>
                <span style={{ fontWeight: 600 }}>{k}</span>
                <span className="flex items-center gap-2 text-right" style={{ color: MUT }}>
                  <span style={{ width: 7, height: 7, borderRadius: 4, background: c, display: "inline-block", flexShrink: 0 }} />
                  {v}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* WHAT IT IS NOT */}
        <div className="mt-16 rounded-2xl p-7" style={{ background: "rgba(29,35,32,.03)" }}>
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="text-xl">What this is not</h2>
          <p className="mt-3 text-base" style={{ color: MUT, lineHeight: 1.6 }}>
            Not a forecast, not a live VPP operator, not a recommendation engine handing down a verdict, and not a claim about any real Waterloo customer or asset. It&apos;s a planning simulation: what would happen to a set of flexibility constraints, under real Waterloo-shaped conditions, if this load joined the grid — and, if it wouldn&apos;t hold, what verified change would make it hold.
          </p>
        </div>

        {/* FAQ */}
        <div className="mt-16">
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="text-2xl sm:text-3xl">Questions worth asking</h2>
          <div className="mt-6 flex flex-col gap-6">
            {FAQ.map(([q, a]) => (
              <div key={q}>
                <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-base">{q}</div>
                <div className="mt-1.5 text-sm sm:text-base" style={{ color: MUT, lineHeight: 1.6 }}>{a}</div>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="mt-16 rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4" style={{ background: INK, color: PAPER }}>
          <div>
            <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-xl">See it run on a real day.</div>
            <div className="text-sm mt-1" style={{ color: "#C9C2AE" }}>Every step above is visible live in the product&apos;s Log tab.</div>
          </div>
          <Link href="/sandbox" style={{ background: AMB, color: INK }} className="rounded-full px-7 py-3 text-base font-semibold hover:opacity-90 transition whitespace-nowrap">
            Open the product →
          </Link>
        </div>
      </div>
    </main>
  );
}
