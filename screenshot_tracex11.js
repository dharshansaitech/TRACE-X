const puppeteer = require("C:\\Users\\sathe\\website-scanner\\node_modules\\puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1400 });

  page.on("console", async (msg) => {
    if (msg.text().includes("ARIZE_DEBUG")) {
      const args = msg.args();
      const vals = await Promise.all(args.map((a) => a.jsonValue().catch(() => String(a))));
      console.log("CONSOLE:", JSON.stringify(vals));
    }
  });

  await page.goto("http://localhost:3000/replay/trace-eafd91b8e14f", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 8000));

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
