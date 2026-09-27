// Generates the 4 cinematic opening clips via the Runway API (text_to_video) and downloads them.
// Run: node scripts/gen_cinematics.mjs   (needs RUNWAY_API_KEY in ../../.env)
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, "out", "cinematic");
mkdirSync(OUT_DIR, { recursive: true });

// load RUNWAY_API_KEY from ../../.env without printing it anywhere
const envText = readFileSync(join(__dirname, "..", "..", "..", ".env"), "utf8");
const m = envText.match(/^RUNWAY_API_KEY=(.+)$/m);
if (!m) throw new Error("RUNWAY_API_KEY not found in .env");
const KEY = m[1].trim();

const BASE = "https://api.dev.runwayml.com";
const VERSION = "2024-11-06";

const SHOTS = [
  ["03_buses", "Static wide shot of electric buses parked at a charging depot at dusk, charging cables connected, soft ambient lighting, subtle steam in the air, cinematic color grade matching warm amber and cool teal tones, photorealistic"],
  ["04_industrial", "Slow cinematic pan across a modern industrial manufacturing facility exterior, clean architecture, overcast neutral light, subtle sense of scale and productivity, muted color grade, photorealistic"],
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

async function submit(promptText) {
  return req("/v1/text_to_video", {
    method: "POST",
    body: JSON.stringify({ model: "gen4.5", promptText, ratio: "1280:720", duration: 6 }),
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

const run = async () => {
  for (const [label, prompt] of SHOTS) {
    console.log(`\n=== ${label} ===`);
    const created = await submit(prompt);
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
};

run().catch((e) => { console.error(e); process.exit(1); });
