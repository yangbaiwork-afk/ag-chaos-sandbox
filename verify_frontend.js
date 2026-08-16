const { chromium } = require('playwright');
const assert = require('assert');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto('http://127.0.0.1:8000');

    await page.waitForTimeout(1000);
    const rulesHPs = await page.textContent('#hp-rules');
    console.log("Rules HPs:", rulesHPs);

    // Connect as student
    await page.fill('#studentName', 'Jules');
    await page.click('#connectBtn');

    await page.waitForTimeout(1000);

    const ws = await page.evaluate(() => {
        return window.ws ? "connected" : "disconnected";
    });
    console.log("WS Status:", ws);

    await browser.close();
})();
