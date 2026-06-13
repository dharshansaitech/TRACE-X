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
  await new Promise((r) => setTimeout(r, 6000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\flightdeck.png" });

  // Click Inject Failure button
  const buttons = await page.$$("button");
  let clicked = false;
  for (const btn of buttons) {
    const text = await page.evaluate((el) => el.textContent, btn);
    if (text && text.includes("Inject Failure")) {
      await btn.click();
      clicked = true;
      break;
    }
  }
  console.log("Clicked Inject Failure:", clicked);
  await new Promise((r) => setTimeout(r, 4000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\flightdeck_after_inject.png" });

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
