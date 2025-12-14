const puppeteer = require('puppeteer');
const fs = require('fs');

(async () => {
  console.log('Starting test...');
  
  const browser = await puppeteer.launch({
    headless: false, // Use headed mode to see what happens
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--window-size=1920,1080'
    ]
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });
  
  // Log all console messages
  page.on('console', msg => {
    const type = msg.type();
    console.log(`[BROWSER ${type.toUpperCase()}] ${msg.text()}`);
  });

  // Log network activity
  page.on('response', async response => {
    const url = response.url();
    const status = response.status();
    if (status >= 400 || url.includes('ws://') || url.includes('wss://')) {
      console.log(`[NETWORK] ${status} ${url}`);
    }
  });

  console.log('Navigating to jamovi...');
  await page.goto('https://jamovi.truyenthong.edu.vn/', {
    waitUntil: 'networkidle0',
    timeout: 60000
  });

  console.log('Waiting for page to stabilize...');
  await new Promise(resolve => setTimeout(resolve, 5000));

  // Check if analyses results appear
  const hasResults = await page.evaluate(() => {
    // Look for results panel or tables
    const resultsPanel = document.querySelector('.silky-results-panel, #results, .jmv-results');
    const hasTables = document.querySelectorAll('table.jmv-results-table').length > 0;
    const hasAnalysisResults = document.querySelectorAll('.silky-results-item').length > 0;
    
    return {
      resultsPanel: !!resultsPanel,
      tablesCount: document.querySelectorAll('table').length,
      analysisResultsCount: document.querySelectorAll('.silky-results-item, .jmv-results-item').length,
      bodyText: document.body.textContent.substring(0, 500)
    };
  });

  console.log('Page state:', JSON.stringify(hasResults, null, 2));

  // Take screenshot
  await page.screenshot({ 
    path: '/root/jamovi/chrome-test/test_descriptives.png', 
    fullPage: true 
  });
  console.log('Screenshot saved');

  // Keep browser open for manual inspection
  console.log('Browser will stay open for 30 seconds for inspection...');
  await new Promise(resolve => setTimeout(resolve, 30000));

  await browser.close();
})();
