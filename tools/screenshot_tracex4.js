const puppeteer = require("C:\\Users\\sathe\\website-scanner\\node_modules\\puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1400 });

  page.on("console", (msg) => {
    if (msg.type() === "error") console.log("CONSOLE ERROR:", msg.text());
  });

  // Title area + success toast - reload and click immediately, screenshot quickly
  await page.goto("http://localhost:3000/", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 6000));

  const buttons = await page.$$("button");
  for (const btn of buttons) {
    const text = await page.evaluate((el) => el.textContent.trim(), btn);
    if (text === "Inject Failure") {
      await btn.click();
      break;
    }
  }
  await new Promise((r) => setTimeout(r, 1500));
  // Screenshot just the top header area to capture success toast
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\toast_area.png", clip: { x: 800, y: 80, width: 800, height: 80 } });

  // Replay Center
  await page.goto("http://localhost:3000/replay/trace-eafd91b8e14f", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 4000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\replay_full.png", fullPage: true });

  // Click Generate Incident Report
  const buttons2 = await page.$$("button");
  for (const btn of buttons2) {
    const text = await page.evaluate((el) => el.textContent.trim(), btn);
    if (text.includes("Generate Incident Report") || text.includes("Regenerate Report")) {
      await btn.click();
      console.log("Clicked report button:", text);
      break;
    }
  }
  await new Promise((r) => setTimeout(r, 4000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\incident_report_modal.png" });

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
