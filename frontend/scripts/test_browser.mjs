import { chromium } from 'playwright';

async function test() {
  console.log('Testing Playwright launch...');
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    console.log('Chromium bundled launch successful');
  } catch (err) {
    console.log('Falling back to msedge channel...');
    browser = await chromium.launch({ channel: 'msedge', headless: true });
    console.log('Edge launch successful');
  }
  const page = await browser.newPage();
  await page.setContent('<h1>Hello RazP</h1>');
  const text = await page.innerText('h1');
  console.log('Page content:', text);
  await browser.close();
}

test().catch(console.error);
