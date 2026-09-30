// The dummy walk (G12): the walk rig on a GitHub runner — puppeteer-core in real Chrome, the mock's own window.__walk().
'use strict';
const path = require('path');
const puppeteer = require('puppeteer-core');

(async () => {
  const chrome = process.env.CHROME || '/usr/bin/google-chrome';
  const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--no-sandbox', '--hide-scrollbars'] });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 420, height: 900, deviceScaleFactor: 2.625 });
    await page.goto('file://' + path.resolve('mocks/dummy.html'), { waitUntil: 'load', timeout: 60000 });
    const r = await page.evaluate(() => window.__walk());
    console.log(r.summary);
    process.exitCode = / 0 red$/.test(r.summary) ? 0 : 1;
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(2); });
