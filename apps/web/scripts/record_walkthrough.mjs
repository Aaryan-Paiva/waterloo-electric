// Part 3 — the real feature walkthrough, recorded against the verified canonical scenario:
// data centre 20MW + housing 1000 homes, summer 2pm, $130/MWh -> partly holds, 6.2/7.3 MW absorbed.
// Run: RECORD_BASE_URL=http://localhost:3000 node scripts/record_walkthrough.mjs
import { chromium } from "playwright";
import { mkdirSync, renameSync, readdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import os from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, "out");
mkdirSync(OUT_DIR, { recursive: true });
const BASE = process.env.RECORD_BASE_URL || "http://localhost:3000";

const VW = 1440, VH = 960, NAV_H = 44;
const TW = 64, TH = 32, OX = 720, OY = 246;
const LOTS = [{ x: 7.4, y: 9.4 }, { x: 10, y: 9.4 }, { x: 7.4, y: 11.4 }, { x: 10, y: 11.4 }];
const P = (x, y) => [OX + ((x - y) * TW) / 2, OY + ((x + y) * TH) / 2];
const lotCenterPage = (i) => { const l = LOTS[i]; const [x, y] = P(l.x + 1, l.y + 1); return { x, y: y + NAV_H }; };

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function dragLoad(page, label, lotIndex) {
  const card = page.locator(`text=${label}`).first();
  const box = await card.boundingBox();
  const target = lotCenterPage(lotIndex);
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(target.x, target.y, { steps: 20 });
  await wait(150);
  await page.mouse.move(target.x, target.y, { steps: 4 });
  await page.mouse.up();
}

async function setRange(page, ariaLabel, value) {
  const el = page.locator(`input[aria-label="${ariaLabel}"]`);
  await el.evaluate((node, v) => {
    const proto = Object.getPrototypeOf(node);
    const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    setter.call(node, String(v));
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

const run = async () => {
  const tmpVideoDir = join(os.tmpdir(), `walkthrough-${Date.now()}`);
  mkdirSync(tmpVideoDir, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: VW, height: VH },
    recordVideo: { dir: tmpVideoDir, size: { width: VW, height: VH } },
  });
  const page = await context.newPage();
  await page.addInitScript(() => localStorage.setItem("we-seen-help", "1"));

  // Playwright's headless browser renders no OS cursor at all — inject a visible one so
  // clicks and drags are actually followable in the recorded video.
  await page.addInitScript(() => {
    const cursor = document.createElement("div");
    cursor.style.cssText = "position:fixed;top:0;left:0;width:22px;height:22px;border-radius:50%;background:rgba(29,35,32,.55);border:2.5px solid #FBF7EE;box-shadow:0 1px 4px rgba(0,0,0,.4);pointer-events:none;z-index:2147483647;transform:translate(-50%,-50%);transition:width .1s,height .1s;";
    const mount = () => document.body && document.body.appendChild(cursor);
    if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
    window.addEventListener("mousemove", (e) => { cursor.style.left = e.clientX + "px"; cursor.style.top = e.clientY + "px"; }, true);
    window.addEventListener("mousedown", () => { cursor.style.width = "14px"; cursor.style.height = "14px"; cursor.style.background = "rgba(242,167,46,.85)"; }, true);
    window.addEventListener("mouseup", () => { cursor.style.width = "22px"; cursor.style.height = "22px"; cursor.style.background = "rgba(29,35,32,.55)"; }, true);
  });

  // 1. establish the world, hold on provenance badges
  await page.goto(`${BASE}/sandbox`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=device clusters are following their routines", { timeout: 20000 }).catch(() => {});
  await page.mouse.move(200, 250, { steps: 15 });
  await wait(5000);

  // 2. configure the VPP: open editor, set incentive to $130, pause on other sliders
  await page.getByRole("button", { name: "Edit the devices" }).click();
  await wait(1500);
  await setRange(page, "Incentive offered", 130);
  await wait(2500);
  await wait(1500); // hold on battery reserve / EV flex / building comfort area (already visible while scrolled)
  await page.mouse.wheel(0, 200);
  await wait(2500);
  await page.getByRole("button", { name: "Close editor" }).click();
  await wait(1000);

  // 3. add growth: data centre then housing
  await dragLoad(page, "Data centre", 0);
  await wait(2000); // hold on the pending overload before housing goes in too
  await dragLoad(page, "Housing", 1);

  // 4. wait for the real run (18 real OpenAI owner calls) to resolve and playback to finish
  await page.waitForSelector('[role="tab"]', { timeout: 90000 }).catch(() => {});
  await wait(2000);

  // 5. result tab: hold on the real "partly holds" outcome
  const resultTab = page.getByRole("tab", { name: /^Result$/ }).first();
  if (await resultTab.count()) { await resultTab.click(); await wait(7000); }

  // 6. log tab: hold on the owner list (the real rejection+revision pair is in here)
  const logTab = page.getByRole("tab", { name: /^Log$/ }).first();
  if (await logTab.count()) {
    await logTab.click();
    await wait(3000);
    await page.mouse.wheel(0, 300);
    await wait(3000);
    await page.mouse.wheel(0, 300);
    await wait(4000);
  }

  // 7. Fix it tab: wait for the real search, hold on both pathways
  const fixTab = page.getByRole("tab", { name: /Fix it/i }).first();
  if (await fixTab.count()) {
    await fixTab.click();
    await page.waitForSelector("text=Searching and rerunning", { state: "detached", timeout: 90000 }).catch(() => {});
    await wait(4000);
    await page.mouse.wheel(0, 250);
    await wait(5000);
  }

  // 8. seasons tab
  const seasonsTab = page.getByRole("tab", { name: /Seasons/i }).first();
  if (await seasonsTab.count()) { await seasonsTab.click(); await wait(6000); }

  // 9. history tab
  const historyTab = page.getByRole("tab", { name: /Runs/i }).first();
  if (await historyTab.count()) { await historyTab.click(); await wait(3000); }

  // 10. guide / tour overlay, briefly
  const helpBtn = page.getByRole("button", { name: "60-second tour" }).first();
  if (await helpBtn.count()) {
    await helpBtn.click();
    await wait(3500);
    const closeBtn = page.getByRole("button", { name: "Skip" }).first();
    if (await closeBtn.count()) await closeBtn.click();
    await wait(500);
  }

  // 11. reset — hold on the cleared world (provenance legend close)
  const resetBtn = page.getByRole("button", { name: "Reset the whole world" }).first();
  if (await resetBtn.count()) { await resetBtn.click(); await wait(6000); }

  await context.close();
  await browser.close();

  const files = readdirSync(tmpVideoDir).filter((f) => f.endsWith(".webm"));
  if (files.length === 0) throw new Error("no video file produced");
  const webmOut = join(OUT_DIR, "walkthrough.webm");
  renameSync(join(tmpVideoDir, files[0]), webmOut);
  console.log("saved", webmOut);

  let ffmpeg = null;
  try { ffmpeg = execFileSync("which", ["ffmpeg"], { encoding: "utf8" }).trim() || null; } catch { /* not on PATH */ }
  if (!ffmpeg) { for (const p of ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]) { try { execFileSync(p, ["-version"]); ffmpeg = p; break; } catch { /* next */ } } }
  if (ffmpeg) {
    const mp4Out = join(OUT_DIR, "walkthrough.mp4");
    execFileSync(ffmpeg, ["-y", "-i", webmOut, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-crf", "20", mp4Out]);
    console.log("saved", mp4Out);
  }
};

run().catch((e) => { console.error(e); process.exit(1); });
