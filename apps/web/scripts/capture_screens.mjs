// Regenerable real-product screenshots for the homepage hero and the Guide page.
// Run with the dev server up: node scripts/capture_screens.mjs
// Requires playwright (devDependency) + chromium installed (npx playwright install chromium).
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, "..", "public", "guide");
mkdirSync(OUT, { recursive: true });
const BASE = process.env.CAPTURE_BASE_URL || "http://localhost:3000";

// Stage is a fixed 1440x900 logical canvas scaled to fit; pin the viewport so scale === 1,
// which makes iso-world pixel math (below) exact.
const VIEWPORT = { width: 1440, height: 980 };
const NAV_H = 44;

// Mirrors apps/web/src/components/iso/scene.ts's P()/LOTS so we can click real drop targets.
const TW = 64, TH = 32, OX = 720, OY = 246;
const LOTS = [{ x: 7.4, y: 9.4 }, { x: 10, y: 9.4 }, { x: 7.4, y: 11.4 }, { x: 10, y: 11.4 }];
const P = (x, y) => [OX + ((x - y) * TW) / 2, OY + ((x + y) * TH) / 2];
const lotCenterPage = (i) => { const l = LOTS[i]; const [x, y] = P(l.x + 1, l.y + 1); return { x, y: y + NAV_H }; };

async function dragLoad(page, label, lotIndex) {
  const card = page.locator(`text=${label}`).first();
  const box = await card.boundingBox();
  const target = lotCenterPage(lotIndex);
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(target.x, target.y, { steps: 12 });
  await page.mouse.move(target.x, target.y, { steps: 2 });
  await page.mouse.up();
}

async function shot(page, name, clip) {
  await page.screenshot({ path: join(OUT, `${name}.png`), clip });
  console.log("saved", name);
}

const run = async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: VIEWPORT });
  await page.addInitScript(() => localStorage.setItem("we-seen-help", "1"));

  // 1. clean world, no loads — season/time controls visible (Guide step 1; also hero background)
  await page.goto(`${BASE}/sandbox`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=device clusters are following their routines", { timeout: 20000 });
  await page.waitForTimeout(400);
  await shot(page, "01-world", { x: 0, y: NAV_H, width: 1440, height: 900 });

  // 2. drag a data centre onto a lot (tray + drop target both visible before drop)
  const dcCard = page.locator("text=Data centre").first();
  const dcBox = await dcCard.boundingBox();
  await shot(page, "02-tray", { x: Math.max(0, dcBox.x - 40), y: Math.max(NAV_H, dcBox.y - 40), width: 420, height: 260 });

  await dragLoad(page, "Data centre", 0);
  await page.waitForTimeout(600);
  await shot(page, "03-load-placed", { x: 0, y: NAV_H, width: 1440, height: 900 });

  // wait for the run to actually resolve (owners decide -> validator -> optimizer -> result),
  // then for the step-by-step playback narration to finish (tabs only render once finished)
  await page.waitForSelector('[role="tab"]', { timeout: 90000 }).catch((e) => console.log("no tabs appeared:", e.message));
  await page.waitForTimeout(500);

  // hero shot: single 20 MW data centre, holds — the "problem -> response -> resolved" story in one frame
  await shot(page, "00-hero-holds", { x: 0, y: NAV_H, width: 1440, height: 900 });

  // now push it into a genuine overload (adds housing) so the rest of the walkthrough — editor, log,
  // Fix It, seasons — has something real to show and fix
  await dragLoad(page, "Housing", 1);
  await page.waitForTimeout(600);
  await page.waitForSelector('[role="tab"]', { timeout: 90000 }).catch((e) => console.log("no tabs appeared (2):", e.message));
  await page.waitForTimeout(500);

  // 4. result tab
  await shot(page, "05-result", { x: 0, y: NAV_H, width: 1440, height: 900 });

  // 3. open the device editor from the result panel (VPP rules: enrolment, incentive, battery reserve, EV flex, building comfort)
  await page.getByRole("button", { name: "Edit the devices" }).click();
  await page.waitForTimeout(300);
  await shot(page, "04-editor", { x: 0, y: NAV_H, width: 1440, height: 900 });
  await page.getByRole("button", { name: "Close editor" }).click();
  await page.waitForTimeout(300);

  // 5. log tab (owner responses, physics, optimizer)
  const allTabs = await page.getByRole("tab").allTextContents();
  console.log("tabs found:", allTabs);
  const logTab = page.getByRole("tab", { name: /^Log$/ }).first();
  if (await logTab.count()) { await logTab.click(); await page.waitForTimeout(300); await shot(page, "06-log", { x: 0, y: NAV_H, width: 1440, height: 900 }); }

  // 6. Fix it tab
  const fixTab = page.getByRole("tab", { name: /Fix it/i }).first();
  if (await fixTab.count()) {
    await fixTab.click();
    await page.waitForSelector("text=Searching and rerunning", { state: "detached", timeout: 120000 }).catch((e) => console.log("fix-it still searching:", e.message));
    await page.waitForTimeout(500);
    await shot(page, "07-fixit", { x: 0, y: NAV_H, width: 1440, height: 900 });
  }

  // 7. seasons tab
  const seasonsTab = page.getByRole("tab", { name: /Seasons/i }).first();
  if (await seasonsTab.count()) {
    await seasonsTab.click();
    await page.waitForTimeout(2500);
    await shot(page, "08-seasons", { x: 0, y: NAV_H, width: 1440, height: 900 });
  }

  await browser.close();
};

run().catch((e) => { console.error(e); process.exit(1); });
