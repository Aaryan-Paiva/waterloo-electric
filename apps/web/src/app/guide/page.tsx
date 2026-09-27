import Link from "next/link";

const PAPER = "#FBF7EE", INK = "#1D2320", LINE = "#D9D1BE", AMB = "#F2A72E", TEAL = "#1F9E89", CORAL = "#E5533D";
const FD = "var(--font-display), 'Bricolage Grotesque', system-ui, sans-serif";
const MUT = "#4A4F45", MUT2 = "#8A8F82";

type Box = [number, number, number, number]; // left%, top%, width%, height% — over a 1440x900 real screenshot
type Step = [string, string, string, string, Box?];

const STEPS: Step[] = [
  ["1", "Choose a condition", "Pick the season and hour — or Play the day. Every world starts from a real historical Waterloo-zone demand day, not a forecast.", "/guide/01-world.png", [61, 87.5, 38, 11.5]],
  ["2", "Add new demand", "Drag a data centre, housing development, or EV depot from the tray into an empty lot. Up to four loads at once.", "/guide/02-tray.png"],
  ["3", "Configure the VPP", "These are the rules of the program you're testing: owner enrolment, incentive, battery reserve, EV flexibility, building comfort.", "/guide/04-editor.png", [77, 1, 22, 97]],
  ["4", "Run the event", "CapacityOS builds a flexibility request and asks the modeled owners for help — the world starts responding immediately.", "/guide/03-load-placed.png"],
  ["5", "Watch the owners respond", "18 owner agents each decide independently: offer, decline, or revise. Every decision — with the owner's own explanation — is in the Log.", "/guide/06-log.png", [77, 1, 22, 30]],
  ["6", "Physics checks, then optimization", "Every offer is checked against real device limits before it counts. Only what survives reaches OR-Tools, which picks the actual dispatch.", "/guide/06-log.png", [77, 32, 22, 68]],
  ["7", "Read the result", "Holds, partly holds, or breaks — with the exact overload, MW absorbed, residual, and which resource type did the work.", "/guide/05-result.png", [77, 1, 22, 32]],
  ["8", "Use Fix It", "If it breaks: two pathways, tightening the program or adding zone capacity, each proven by rerunning the real day.", "/guide/07-fixit.png", [77, 1, 22, 62]],
  ["9", "Compare seasons", "The same VPP design, tested against all four seasons' real worst day. A design that holds in summer can still fail in winter.", "/guide/08-seasons.png", [77, 1, 22, 97]],
];

function StepBlock([n, h, b, img, box]: Step, reverse: boolean) {
  return (
    <div className={`grid gap-6 sm:grid-cols-2 items-center py-12 ${reverse ? "" : ""}`}>
      <div className={reverse ? "sm:order-2" : ""}>
        <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">Step {n}</div>
        <h3 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-1.5 text-xl sm:text-2xl">{h}</h3>
        <p className="mt-2.5 text-sm sm:text-base" style={{ color: MUT, lineHeight: 1.55 }}>{b}</p>
      </div>
      <div className={reverse ? "sm:order-1" : ""}>
        <div className="relative rounded-xl overflow-hidden" style={{ border: `1px solid ${LINE}` }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={img} alt={h} style={{ width: "100%", display: "block" }} />
          {box && (
            <div
              className="absolute rounded-md pointer-events-none"
              style={{ left: `${box[0]}%`, top: `${box[1]}%`, width: `${box[2]}%`, height: `${box[3]}%`, border: `2.5px solid ${AMB}`, boxShadow: "0 0 0 4000px rgba(20,24,20,.35)" }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default function Guide() {
  return (
    <main style={{ background: PAPER, color: INK, fontFamily: "var(--font-body), 'IBM Plex Sans', system-ui, sans-serif" }}>
      <div className="mx-auto max-w-5xl px-6 py-16 sm:py-20">
        <div className="flex items-center gap-2 text-sm" style={{ color: MUT2 }}>
          <span style={{ width: 10, height: 10, borderRadius: 3, background: AMB, display: "inline-block" }} />
          Guide
        </div>
        <h1 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-4 text-3xl sm:text-5xl leading-[1.08]">
          How to use CapacityOS
        </h1>
        <p className="mt-5 max-w-2xl text-lg" style={{ color: MUT, lineHeight: 1.55 }}>
          Nine steps, real screenshots, under a minute to actually operate the sandbox. Every image below is a live capture of the deployed product.
        </p>

        {/* legend */}
        <div className="mt-8 flex flex-wrap gap-x-8 gap-y-3 rounded-2xl p-5" style={{ border: `1px solid ${LINE}`, background: "rgba(29,35,32,.02)" }}>
          <div>
            <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-xs uppercase tracking-wide" >Result colours</div>
            <div className="mt-2 flex gap-4 text-sm">
              <span className="flex items-center gap-1.5"><span style={{ width: 9, height: 9, borderRadius: 5, background: TEAL, display: "inline-block" }} />Holds</span>
              <span className="flex items-center gap-1.5"><span style={{ width: 9, height: 9, borderRadius: 5, background: AMB, display: "inline-block" }} />Partly holds</span>
              <span className="flex items-center gap-1.5"><span style={{ width: 9, height: 9, borderRadius: 5, background: CORAL, display: "inline-block" }} />Breaks</span>
            </div>
          </div>
          <div>
            <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-xs uppercase tracking-wide">Provenance</div>
            <div className="mt-2 flex gap-4 text-sm" style={{ color: MUT }}>
              <span>Derived = from public historical data</span>
              <span>Modeled = synthetic assumption</span>
              <span>Hypothetical = a load you added</span>
            </div>
          </div>
        </div>

        {/* steps */}
        <div className="mt-4 divide-y" style={{ borderColor: LINE }}>
          {STEPS.map((s, i) => <div key={s[0]} style={{ borderTop: i ? `1px solid ${LINE}` : undefined }}>{StepBlock(s, i % 2 === 1)}</div>)}
        </div>

        {/* step 10: reset */}
        <div className="py-12" style={{ borderTop: `1px solid ${LINE}` }}>
          <div className="grid gap-6 sm:grid-cols-2 items-center">
            <div>
              <div style={{ fontFamily: FD, fontWeight: 700, color: TEAL }} className="text-xs uppercase tracking-wide">Step 10</div>
              <h3 style={{ fontFamily: FD, fontWeight: 700 }} className="mt-1.5 text-xl sm:text-2xl">Reset and experiment again</h3>
              <p className="mt-2.5 text-sm sm:text-base" style={{ color: MUT, lineHeight: 1.55 }}>
                The circular arrow next to the &quot;?&quot; in the top-left card clears everything — loads, VPP rules, history — back to a clean world. Nothing is ever permanent.
              </p>
            </div>
            <div className="relative rounded-xl overflow-hidden" style={{ border: `1px solid ${LINE}` }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/guide/01-world.png" alt="Reset control, top-left brand card" style={{ width: "100%", display: "block" }} />
              <div className="absolute rounded-full pointer-events-none" style={{ left: "20.5%", top: "6%", width: "5.5%", height: "9%", border: `2.5px solid ${AMB}`, boxShadow: "0 0 0 4000px rgba(20,24,20,.35)" }} />
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="mt-6 rounded-2xl p-7 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4" style={{ background: INK, color: PAPER }}>
          <div style={{ fontFamily: FD, fontWeight: 700 }} className="text-xl">Ready?</div>
          <Link href="/sandbox" style={{ background: AMB, color: INK }} className="rounded-full px-7 py-3 text-base font-semibold hover:opacity-90 transition whitespace-nowrap">
            Launch the sandbox →
          </Link>
        </div>
      </div>
    </main>
  );
}
