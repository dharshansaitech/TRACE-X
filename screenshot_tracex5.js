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
  page.on("response", (res) => {
    if (res.url().includes("/insights")) console.log("INSIGHTS RESPONSE:", res.status(), res.url());
  });

  await page.goto("http://localhost:3000/replay/trace-eafd91b8e14f", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 8000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\replay_full2.png", fullPage: true });

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
