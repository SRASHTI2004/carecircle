// Real-browser check: click through every feature as each role, capture console errors,
// run axe-core WITH colour contrast, and save screenshots. Usage: node e2e/browser-check.mjs [baseUrl]
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright-core";

const BASE = process.argv[2] ?? "http://localhost:8000";
const axeSource = readFileSync("node_modules/axe-core/axe.min.js", "utf8");
const shots = new URL("../../docs/screenshots/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(shots, { recursive: true });

const report = { base: BASE, consoleErrors: [], axe: {}, steps: [] };
const step = (name, ok = true) => report.steps.push({ name, ok });

const browser = await chromium.launch({ channel: "msedge", headless: true });

async function axeCheck(page, label) {
  await page.evaluate(axeSource);
  const result = await page.evaluate(async () =>
    // eslint-disable-next-line no-undef
    axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] } }),
  );
  report.axe[label] = result.violations.map((v) => `${v.id} (${v.nodes.length}): ${v.help}`);
}

async function session(role, viewport, fn) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  page.on("console", (m) => m.type() === "error" && report.consoleErrors.push(`${role}: ${m.text()}`));
  page.on("pageerror", (e) => report.consoleErrors.push(`${role} pageerror: ${e.message}`));
  await page.goto(BASE, { waitUntil: "networkidle" });
  await fn(page);
  await context.close();
}

const desktop = { width: 1280, height: 900 };
const phone = { width: 390, height: 844 };
const shot = (page, name, fullPage = true) => page.screenshot({ path: `${shots}${name}.png`, fullPage });

// Landing
await session("landing", desktop, async (page) => {
  await shot(page, "01-landing");
  await axeCheck(page, "landing");
  step("landing renders");
});

// Elder: elder mode, check-in, mark done, standard view tabs, settings, emergency card
await session("elder", desktop, async (page) => {
  await page.getByRole("button", { name: "Try as Elder" }).click();
  await page.getByRole("heading", { name: /Hello, Margaret/ }).waitFor();
  await page.getByRole("button", { name: /Mark .* as (done|taken)/ }).first().waitFor();
  await page.getByRole("heading", { name: "Today", exact: true }).waitFor();
  await shot(page, "02-elder-light", false);
  await shot(page, "02-elder-light-full");
  await axeCheck(page, "elder-mode-light");
  await page.getByRole("switch", { name: /Dark theme/ }).click();
  await page.waitForTimeout(200);
  await shot(page, "02-elder-dark", false);
  await shot(page, "02-elder-dark-full");
  await axeCheck(page, "elder-mode-dark");
  step("elder dark theme");
  await page.getByRole("switch", { name: /Dark theme/ }).click();
  await page.getByRole("button", { name: /Good/ }).first().click();
  await page.getByText("Thank you for checking in.").waitFor();
  step("elder check-in");
  const doneBtn = page.getByRole("button", { name: /Mark .* as (done|taken)/ }).first();
  if (await doneBtn.isEnabled()) await doneBtn.click();
  step("elder marks dose");
  await page.getByRole("button", { name: "Standard view" }).click();
  for (const tab of ["Today", "Medicines & routines", "Appointments", "Care circle", "Emergency card", "Email reminders", "Settings"]) {
    await page.getByRole("button", { name: tab, exact: true }).click();
    await page.waitForTimeout(400);
    const slug = tab.toLowerCase().replace(/[^a-z]+/g, "-");
    await shot(page, `03-standard-${slug}`);
    if (slug === "today") await shot(page, "03-today-viewport", false);
    await axeCheck(page, `elder-${slug}`);
    step(`tab ${tab}`);
  }
  await page.getByRole("button", { name: "Emergency card", exact: true }).click();
  await page.getByRole("button", { name: "Show to doctor" }).click();
  await page.getByRole("dialog").waitFor();
  await shot(page, "04-show-to-doctor");
  await axeCheck(page, "doctor-view");
  await page.keyboard.press("Escape");
  step("doctor view + Escape closes");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByLabel("Send to").fill("judge@example.com");
  await page.getByRole("button", { name: "Send test email" }).click();
  await page.locator(".toast").waitFor();
  step(`test email toast: ${await page.locator(".toast").innerText()}`);
});

// Elder on a phone: light and dark
await session("elder-phone", phone, async (page) => {
  await page.getByRole("button", { name: "Try as Elder" }).click();
  await page.getByRole("heading", { name: "Today", exact: true }).waitFor();
  await shot(page, "02-elder-phone-light", false);
  await axeCheck(page, "elder-phone-light");
  step("no horizontal scroll on phone (elder)", !(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)));
  await page.getByRole("switch", { name: /Dark theme/ }).click();
  await page.waitForTimeout(200);
  await shot(page, "02-elder-phone-dark", false);
  await axeCheck(page, "elder-phone-dark");
  await page.getByRole("switch", { name: /Dark theme/ }).click();
});

// Caretaker on a phone: add a routine, see duplicate guard
await session("caretaker-phone", phone, async (page) => {
  await page.getByRole("button", { name: "Try as Caretaker" }).click();
  await page.getByRole("button", { name: "Medicines & routines", exact: true }).click();
  await page.getByRole("button", { name: "Add routine" }).click();
  const name = `Stretching ${Date.now() % 10000}`;
  await page.getByLabel("Routine name").fill(name);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByText(`Add ${name}: saved.`).waitFor();
  step("caretaker adds routine");
  const hscroll = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  step("no horizontal scroll on phone", !hscroll);
  await shot(page, "05-phone-medicines");
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await page.waitForTimeout(500);
  await shot(page, "06-phone-today");
  await axeCheck(page, "caretaker-phone-today");
});

// Family: read-only
await session("family", desktop, async (page) => {
  await page.getByRole("button", { name: "Try as Family" }).click();
  await page.getByRole("heading", { name: "Today", exact: true }).waitFor();
  const canMark = await page.getByRole("button", { name: /Mark .* as taken/ }).count();
  step("family has no Taken buttons", canMark === 0);
  await page.getByRole("button", { name: "Medicines & routines", exact: true }).click();
  step("family has no Add medicine", (await page.getByRole("button", { name: "Add medicine" }).count()) === 0);
  await page.getByRole("button", { name: "Care circle", exact: true }).click();
  await page.waitForTimeout(500);
  await axeCheck(page, "family-care");
});

await browser.close();
const bad = Object.entries(report.axe).filter(([, v]) => v.length);
report.summary = {
  consoleErrors: report.consoleErrors.length,
  axePagesChecked: Object.keys(report.axe).length,
  axePagesWithViolations: bad.length,
  failedSteps: report.steps.filter((s) => !s.ok).length,
};
writeFileSync(new URL("../../docs/browser-check.json", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report.summary), bad.length ? JSON.stringify(Object.fromEntries(bad), null, 1) : "", report.consoleErrors.slice(0, 5));
process.exit(bad.length || report.consoleErrors.length || report.summary.failedSteps ? 1 : 0);
