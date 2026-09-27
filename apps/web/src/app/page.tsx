import Link from "next/link";
import { FlexEquation } from "@/components/site/FlexEquation";

const PAPER = "#FBF7EE", INK = "#1D2320", LINE = "#D9D1BE", AMB = "#F2A72E", TEAL = "#1F9E89", CORAL = "#E5533D", BLUE = "#3F86D8", VIO = "#8C7AE0";
const FD = "var(--font-display), 'Bricolage Grotesque', system-ui, sans-serif";
const MUT = "#4A4F45", MUT2 = "#8A8F82";

const DRIVERS: [string, string, string][] = [
  ["Housing", "New builds add heat pumps, EVs, and induction cooking to the grid, not just square footage.", TEAL],
  ["EV charging", "Depots and home chargers concentrate large, coincident loads at predictable hours.", BLUE],
  ["Industry", "Electrification of process heat and equipment turns fuel demand into grid demand.", CORAL],
  ["Compute", "AI data centres arrive as single loads the size of a small town — and run near-continuously.", VIO],
];

const HOTSPOTS: [string, string, string, number, number][] = [
  ["1", "Add demand", "Drag a data centre, housing block, or EV depot onto an empty lot.", 46, 66],
  ["2", "Edit VPP rules", "Set enrolment, incentive, battery reserve, EV flexibility, building comfort.", 88.5, 71],
  ["3", "Owner responses", "18 owner agents offer, decline, or revise — inspect every one in the Log.", 87, 5],
  ["4", "Physical validation", "Every offer is checked against real device limits before it's dispatched.", 87, 20],
  ["5", "Result", "Holds, partly holds, or breaks — MW by MW, resource by resource.", 79, 16],
  ["6", "Fix It", "Two verified pathways to close any gap, proven by rerunning the real day.", 92, 5],
];

const LIFECYCLE: [string, string, string, string][] = [
  ["Capacity visibility", "Where is capacity?", "Utility capacity maps and hosting-capacity tools tell you what headroom exists today.", MUT2],
  ["VPP design", "What program design holds?", "CapacityOS stress-tests a specific flexibility program against a specific new load, before anyone commits.", TEAL],
  ["VPP operation", "How do we run enrolled resources?", "DERMS and VPP operating platforms enroll, dispatch, and settle real participants day to day.", MUT2],
];

const PROVENANCE: [string, string, string][] = [
  ["Observed", "Public IESO hourly reporting for the Southwest zone", "#2E6E3E"],
  ["Derived", "The hourly demand shape built from that reporting", TEAL],
  ["Modeled", "234 device clusters, 18 owner agents, the 90 MW zone capacity", AMB],
  ["Hypothetical", "Any load you drag in — a scenario you're testing, not a real project", CORAL],
  ["Calculated", "Every offer, dispatch, and result — always derived, never hand-tuned", BLUE],
];

const PILOT: [string, string, string][] = [
  ["Sandbox", "Today", "Public IESO demand data, a seeded synthetic DER population, an assumed zone capacity."],
  ["Calibrated utility pilot", "Next", "Swap in a utility's local constraints, real DER inventory, and the program rules actually being considered."],
  ["Operational deployment", "Then", "Hand the selected, stress-tested design to a real DERMS or utility program to enroll and run."],
];

const DECISIONS: [string, string][] = [
  ["A utility", "“What participation target do we need to defer this upgrade?”"],
  ["An aggregator", "“What incentive and resource mix should we deploy for this request?”"],
  ["A consultant", "“Which program design survives the hardest historical scenario?”"],
  ["A municipality", "“How much can flexibility contribute before infrastructure is still required?”"],
];

const LIMITATIONS = [
  "One-zone capacity screening, not feeder- or device-level power flow.",
  "Owner agents are modeled economic behavior, not calibrated predictions of real customers.",
  "CapacityOS does not operate real resources — it's a design and stress-testing tool, not a DERMS.",
];

export default function Home() {
  return (
    <main style={{ background: INK, color: PAPER, fontFamily: "var(--font-body), 'IBM Plex Sans', system-ui, sans-serif" }}>
      {/* HERO — 45/55 copy/visual */}
      <div className="mx-auto max-w-6xl px-6 pt-14 pb-16 sm:pt-20 sm:pb-20">
        <div className="grid gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:items-center">
          <div>
            <h1 style={{ fontFamily: FD, fontWeight: 700 }} className="text-3xl sm:text-[2.75rem] leading-[1.08]">
              Prove a VPP holds before someone deploys it.
            </h1>
            <p className="mt-5 text-base sm:text-lg" style={{ color: "#D8D3C4", lineHeight: 1.55 }}>
              Drop a new AI data centre, housing development, or EV depot onto the live Ontario Southwest Zone Sandbox, and watch whether a specific flexibility program can absorb it — real demand, real physics, a real optimizer.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/sandbox" style={{ background: AMB, color: INK }} className="rounded-full px-6 py-3 text-base font-semibold hover:opacity-90 transition">
                Launch sandbox →
              </Link>
              <a href="#problem" style={{ border: "1px solid #3A4038", color: PAPER }} className="rounded-full px-6 py-3 text-base font-semibold hover:bg-white/5 transition">
                See the problem
              </a>
            </div>
            <div className="mt-10 grid grid-cols-3 gap-x-5 gap-y-4 max-w-sm border-t pt-6" style={{ borderColor: "#2C332D" }}>
              {[["18", "owner agents"], ["4", "seasons tested"], ["3", "load types"]].map(([n, l]) => (
                <div key={l}>
                  <div style={{ fontFamily: FD, fontWeight: 700, color: AMB }} className="text-2xl">{n}</div>
                  <div className="mt-1 text-xs" style={{ color: "#9C9787", lineHeight: 1.35 }}>{l}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative rise-in">
            <div className="rounded-2xl overflow-hidden shadow-2xl" style={{ border: "1px solid #2C332D" }}>
              <div className="flex items-center gap-1.5 px-3.5 py-2.5" style={{ background: "#141814" }}>
                <span style={{ width: 9, height: 9, borderRadius: "50%", background: "#4A4F45" }} />
                <span style={{ width: 9, height: 9, borderRadius: "50%", background: "#4A4F45" }} />
                <span style={{ width: 9, height: 9, borderRadius: "50%", background: "#4A4F45" }} />
                <span className="ml-2.5 text-xs" style={{ color: "#8A8F82" }}>waterloo-electric.vercel.app/sandbox</span>
              </div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/guide/00-hero-holds.png" alt="A live run in Ontario Southwest Zone Sandbox: a 20 MW data centre absorbed, result holds" style={{ width: "100%", display: "block" }} />
            </div>
            <div className="absolute -top-3 -right-3 flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold" style={{ background: INK, border: `1px solid ${TEAL}`, color: TEAL, fontFamily: FD }}>
              <span className="pulse-dot" style={{ width: 7, height: 7, borderRadius: "50%", background: TEAL, display: "inline-block" }} />
              Live product, real run
            </div>
          </div>
        </div>
      </div>

      {/* PAPER BODY */}
      <div style={{ background: PAPER, color: INK }} className="rounded-t-[32px]">

        {/* THE PROBLEM */}
        <div id="problem" className="mx-auto max-w-6xl px-6 py-16 sm:py-20 scroll-mt-16">
          <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">The national problem</div>
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-4xl max-w-2xl leading-tight">Canada wants to build more. Growth increasingly arrives as electrical load.</h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-4">
            {DRIVERS.map(([h, b, c]) => (
              <div key={h} className="rounded-2xl p-5" style={{ border: `1px solid ${LINE}` }}>
                <span style={{ width: 10, height: 10, borderRadius: 5, background: c, display: "inline-block" }} />
                <div style={{ fontFamily: FD, fontWeight: 700 }} className="mt-3 text-base">{h}</div>
                <div className="mt-1.5 text-sm" style={{ color: MUT, lineHeight: 1.5 }}>{b}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex justify-center">
            <svg width="28" height="40" viewBox="0 0 28 40" fill="none"><path d="M14 2v30M4 24l10 10 10-10" stroke={MUT2} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
          <div className="mt-3 rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center gap-6" style={{ background: INK, color: PAPER }}>
            <div className="flex-1">
              <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-lg">…feeding one rising demand curve into a fixed local capacity limit.</div>
              <p className="mt-2 text-sm" style={{ color: "#C9C2AE", lineHeight: 1.55 }}>
                A traditional interconnection study is slow, static, and answers only one scenario at a time. Meanwhile, flexibility programs are already real money: Ontario&apos;s Peak Perks VPP has over 100,000 enrolled homes today.
              </p>
            </div>
            <div className="shrink-0 rounded-xl p-4 text-center" style={{ background: "rgba(242,167,46,.12)", border: `1px solid ${AMB}` }}>
              <div style={{ fontFamily: FD, fontWeight: 700, color: AMB }} className="text-3xl">100,000+</div>
              <div className="mt-1 text-xs max-w-[9rem]" style={{ color: "#D8D3C4" }}>homes enrolled in Ontario&apos;s Peak Perks VPP</div>
            </div>
          </div>
        </div>
      </div>

      {/* EQUATION — dark */}
      <div className="px-6 py-16 sm:py-20">
        <div className="mx-auto max-w-4xl">
          <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">Why not just batteries</div>
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-4xl leading-tight">Installed DER capacity is not deliverable VPP capacity.</h2>
          <p className="mt-4 max-w-2xl text-base" style={{ color: "#D8D3C4", lineHeight: 1.55 }}>
            Five things multiply — not add — to get from nameplate hardware to what a program can actually call on, in the hour that matters.
          </p>
          <div className="mt-8 rounded-2xl p-6 sm:p-8" style={{ background: PAPER }}>
            <FlexEquation />
          </div>
        </div>
      </div>

      {/* PAPER: LIFECYCLE */}
      <div style={{ background: PAPER, color: INK }} className="rounded-t-[32px]">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">Where CapacityOS fits</div>
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-4xl leading-tight">We are not a capacity map, and we are not a DERMS.</h2>
          <div className="mt-10 grid gap-0 sm:grid-cols-3 rounded-2xl overflow-hidden" style={{ border: `1px solid ${LINE}` }}>
            {LIFECYCLE.map(([h, q, b, c], i) => (
              <div key={h} className="p-6" style={{ borderLeft: i ? `1px solid ${LINE}` : undefined, background: i === 1 ? "rgba(31,158,137,.06)" : undefined }}>
                <div style={{ fontFamily: FD, fontWeight: 700, color: c }} className="text-xs uppercase tracking-wide">{i === 1 ? "CapacityOS" : "Existing tools"}</div>
                <div style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-lg">{h}</div>
                <div className="mt-1 text-sm italic" style={{ color: MUT2 }}>{q}</div>
                <div className="mt-2 text-sm" style={{ color: MUT, lineHeight: 1.5 }}>{b}</div>
              </div>
            ))}
          </div>
          <p className="mt-5 text-sm max-w-2xl" style={{ color: MUT2 }}>
            CapacityOS sits in the design and stress-testing gap between knowing where capacity exists and operating enrolled resources day to day. It doesn&apos;t replace either side.
          </p>
        </div>
      </div>

      {/* PRODUCT REVEAL — dark, dominant */}
      <div className="px-6 py-16 sm:py-24">
        <div className="mx-auto max-w-6xl">
          <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide text-center">The product</div>
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-4xl leading-tight text-center">Every one of these is a real, working part of the sandbox.</h2>
          <div className="mt-10 relative rounded-2xl overflow-hidden shadow-2xl" style={{ border: "1px solid #2C332D" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/guide/05-result.png" alt="Ontario Southwest Zone Sandbox with a 7.3 MW overload, breaking, numbered hotspots over each real feature" style={{ width: "100%", display: "block" }} />
            {HOTSPOTS.map(([n, h, , x, y]) => (
              <div key={n} className="absolute -translate-x-1/2 -translate-y-1/2 group" style={{ left: `${x}%`, top: `${y}%` }}>
                <div style={{ width: 26, height: 26, borderRadius: 13, background: AMB, color: INK, fontFamily: FD, fontWeight: 700, fontSize: 13 }} className="flex items-center justify-center shadow-lg cursor-default">{n}</div>
                <div className="absolute left-1/2 -translate-x-1/2 mt-2 w-44 rounded-lg px-3 py-2 text-xs opacity-0 group-hover:opacity-100 transition pointer-events-none z-10" style={{ background: INK, color: PAPER, border: "1px solid #3A4038" }}>
                  <b style={{ fontFamily: FD }}>{h}</b>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 text-sm text-center" style={{ color: "#9C9787" }}>Hover a number. Every screenshot on this site is from the live product, not a mockup.</p>
        </div>
      </div>

      {/* PAPER: FIX IT */}
      <div style={{ background: PAPER, color: INK }} className="rounded-t-[32px]">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <div style={{ fontFamily: FD, fontWeight: 700, color: CORAL }} className="text-xs uppercase tracking-wide">The differentiator</div>
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-4xl leading-tight max-w-2xl">When it breaks, CapacityOS doesn&apos;t just tell you. It tests what would fix it.</h2>
          <p className="mt-4 max-w-2xl text-base" style={{ color: MUT, lineHeight: 1.55 }}>
            Every option shown is a <b>verified rerun</b> of the real day — never an LLM guess, never an estimate.
          </p>
          <div className="mt-9 grid gap-6 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
            <div className="rounded-2xl overflow-hidden" style={{ border: `1px solid ${LINE}` }}>
              <div className="px-4 py-2 text-xs font-semibold" style={{ background: "rgba(229,83,61,.1)", color: CORAL, fontFamily: FD }}>BEFORE — BREAKS</div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/guide/05-result.png" alt="Before: breaks, 0.0 of 7.3 MW absorbed" style={{ width: "100%", display: "block" }} />
            </div>
            <div className="flex justify-center">
              <svg className="rotate-90 sm:rotate-0" width="34" height="24" viewBox="0 0 34 24" fill="none"><path d="M2 12h28M22 2l10 10-10 10" stroke={MUT2} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </div>
            <div className="rounded-2xl overflow-hidden" style={{ border: `1px solid ${TEAL}` }}>
              <div className="px-4 py-2 text-xs font-semibold" style={{ background: "rgba(31,158,137,.12)", color: TEAL, fontFamily: FD }}>APPLY → RERUN → VERIFIED</div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/guide/07-fixit.png" alt="Fix It: two verified pathways, incentive change or capacity increase" style={{ width: "100%", display: "block" }} />
            </div>
          </div>
        </div>
      </div>

      {/* TRUST ARCHITECTURE — dark */}
      <div className="px-6 py-16 sm:py-20">
        <div className="mx-auto max-w-5xl">
          <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide text-center">Trust architecture</div>
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-xl sm:text-3xl text-center">AI proposes. Physics constrains. Optimization dispatches.</h2>
          <div className="mt-10 grid gap-3 sm:grid-cols-4 items-stretch">
            {[
              ["Owner agents", "LLM", "Model willingness and price. Offer, decline, or revise.", AMB],
              ["Physical validator", "Deterministic", "Enforce battery SOC, EV deadlines, building comfort — every offer, checked.", TEAL],
              ["OR-Tools optimizer", "Deterministic", "Decide the actual dispatch from what survived validation.", BLUE],
              ["Result", "Derived", "Holds, partly holds, or breaks — traceable to every step above.", CORAL],
            ].map(([h, tag, b, c]) => (
              <div key={h as string} className="rounded-xl p-4 relative" style={{ background: "#141814", border: `1px solid ${c}` }}>
                <div style={{ fontFamily: FD, fontWeight: 700, fontSize: 10, color: c }} className="uppercase tracking-wide">{tag}</div>
                <div style={{ fontFamily: FD, fontWeight: 700 }} className="mt-1 text-sm">{h}</div>
                <div className="mt-1.5 text-xs" style={{ color: "#B8B3A3", lineHeight: 1.45 }}>{b}</div>
              </div>
            ))}
          </div>
          <p className="mt-6 text-sm text-center max-w-2xl mx-auto" style={{ color: "#9C9787" }}>
            Bulk searches — Fix It, the season comparison — use the deterministic owner policy instead of live LLM calls. Repeated real calls would be slower and non-reproducible; a search needs the same conditions every time.
          </p>
        </div>
      </div>

      {/* PAPER: PROVENANCE */}
      <div style={{ background: PAPER, color: INK }} className="rounded-t-[32px]">
        <div className="mx-auto max-w-5xl px-6 py-16 sm:py-20">
          <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">What&apos;s real, what&apos;s modeled</div>
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-4xl leading-tight">Ontario Southwest Zone Sandbox is not a digital twin. That&apos;s a feature of the brand, not an apology.</h2>
          <div className="mt-8 overflow-hidden rounded-2xl" style={{ border: `1px solid ${LINE}` }}>
            {PROVENANCE.map(([k, v, c], i) => (
              <div key={k} className="flex items-start gap-4 px-5 py-4 text-sm" style={{ borderTop: i ? `1px solid ${LINE}` : undefined }}>
                <span className="shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold" style={{ background: c, color: "#fff", fontFamily: FD, minWidth: 92, textAlign: "center" }}>{k}</span>
                <span style={{ color: MUT }}>{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* PILOT PATHWAY — dark */}
      <div className="px-6 py-16 sm:py-20">
        <div className="mx-auto max-w-5xl">
          <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">What happens after the hackathon</div>
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-4xl leading-tight">The simulator doesn&apos;t change. Its inputs do.</h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {PILOT.map(([h, tag, b], i) => (
              <div key={h} className="rounded-2xl p-5" style={{ background: i === 0 ? "rgba(242,167,46,.1)" : "#141814", border: `1px solid ${i === 0 ? AMB : "#2C332D"}` }}>
                <div style={{ fontFamily: FD, fontWeight: 700, color: i === 0 ? AMB : "#9C9787" }} className="text-xs uppercase tracking-wide">{tag}</div>
                <div style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-lg">{h}</div>
                <div className="mt-2 text-sm" style={{ color: "#C9C2AE", lineHeight: 1.5 }}>{b}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* PAPER: WHO USES IT */}
      <div style={{ background: PAPER, color: INK }} className="rounded-t-[32px]">
        <div className="mx-auto max-w-5xl px-6 py-16 sm:py-20">
          <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">Who uses it, and the decision it answers</div>
          <h2 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-2 text-2xl sm:text-4xl leading-tight">Not a persona. A question they need answered.</h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {DECISIONS.map(([who, q]) => (
              <div key={who} className="rounded-2xl p-5" style={{ border: `1px solid ${LINE}` }}>
                <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-sm">{who} asks:</div>
                <div style={{ fontFamily: FD, fontWeight: 700 }} className="mt-1.5 text-lg leading-snug">{q}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* LIMITATIONS + CTA — dark */}
      <div className="px-6 py-16 sm:py-20">
        <div className="mx-auto max-w-3xl">
          <div style={{ fontFamily: FD, fontWeight: 700, color: "#9C9787" }} className="text-xs uppercase tracking-wide">Before you launch it, three limits</div>
          <ul className="mt-4 flex flex-col gap-2.5">
            {LIMITATIONS.map((l) => (
              <li key={l} className="flex gap-2.5 text-sm sm:text-base" style={{ color: "#D8D3C4", lineHeight: 1.5 }}>
                <span style={{ color: CORAL, flexShrink: 0 }}>●</span>{l}
              </li>
            ))}
          </ul>
          <div className="mt-10 rounded-2xl p-7 sm:p-9 text-center" style={{ background: "#141814", border: "1px solid #2C332D" }}>
            <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-2xl sm:text-3xl">Break a VPP before somebody deploys it.</div>
            <Link href="/sandbox" style={{ background: AMB, color: INK }} className="mt-6 inline-block rounded-full px-8 py-3.5 text-base font-semibold hover:opacity-90 transition">
              Launch Ontario Southwest Zone Sandbox →
            </Link>
          </div>
        </div>
      </div>

      {/* FOOTER */}
      <div style={{ background: PAPER, color: INK }} className="rounded-t-[32px]">
        <div className="mx-auto max-w-6xl px-6 py-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs" style={{ color: MUT2 }}>
          <div className="flex items-center gap-2">
            <span style={{ width: 8, height: 8, borderRadius: 3, background: AMB, display: "inline-block" }} />
            Built for AF Hacks: Growing Canada. A planning simulation, not a forecast or a utility-grade engineering study.
          </div>
          <div>
            <span style={{ color: CORAL }}>●</span> hypothetical · <span style={{ color: AMB }}>●</span> modeled · <span style={{ color: TEAL }}>●</span> derived · <span style={{ color: "#2E6E3E" }}>●</span> observed
          </div>
        </div>
      </div>
    </main>
  );
}
