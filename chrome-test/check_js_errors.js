const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const page = await browser.newPage();
  
  const jsErrors = [];
  const consoleErrors = [];
  
  page.on('pageerror', error => {
    jsErrors.push({
      message: error.message,
      stack: error.stack
    });
    console.log('[PAGE ERROR]', error.message);
  });
  
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
      console.log('[CONSOLE ERROR]', msg.text());
    }
  });

  console.log('Loading jamovi...');
  await page.goto('https://jamovi.truyenthong.edu.vn/', {
    waitUntil: 'networkidle2',
    timeout: 60000
  });

  await new Promise(resolve => setTimeout(resolve, 10000));

  // Check if critical objects exist
  const diagnostics = await page.evaluate(() => {
    const results = {
      hasJQuery: typeof jQuery !== 'undefined',
      hasHost: typeof host !== 'undefined',
      hasInstance: typeof instance !== 'undefined',
      mainElementExists: !!document.getElementById('main'),
      errorCount: 0,
      globalErrors: []
    };
    
    // Check for global error object
    if (window.jamoviErrors) {
      results.errorCount = window.jamoviErrors.length;
      results.globalErrors = window.jamoviErrors;
    }
    
    return results;
  });

  console.log('\n=== Diagnostics ===');
  console.log(JSON.stringify(diagnostics, null, 2));
  
  console.log('\n=== JavaScript Errors ===');
  console.log('Total JS errors:', jsErrors.length);
  if (jsErrors.length > 0) {
    jsErrors.forEach((err, i) => {
      console.log(`\nError ${i + 1}:`);
      console.log('Message:', err.message);
      console.log('Stack:', err.stack?.substring(0, 300));
    });
  }
  
  console.log('\n=== Console Errors ===');
  console.log('Total console errors:', consoleErrors.length);

  await browser.close();
})();
