const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto('http://127.0.0.1:8000');

    await page.waitForTimeout(2000);

    // Switch to Level 3
    console.log("Switching to Level 3...");
    await page.evaluate(() => window.sendAction('SetLevel:level3'));
    await page.waitForTimeout(3000); // wait for 3d redraw

    // Aim at tomato 0 first
    await page.evaluate(() => window.sendAction('Target:0'));
    await page.waitForTimeout(2000);

    // Take a screenshot
    await page.screenshot({ path: 'screenshot.png' });
    console.log("Screenshot saved.");

    await browser.close();
})();
