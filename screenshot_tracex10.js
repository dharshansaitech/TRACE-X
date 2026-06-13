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

  const info = await page.evaluate(() => {
    const els = Array.from(document.querySelectorAll(".animate-spin"));
    return els.map(el => {
      const rect = el.getBoundingClientRect();
      let parent = el.parentElement;
      let chain = [];
      for (let i = 0; i < 5 && parent; i++) {
        chain.push(parent.className?.toString().slice(0, 80));
        parent = parent.parentElement;
      }
      return { rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }, chain };
    });
  });
  console.log(JSON.stringify(info, null, 2));

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
