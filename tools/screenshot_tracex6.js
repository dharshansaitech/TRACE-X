const puppeteer = require("C:\\Users\\sathe\\website-scanner\\node_modules\\puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1400 });

  page.on("console", (msg) => console.log("CONSOLE:", msg.type(), msg.text()));
  page.on("pageerror", (err) => console.log("PAGEERROR:", err.message, "\n", err.stack));

  await page.goto("http://localhost:3000/replay/trace-eafd91b8e14f", { waitUntil: "networkidle2", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 6000));

  // Dump outerHTML of the grid row containing Arize insights
  const html = await page.evaluate(() => {
    const heading = Array.from(document.querySelectorAll("h3")).find(h => h.textContent.includes("Arize"));
    if (!heading) return "NOT FOUND - no Arize heading";
    let el = heading;
    while (el && !el.className?.toString?.().includes("glass-card")) el = el.parentElement;
    return el ? el.outerHTML.slice(0, 3000) : "container not found";
  });
  console.log("ARIZE HTML:\n", html);

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
