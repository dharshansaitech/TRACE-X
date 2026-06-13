const puppeteer = require("C:\\Users\\sathe\\website-scanner\\node_modules\\puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1600 });

  await page.goto("http://localhost:3000/repairs", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 1500));

  // Click the first repair card
  await page.evaluate(() => {
    const cards = document.querySelectorAll('[class*="command-card"]');
    if (cards.length) cards[0].click();
  });
  await new Promise((r) => setTimeout(r, 2500));

  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\mc_repairs_detail.png", fullPage: true });

  const counts = await page.evaluate(() => {
    const html = document.body.innerHTML;
    return {
      beforeAfter: (html.match(/Before vs\. After Impact/g) || []).length,
      checksPassed: (html.match(/checks passed/g) || []).length,
    };
  });
  console.log("COUNTS:", JSON.stringify(counts, null, 2));

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
