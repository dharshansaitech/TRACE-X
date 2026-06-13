const puppeteer = require("C:\\Users\\sathe\\website-scanner\\node_modules\\puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000 });

  // Flight Deck
  await page.goto("http://localhost:3000/", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 4000));

  // Click Inject Failure dropdown chevron to test menu
  const buttons = await page.$$("button");
  let mainBtn = null, chevronBtn = null;
  for (const btn of buttons) {
    const text = await page.evaluate((el) => el.textContent.trim(), btn);
    if (text === "Inject Failure") mainBtn = btn;
  }
  // Find the chevron button (sibling, no text)
  if (mainBtn) {
    const parent = await page.evaluateHandle((el) => el.parentElement, mainBtn);
    const siblingBtns = await parent.asElement().$$("button");
    for (const b of siblingBtns) {
      const text = await page.evaluate((el) => el.textContent.trim(), b);
      if (text === "") chevronBtn = b;
    }
  }
  if (chevronBtn) {
    await chevronBtn.click();
    await new Promise((r) => setTimeout(r, 800));
    await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\inject_dropdown.png" });
    // close dropdown
    await chevronBtn.click();
    await new Promise((r) => setTimeout(r, 300));
  }

  // Click the main inject button to inject + verify success message + live feed
  if (mainBtn) {
    await mainBtn.click();
  }
  await new Promise((r) => setTimeout(r, 3000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\after_inject2.png" });

  // Crop region around title + live feed for clarity
  const titleClip = await page.evaluate(() => {
    const el = document.querySelector("h1");
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: 0, y: Math.max(0, r.top - 20), width: 1600, height: 200 };
  });
  if (titleClip) {
    await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\title_area.png", clip: titleClip });
  }

  await new Promise((r) => setTimeout(r, 2000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\after_inject3.png" });

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
