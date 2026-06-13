const puppeteer = require("C:\\Users\\sathe\\website-scanner\\node_modules\\puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1400 });

  await page.goto("http://localhost:3000/dashboard", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 2000));

  // Click "Inject Failure" button
  const clicked = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll("button"));
    const btn = btns.find((b) => b.textContent.includes("Inject Failure"));
    if (btn) { btn.click(); return true; }
    return false;
  });
  console.log("Clicked Inject Failure button:", clicked);

  await new Promise((r) => setTimeout(r, 1500));

  // If a dropdown opened, click "Random"
  await page.evaluate(() => {
    const items = Array.from(document.querySelectorAll("button, a, [role='menuitem']"));
    const random = items.find((b) => b.textContent.trim() === "Random");
    if (random) random.click();
  });

  // Capture quickly after triggering (failure_injected -> failure_detected)
  await new Promise((r) => setTimeout(r, 2500));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\mc_incident_1.png", fullPage: false });

  // Wait for diagnosis/repair stages
  await new Promise((r) => setTimeout(r, 6000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\mc_incident_2.png", fullPage: false });

  // Wait for validation/recovery
  await new Promise((r) => setTimeout(r, 8000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\mc_incident_3.png", fullPage: false });

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
