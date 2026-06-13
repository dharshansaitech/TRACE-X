const puppeteer = require("C:\\Users\\sathe\\website-scanner\\node_modules\\puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000 });

  page.on("console", (msg) => console.log("CONSOLE:", msg.type(), msg.text()));
  page.on("pageerror", (err) => console.log("PAGEERROR:", err.message));
  page.on("requestfailed", (req) => console.log("REQFAILED:", req.url(), req.failure()?.errorText));
  page.on("response", (res) => {
    if (res.url().includes("/api/")) {
      console.log("API RESPONSE:", res.status(), res.url());
    }
  });

  await page.goto("http://localhost:3000/", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 8000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\fresh_load.png" });

  // Click main inject button
  const buttons = await page.$$("button");
  for (const btn of buttons) {
    const text = await page.evaluate((el) => el.textContent.trim(), btn);
    if (text === "Inject Failure") {
      await btn.click();
      console.log("CLICKED inject failure");
      break;
    }
  }

  await new Promise((r) => setTimeout(r, 8000));
  await page.screenshot({ path: "C:\\Users\\sathe\\trace-x\\shots\\after_click_8s.png" });

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
