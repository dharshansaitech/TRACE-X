const puppeteer = require("C:\\Users\\sathe\\website-scanner\\node_modules\\puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1400 });

  await page.goto("http://localhost:3000/replay/trace-eafd91b8e14f", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 6000));

  const result = await page.evaluate(() => {
    // find the main content column (after sidebar)
    const main = document.querySelector("main") || document.body;
    return main.innerText.slice(0, 3000);
  });
  console.log("PAGE TEXT:\n", result);

  // Count occurrences of key strings
  const counts = await page.evaluate(() => {
    const html = document.body.innerHTML;
    return {
      arizeHeading: (html.match(/Arize MCP Insights/g) || []).length,
      incidentReport: (html.match(/AI Incident Report/g) || []).length,
      animateSpin: (html.match(/animate-spin/g) || []).length,
      gridCols3: (html.match(/lg:grid-cols-3/g) || []).length,
    };
  });
  console.log("COUNTS:", JSON.stringify(counts));

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
