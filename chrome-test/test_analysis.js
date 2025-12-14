const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-web-security',
      '--ignore-certificate-errors'
    ]
  });

  const page = await browser.newPage();
  
  // Log console messages
  page.on('console', msg => {
    const type = msg.type();
    if (type === 'error' || type === 'warning') {
      console.log(`CONSOLE ${type.toUpperCase()}: ${msg.text()}`);
    }
  });

  // Log network errors
  page.on('response', response => {
    if (response.status() >= 400) {
      console.log(`HTTP ${response.status()}: ${response.url()}`);
    }
  });

  console.log('Navigating to jamovi...');
  await page.goto('https://jamovi.truyenthong.edu.vn/', {
    waitUntil: 'networkidle2',
    timeout: 30000
  });

  console.log('Waiting for page to load...');
  await new Promise(resolve => setTimeout(resolve, 5000));

  // Check if main elements are present
  const hasAnalysesTab = await page.evaluate(() => {
    const tabs = document.querySelectorAll('.jmv-ribbon-tab, button[data-tabname]');
    return tabs.length > 0;
  });

  console.log('Analyses tab present:', hasAnalysesTab);

  // Check for any critical errors in page
  const pageErrors = await page.evaluate(() => {
    const errors = [];
    // Check for "Connection failed" message
    const connectionError = document.body.textContent.includes('Connection failed');
    if (connectionError) errors.push('Connection failed message visible');
    
    // Check if main app loaded
    const mainDiv = document.getElementById('main');
    if (!mainDiv) errors.push('Main div not found');
    
    return errors;
  });

  if (pageErrors.length > 0) {
    console.log('CRITICAL ERRORS:', pageErrors);
  } else {
    console.log('✓ Page loaded successfully, no critical errors');
  }

  // Take screenshot
  await page.screenshot({ path: '/root/jamovi/chrome-test/screenshot.png', fullPage: true });
  console.log('Screenshot saved to /root/jamovi/chrome-test/screenshot.png');

  await browser.close();
})();
