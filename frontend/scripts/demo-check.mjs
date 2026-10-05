// Demo browser check (demo mission, 2026-10-04): log in to the DEMO instance, open a
// document, ask one question, screenshot the answer. Never points at production.
//   SHOTS=<dir> node scripts/demo-check.mjs [contract | - for the Ask page] [question]
import { chromium } from "@playwright/test";
import fs from "node:fs";
const login = Object.fromEntries(fs.readFileSync("/root/.legalmind/demo/login.txt", "utf8").trim().split("\n").map(l => l.split("=")));
const shots = process.env.SHOTS, base = "http://127.0.0.1:3299";
const [contract, question] = [process.argv[2] || "MSA", process.argv[3] || "Is our liability under this MSA capped at 12 months of fees?"];
const browser = await chromium.launch({ chromiumSandbox: false });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(base + "/login");
await page.getByLabel("Work email").fill(login.email);
await page.getByLabel("Password", { exact: true }).fill(login.password);
await page.getByRole("button", { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/, { timeout: 20000 });
await page.screenshot({ path: `${shots}/1-dashboard.png` });
let box;
if (contract === "-") {                       // the Ask page, no document selected
  await page.goto(base + "/dashboard/ask");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(2000);        // the page opens on a new, empty chat
  box = page.getByPlaceholder(/Ask LegalMind/);
} else {
  await page.getByRole("link", { name: new RegExp(`^${contract}`) }).first().click();
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: `${shots}/2-workspace.png` });
  const opener = page.locator("button:has-text(\"Ask\")").last();
  if (await opener.count()) await opener.first().click();
  await page.waitForTimeout(1500);
  box = page.getByPlaceholder(/Ask about this document/);
}
const before = await page.evaluate(() => (document.body.innerText.match(/\nSources\n/g) || []).length);
await box.fill(question);
await box.press("Enter");
const t0 = Date.now();
await page.waitForFunction((n) => (document.body.innerText.match(/\nSources\n/g) || []).length > n, before, { timeout: 90000 });
console.log("answer after ms", Date.now() - t0);
await page.waitForTimeout(1000);
await page.screenshot({ path: `${shots}/3-answer.png`, fullPage: false });
await browser.close();
