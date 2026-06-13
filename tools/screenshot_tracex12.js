const puppeteer = require("C:\\Users\\sathe\\website-scanner\\node_modules\\puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1400 });

  await page.goto("http://localhost:3000/replay/trace-2a1ba17fa643", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 4000));

  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\arize_insights_fixed.png", fullPage: true });

  const counts = await page.evaluate(() => {
    const html = document.body.innerHTML;
    return {
      arizeHeading: (html.match(/Arize MCP Insights/g) || []).length,
      similarFailures: (html.match(/Similar Historical Failures/g) || []).length,
      featureDrift: (html.match(/Feature Drift/g) || []).length,
      perfBaseline: (html.match(/Performance vs\. Baseline/g) || []).length,
      animateSpin: (html.match(/animate-spin/g) || []).length,
      noSimilar: (html.match(/No similar traces found/g) || []).length,
      matchPct: (html.match(/% match/g) || []).length,
    };
  });
  console.log("COUNTS:", JSON.stringify(counts, null, 2));

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
