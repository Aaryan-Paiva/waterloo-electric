// Generates the 6 motion-graphic clips via the Runway API (text_to_video), same pipeline as gen_cinematics.mjs.
// Run: node scripts/gen_motion.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, "out", "motion");
mkdirSync(OUT_DIR, { recursive: true });

const envText = readFileSync(join(__dirname, "..", "..", "..", ".env"), "utf8");
const m = envText.match(/^RUNWAY_API_KEY=(.+)$/m);
if (!m) throw new Error("RUNWAY_API_KEY not found in .env");
const KEY = m[1].trim();

const BASE = "https://api.dev.runwayml.com";
const VERSION = "2024-11-06";

// No hex codes, no requests for on-screen text/words/numbers anywhere in these prompts —
// that's what caused Runway to hallucinate garbled fake text last time. Pure abstract shape
// motion only; any titles/labels get burned in afterward with ffmpeg drawtext.
const PALETTE = "warm cream colored background, dark ink colored accents, amber orange, teal green, coral red, blue, violet purple accent colors, flat 2D minimalist motion graphic illustration, clean geometric shapes, no photorealism, no 3D rendering, no gradients, no drop shadows, no text, no words, no numbers, no letters, no typography, elegant and simple abstract shapes only";

const SHOTS = [
  ["01_demand_capacity",
    `Minimalist 2D flat motion graphic animation, ${PALETTE}. A smooth teal curved line rises steadily from the bottom left toward the upper right like a rising graph line, crossing above a thin dashed horizontal boundary line and turning coral red past the crossing point, calm smooth motion.`, 8],
  ["02_vpp_devices",
    `Minimalist 2D flat motion graphic animation, ${PALETTE}. Three simple rounded-square icon shapes arranged in a horizontal row, colored blue, teal and violet. Each shape pulses briefly with a soft glow in sequence from left to right, smooth and elegant motion.`, 8],
  ["03_lifecycle",
    `Minimalist 2D flat motion graphic animation, ${PALETTE}. Three connected rounded rectangle shapes arranged in a horizontal row, linked by thin animated arrow lines pointing left to right. The middle shape glows warm amber orange while the two outer shapes remain muted light grey.`, 8],
  ["04_title_reveal",
    `Minimalist 2D flat animation, ${PALETTE}. A single small amber orange square shape gently fades in and scales up at the exact center of the frame with a soft warm glow pulse, then holds still. Extremely simple, elegant, minimal motion, nothing else in frame.`, 4],
  ["05_question_overlay",
    `Minimalist 2D flat motion graphic animation, ${PALETTE}. Three small circular dot shapes in teal, amber and coral fade in one at a time from top to bottom on the left side of the frame, each followed by a soft horizontal light streak extending to the right. Generous spacing, calm pacing.`, 6],
  ["06_pilot_pathway",
    `Minimalist 2D flat motion graphic animation, ${PALETTE}. Three connected rounded rectangle shapes arranged in a horizontal row representing a progression, linked by thin animated arrow lines pointing left to right. The shapes light up sequentially from left to right, ending with the final rightmost shape glowing warm amber orange with a soft pulse.`, 8],
];

async function req(path, opts = {}) {
  const r = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { "Authorization": `Bearer ${KEY}`, "X-Runway-Version": VERSION, "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  const text = await r.text();
  let json; try { json = JSON.parse(text); } catch { json = { raw: text }; }
  if (!r.ok) { throw new Error(`${path} -> ${r.status}: ${JSON.stringify(json)}`); }
  return json;
}

async function submit(promptText, duration) {
  return req("/v1/text_to_video", {
    method: "POST",
    body: JSON.stringify({ model: "gen4.5", promptText, ratio: "1280:720", duration }),
  });
}

async function pollUntilDone(id, label) {
  for (let i = 0; i < 60; i++) {
    const t = await req(`/v1/tasks/${id}`);
    console.log(`[${label}] status=${t.status} (${i + 1}/60)`);
    if (t.status === "SUCCEEDED") return t;
    if (t.status === "FAILED") throw new Error(`${label} failed: ${JSON.stringify(t)}`);
    await new Promise((r) => setTimeout(r, 5000));
  }
  throw new Error(`${label} timed out waiting`);
}

const failed = [];

async function attemptOne(label, prompt, duration, retriesLeft) {
  console.log(`\n=== ${label} (${duration}s), ${retriesLeft} retries left ===`);
  const created = await submit(prompt, duration);
  console.log("task id:", created.id);
  const done = await pollUntilDone(created.id, label);
  const url = done.output?.[0];
  if (!url) throw new Error(`${label}: no output url in ${JSON.stringify(done)}`);
  const resp = await fetch(url);
  const buf = Buffer.from(await resp.arrayBuffer());
  const outPath = join(OUT_DIR, `${label}.mp4`);
  writeFileSync(outPath, buf);
  console.log("saved", outPath, `(${(buf.length / 1024 / 1024).toFixed(1)} MB)`);
}

const run = async () => {
  for (const [label, prompt, duration] of SHOTS) {
    let ok = false;
    for (let attempt = 0; attempt < 2 && !ok; attempt++) {
      try {
        await attemptOne(label, prompt, duration, 1 - attempt);
        ok = true;
      } catch (e) {
        console.log(`${label} attempt ${attempt + 1} failed:`, e.message);
        if (attempt === 1) failed.push(label);
      }
    }
  }
  if (failed.length) console.log("\nFAILED after retry:", failed.join(", "));
  else console.log("\nAll clips succeeded.");
};

run().catch((e) => { console.error(e); process.exit(1); });
