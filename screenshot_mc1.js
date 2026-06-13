const puppeteer = require("C:\\Users\\sathe\\website-scanner\\node_modules\\puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1400 });

  // Flight Deck
  await page.goto("http://localhost:3000/dashboard", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 2000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\mc_flightdeck.png", fullPage: true });

  // Replay Center
  await page.goto("http://localhost:3000/replay/trace-f0945413dcdb", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 4000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\mc_replay.png", fullPage: true });

  // Repairs
  await page.goto("http://localhost:3000/repairs", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 2000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\mc_repairs.png", fullPage: true });

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
